"""Comprehensive tests for the secure filesystem tools."""

import os
import shutil
import tempfile
import uuid
from pathlib import Path

import pytest

from app.agents.framework.tool import ToolResult
from app.agents.framework.tools.context import ToolContext
from app.agents.framework.tools.filesystem import (
    CopyFileTool,
    CreateDirectoryTool,
    DeleteFileTool,
    EditFileTool,
    FileMetadataTool,
    FileOperationRecord,
    ListDirectoryTool,
    MoveFileTool,
    PathTraversalError,
    ReadFileTool,
    SearchFilesTool,
    WorkspaceSandbox,
    WriteFileTool,
    ZipDirectoryTool,
)
from app.agents.framework.tools.filesystem.audit import FileAuditLogger


# ── Helpers ───────────────────────────────────────────────────


@pytest.fixture
def tmp_workspace() -> Path:
    """Create a temporary directory to serve as the workspace root."""
    path = Path(tempfile.mkdtemp(prefix="trace_fs_test_"))
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def sandbox(tmp_workspace: Path) -> WorkspaceSandbox:
    return WorkspaceSandbox(tmp_workspace)


@pytest.fixture
def ctx() -> ToolContext:
    return ToolContext(
        user_id=str(uuid.uuid4()),
        user_role="admin",
        conversation_id=str(uuid.uuid4()),
    )


def _touch(path: Path, content: str = "hello world\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ── WorkspaceSandbox tests ────────────────────────────────────


class TestWorkspaceSandbox:
    def test_relative_path_resolves_within(self, sandbox: WorkspaceSandbox):
        resolved = sandbox.resolve("some/file.txt")
        assert resolved == sandbox.root / "some/file.txt"

    def test_absolute_path_within_workspace(self, sandbox: WorkspaceSandbox):
        target = sandbox.root / "test.txt"
        _touch(target)
        resolved = sandbox.resolve(str(target))
        assert resolved == target

    def test_path_traversal_raises(self, sandbox: WorkspaceSandbox):
        with pytest.raises(PathTraversalError):
            sandbox.resolve("../etc/passwd")

    def test_deep_traversal_raises(self, sandbox: WorkspaceSandbox):
        with pytest.raises(PathTraversalError):
            sandbox.resolve("valid/../../etc/hosts")

    def test_absolute_outside_raises(self, sandbox: WorkspaceSandbox):
        with pytest.raises(PathTraversalError):
            sandbox.resolve("C:/Windows/system32")

    def test_resolve_parent_creates_sandbox_check(self, sandbox: WorkspaceSandbox):
        resolved = sandbox.resolve_parent("new_dir/file.txt")
        assert str(resolved).startswith(str(sandbox.root))

    def test_resolve_parent_traversal_raises(self, sandbox: WorkspaceSandbox):
        with pytest.raises(PathTraversalError):
            sandbox.resolve_parent("../outside.txt")

    def test_relativize(self, sandbox: WorkspaceSandbox):
        target = sandbox.root / "sub" / "file.txt"
        _touch(target)
        rel = sandbox.relativize(str(target))
        assert rel == "sub\\file.txt" or rel == "sub/file.txt"

    def test_root_property(self, sandbox: WorkspaceSandbox):
        assert sandbox.root == sandbox.root.resolve()

    def test_symlink_traversal(self, sandbox: WorkspaceSandbox, tmp_workspace: Path):
        """Symlinks outside the sandbox should be caught."""
        outside = Path(tempfile.mkdtemp(prefix="outside_"))
        try:
            link_target = tmp_workspace / "escape_link"
            try:
                os.symlink(str(outside), str(link_target))
            except (OSError, NotImplementedError):
                pytest.skip("Symlinks not supported on this platform")

            with pytest.raises(PathTraversalError):
                sandbox.resolve("escape_link/../outside_file.txt")
        finally:
            shutil.rmtree(outside, ignore_errors=True)


# ── FileAuditLogger tests ─────────────────────────────────────


class TestFileAuditLogger:
    def test_log_success(self):
        rec = FileAuditLogger.log_success(
            tool="read_file", operation="read", path="/tmp/test.txt",
            user_id="user1", size_bytes=100,
        )
        assert isinstance(rec, FileOperationRecord)
        assert rec.success is True
        assert rec.tool == "read_file"
        assert rec.size_bytes == 100

    def test_log_failure(self):
        rec = FileAuditLogger.log_failure(
            tool="write_file", operation="write", path="/tmp/test.txt",
            user_id="user1", error="Permission denied",
        )
        assert isinstance(rec, FileOperationRecord)
        assert rec.success is False
        assert rec.error == "Permission denied"

    def test_log_has_timestamp(self):
        rec = FileAuditLogger.log_success(
            tool="ping", operation="noop", path="/dev/null",
            user_id="u",
        )
        assert rec.timestamp is not None
        assert "T" in rec.timestamp  # ISO 8601


# ── ReadFileTool tests ────────────────────────────────────────


class TestReadFileTool:
    @pytest.fixture
    def tool(self, sandbox: WorkspaceSandbox) -> ReadFileTool:
        t = ReadFileTool()
        t._sandbox = sandbox
        return t

    async def test_reads_file(self, tool: ReadFileTool, tmp_workspace: Path, ctx: ToolContext):
        path = _touch(tmp_workspace / "hello.txt", "line1\nline2\nline3\n")
        result = await tool.execute({"path": str(path)}, ctx)
        assert result.success
        assert result.data["content"] == "line1\nline2\nline3\n"
        assert result.data["line_count"] == 3

    async def test_offset(self, tool: ReadFileTool, tmp_workspace: Path, ctx: ToolContext):
        path = _touch(tmp_workspace / "lines.txt", "a\nb\nc\nd\ne\n")
        result = await tool.execute({"path": str(path), "offset": 3}, ctx)
        assert result.success
        assert result.data["content"] == "c\nd\ne\n"

    async def test_offset_and_limit(self, tool: ReadFileTool, tmp_workspace: Path, ctx: ToolContext):
        path = _touch(tmp_workspace / "lines.txt", "a\nb\nc\nd\ne\n")
        result = await tool.execute({"path": str(path), "offset": 2, "limit": 2}, ctx)
        assert result.success
        assert result.data["content"] == "b\nc\n"

    async def test_file_not_found(self, tool: ReadFileTool, tmp_workspace: Path, ctx: ToolContext):
        result = await tool.execute({"path": str(tmp_workspace / "nope.txt")}, ctx)
        assert not result.success
        assert "not found" in result.error

    async def test_path_traversal_blocked(self, tool: ReadFileTool, ctx: ToolContext):
        result = await tool.execute({"path": "../etc/passwd"}, ctx)
        assert not result.success
        assert "outside the workspace" in result.error


# ── WriteFileTool tests ───────────────────────────────────────


class TestWriteFileTool:
    @pytest.fixture
    def tool(self, sandbox: WorkspaceSandbox) -> WriteFileTool:
        t = WriteFileTool()
        t._sandbox = sandbox
        return t

    async def test_writes_file(self, tool: WriteFileTool, tmp_workspace: Path, ctx: ToolContext):
        path = tmp_workspace / "new_file.txt"
        result = await tool.execute({"path": str(path), "content": "hello"}, ctx)
        assert result.success
        assert path.read_text() == "hello"

    async def test_creates_parent_dirs(self, tool: WriteFileTool, tmp_workspace: Path, ctx: ToolContext):
        path = tmp_workspace / "a" / "b" / "c" / "deep.txt"
        result = await tool.execute({"path": str(path), "content": "deep"}, ctx)
        assert result.success
        assert path.exists()
        assert path.read_text() == "deep"

    async def test_overwrites_existing(self, tool: WriteFileTool, tmp_workspace: Path, ctx: ToolContext):
        path = _touch(tmp_workspace / "existing.txt", "old")
        result = await tool.execute({"path": str(path), "content": "new"}, ctx)
        assert result.success
        assert path.read_text() == "new"

    async def test_traversal_blocked(self, tool: WriteFileTool, ctx: ToolContext):
        result = await tool.execute({"path": "../../escape.txt", "content": "x"}, ctx)
        assert not result.success
        assert "outside the workspace" in result.error


# ── EditFileTool tests ────────────────────────────────────────


class TestEditFileTool:
    @pytest.fixture
    def tool(self, sandbox: WorkspaceSandbox) -> EditFileTool:
        t = EditFileTool()
        t._sandbox = sandbox
        return t

    async def test_simple_replacement(self, tool: EditFileTool, tmp_workspace: Path, ctx: ToolContext):
        path = _touch(tmp_workspace / "edit.txt", "Hello World")
        result = await tool.execute({
            "path": str(path), "old_string": "World", "new_string": "There",
        }, ctx)
        assert result.success
        assert result.data["replacements"] == 1
        assert path.read_text() == "Hello There"

    async def test_no_match(self, tool: EditFileTool, tmp_workspace: Path, ctx: ToolContext):
        path = _touch(tmp_workspace / "edit.txt", "Hello World")
        result = await tool.execute({
            "path": str(path), "old_string": "ZZZ", "new_string": "YYY",
        }, ctx)
        assert not result.success
        assert "Could not find" in result.error

    async def test_replace_all(self, tool: EditFileTool, tmp_workspace: Path, ctx: ToolContext):
        path = _touch(tmp_workspace / "edit.txt", "a a a")
        result = await tool.execute({
            "path": str(path), "old_string": "a", "new_string": "b", "replace_all": True,
        }, ctx)
        assert result.success
        assert result.data["replacements"] == 3
        assert path.read_text() == "b b b"

    async def test_file_not_found(self, tool: EditFileTool, tmp_workspace: Path, ctx: ToolContext):
        result = await tool.execute({
            "path": str(tmp_workspace / "nope.txt"), "old_string": "a", "new_string": "b",
        }, ctx)
        assert not result.success
        assert "not found" in result.error

    async def test_traversal_blocked(self, tool: EditFileTool, ctx: ToolContext):
        result = await tool.execute({
            "path": "../../secrets.txt", "old_string": "a", "new_string": "b",
        }, ctx)
        assert not result.success
        assert "outside the workspace" in result.error


# ── DeleteFileTool tests ──────────────────────────────────────


class TestDeleteFileTool:
    @pytest.fixture
    def tool(self, sandbox: WorkspaceSandbox) -> DeleteFileTool:
        t = DeleteFileTool()
        t._sandbox = sandbox
        return t

    async def test_deletes_file(self, tool: DeleteFileTool, tmp_workspace: Path, ctx: ToolContext):
        path = _touch(tmp_workspace / "delete_me.txt")
        result = await tool.execute({"path": str(path)}, ctx)
        assert result.success
        assert not path.exists()

    async def test_deletes_empty_directory(self, tool: DeleteFileTool, tmp_workspace: Path, ctx: ToolContext):
        d = tmp_workspace / "empty_dir"
        d.mkdir()
        result = await tool.execute({"path": str(d)}, ctx)
        assert result.success
        assert not d.exists()

    async def test_not_found(self, tool: DeleteFileTool, tmp_workspace: Path, ctx: ToolContext):
        result = await tool.execute({"path": str(tmp_workspace / "ghost.txt")}, ctx)
        assert not result.success
        assert "not found" in result.error

    async def test_traversal_blocked(self, tool: DeleteFileTool, ctx: ToolContext):
        result = await tool.execute({"path": "../outside.txt"}, ctx)
        assert not result.success
        assert "outside the workspace" in result.error


# ── MoveFileTool tests ────────────────────────────────────────


class TestMoveFileTool:
    @pytest.fixture
    def tool(self, sandbox: WorkspaceSandbox) -> MoveFileTool:
        t = MoveFileTool()
        t._sandbox = sandbox
        return t

    async def test_moves_file(self, tool: MoveFileTool, tmp_workspace: Path, ctx: ToolContext):
        src = _touch(tmp_workspace / "source.txt")
        dst = tmp_workspace / "dest.txt"
        result = await tool.execute({"source": str(src), "destination": str(dst)}, ctx)
        assert result.success
        assert dst.exists()
        assert not src.exists()

    async def test_moves_to_subdirectory(self, tool: MoveFileTool, tmp_workspace: Path, ctx: ToolContext):
        src = _touch(tmp_workspace / "move_me.txt")
        dst = tmp_workspace / "sub" / "moved.txt"
        result = await tool.execute({"source": str(src), "destination": str(dst)}, ctx)
        assert result.success
        assert dst.exists()
        assert dst.read_text() == "hello world\n"

    async def test_source_not_found(self, tool: MoveFileTool, tmp_workspace: Path, ctx: ToolContext):
        result = await tool.execute({
            "source": str(tmp_workspace / "ghost.txt"),
            "destination": str(tmp_workspace / "gone.txt"),
        }, ctx)
        assert not result.success
        assert "not found" in result.error

    async def test_traversal_blocked(self, tool: MoveFileTool, ctx: ToolContext):
        result = await tool.execute({
            "source": "valid.txt", "destination": "../../outside.txt",
        }, ctx)
        assert not result.success
        assert "outside the workspace" in result.error


# ── CopyFileTool tests ────────────────────────────────────────


class TestCopyFileTool:
    @pytest.fixture
    def tool(self, sandbox: WorkspaceSandbox) -> CopyFileTool:
        t = CopyFileTool()
        t._sandbox = sandbox
        return t

    async def test_copies_file(self, tool: CopyFileTool, tmp_workspace: Path, ctx: ToolContext):
        src = _touch(tmp_workspace / "src.txt", "copy me")
        dst = tmp_workspace / "dst.txt"
        result = await tool.execute({"source": str(src), "destination": str(dst)}, ctx)
        assert result.success
        assert dst.exists()
        assert dst.read_text() == "copy me"
        assert src.exists()

    async def test_copies_directory(self, tool: CopyFileTool, tmp_workspace: Path, ctx: ToolContext):
        src_dir = tmp_workspace / "src_dir"
        src_dir.mkdir()
        _touch(src_dir / "a.txt", "a")
        _touch(src_dir / "b.txt", "b")
        dst_dir = tmp_workspace / "dst_dir"
        result = await tool.execute({"source": str(src_dir), "destination": str(dst_dir)}, ctx)
        assert result.success
        assert (dst_dir / "a.txt").exists()
        assert (dst_dir / "b.txt").exists()

    async def test_source_not_found(self, tool: CopyFileTool, tmp_workspace: Path, ctx: ToolContext):
        result = await tool.execute({
            "source": str(tmp_workspace / "ghost.txt"),
            "destination": str(tmp_workspace / "x.txt"),
        }, ctx)
        assert not result.success
        assert "not found" in result.error


# ── ListDirectoryTool tests ───────────────────────────────────


class TestListDirectoryTool:
    @pytest.fixture
    def tool(self, sandbox: WorkspaceSandbox) -> ListDirectoryTool:
        t = ListDirectoryTool()
        t._sandbox = sandbox
        return t

    async def test_lists_directory(self, tool: ListDirectoryTool, tmp_workspace: Path, ctx: ToolContext):
        _touch(tmp_workspace / "a.txt")
        _touch(tmp_workspace / "b.txt")
        (tmp_workspace / "sub").mkdir()
        result = await tool.execute({"path": str(tmp_workspace)}, ctx)
        assert result.success
        assert result.data["total"] == 3
        names = {e["name"] for e in result.data["entries"]}
        assert names == {"a.txt", "b.txt", "sub"}

    async def test_with_glob_pattern(self, tool: ListDirectoryTool, tmp_workspace: Path, ctx: ToolContext):
        _touch(tmp_workspace / "a.py")
        _touch(tmp_workspace / "b.py")
        _touch(tmp_workspace / "c.txt")
        result = await tool.execute({"path": str(tmp_workspace), "pattern": "*.py"}, ctx)
        assert result.success
        assert result.data["total"] == 2
        assert all(e["name"].endswith(".py") for e in result.data["entries"])

    async def test_not_found(self, tool: ListDirectoryTool, tmp_workspace: Path, ctx: ToolContext):
        result = await tool.execute({"path": str(tmp_workspace / "nope")}, ctx)
        assert not result.success
        assert "not found" in result.error


# ── SearchFilesTool tests ─────────────────────────────────────


class TestSearchFilesTool:
    @pytest.fixture
    def tool(self, sandbox: WorkspaceSandbox) -> SearchFilesTool:
        t = SearchFilesTool()
        t._sandbox = sandbox
        return t

    async def test_glob_search(self, tool: SearchFilesTool, tmp_workspace: Path, ctx: ToolContext):
        _touch(tmp_workspace / "a.py")
        _touch(tmp_workspace / "b.py")
        (tmp_workspace / "sub").mkdir()
        _touch(tmp_workspace / "sub" / "c.py")
        result = await tool.execute({"pattern": "**/*.py", "path": str(tmp_workspace)}, ctx)
        assert result.success
        assert result.data["total"] == 3

    async def test_simple_pattern(self, tool: SearchFilesTool, tmp_workspace: Path, ctx: ToolContext):
        _touch(tmp_workspace / "data.json")
        _touch(tmp_workspace / "data.xml")
        result = await tool.execute({"pattern": "*.json", "path": str(tmp_workspace)}, ctx)
        assert result.success
        assert result.data["total"] == 1
        assert result.data["files"][0]["name"] == "data.json"

    async def test_max_results(self, tool: SearchFilesTool, tmp_workspace: Path, ctx: ToolContext):
        for i in range(10):
            _touch(tmp_workspace / f"file_{i}.txt")
        result = await tool.execute({
            "pattern": "*.txt", "path": str(tmp_workspace), "max_results": 3,
        }, ctx)
        assert result.success
        assert result.data["total"] == 3
        assert result.data["truncated"] is True

    async def test_empty_pattern_fails(self, tool: SearchFilesTool, ctx: ToolContext):
        result = await tool.execute({"pattern": ""}, ctx)
        assert not result.success
        assert "cannot be empty" in result.error


# ── FileMetadataTool tests ────────────────────────────────────


class TestFileMetadataTool:
    @pytest.fixture
    def tool(self, sandbox: WorkspaceSandbox) -> FileMetadataTool:
        t = FileMetadataTool()
        t._sandbox = sandbox
        return t

    async def test_file_metadata(self, tool: FileMetadataTool, tmp_workspace: Path, ctx: ToolContext):
        path = _touch(tmp_workspace / "meta.txt", "metadata test")
        result = await tool.execute({"path": str(path)}, ctx)
        assert result.success
        assert result.data["name"] == "meta.txt"
        assert result.data["type"] == "file"
        assert result.data["size_bytes"] == len("metadata test")

    async def test_directory_metadata(self, tool: FileMetadataTool, tmp_workspace: Path, ctx: ToolContext):
        (tmp_workspace / "sub").mkdir()
        result = await tool.execute({"path": str(tmp_workspace / "sub")}, ctx)
        assert result.success
        assert result.data["type"] == "directory"

    async def test_not_found(self, tool: FileMetadataTool, tmp_workspace: Path, ctx: ToolContext):
        result = await tool.execute({"path": str(tmp_workspace / "nope")}, ctx)
        assert not result.success
        assert "not found" in result.error

    async def test_has_timestamps(self, tool: FileMetadataTool, tmp_workspace: Path, ctx: ToolContext):
        path = _touch(tmp_workspace / "ts.txt")
        result = await tool.execute({"path": str(path)}, ctx)
        assert result.success
        assert result.data["created_at"] > 0
        assert result.data["modified_at"] > 0


# ── CreateDirectoryTool tests ─────────────────────────────────


class TestCreateDirectoryTool:
    @pytest.fixture
    def tool(self, sandbox: WorkspaceSandbox) -> CreateDirectoryTool:
        t = CreateDirectoryTool()
        t._sandbox = sandbox
        return t

    async def test_creates_directory(self, tool: CreateDirectoryTool, tmp_workspace: Path, ctx: ToolContext):
        d = tmp_workspace / "new_dir"
        result = await tool.execute({"path": str(d)}, ctx)
        assert result.success
        assert d.exists()
        assert d.is_dir()

    async def test_creates_nested_directories(self, tool: CreateDirectoryTool, tmp_workspace: Path, ctx: ToolContext):
        d = tmp_workspace / "a" / "b" / "c"
        result = await tool.execute({"path": str(d)}, ctx)
        assert result.success
        assert d.exists()

    async def test_existing_directory(self, tool: CreateDirectoryTool, tmp_workspace: Path, ctx: ToolContext):
        d = tmp_workspace / "existing"
        d.mkdir()
        result = await tool.execute({"path": str(d)}, ctx)
        assert result.success
        assert result.data["created"] is False

    async def test_traversal_blocked(self, tool: CreateDirectoryTool, ctx: ToolContext):
        result = await tool.execute({"path": "../../escape"}, ctx)
        assert not result.success
        assert "outside the workspace" in result.error


# ── ZipDirectoryTool tests ────────────────────────────────────


class TestZipDirectoryTool:
    @pytest.fixture
    def tool(self, sandbox: WorkspaceSandbox) -> ZipDirectoryTool:
        t = ZipDirectoryTool()
        t._sandbox = sandbox
        return t

    async def test_zips_directory(self, tool: ZipDirectoryTool, tmp_workspace: Path, ctx: ToolContext):
        src = tmp_workspace / "to_zip"
        src.mkdir()
        _touch(src / "a.txt", "aaa")
        _touch(src / "b.txt", "bbb")
        dst = tmp_workspace / "archive.zip"
        result = await tool.execute({
            "source_path": str(src), "output_path": str(dst),
        }, ctx)
        assert result.success
        assert dst.exists()
        assert result.data["file_count"] == 2
        assert result.data["size_bytes"] > 0

    async def test_zips_with_pattern(self, tool: ZipDirectoryTool, tmp_workspace: Path, ctx: ToolContext):
        src = tmp_workspace / "mixed"
        src.mkdir()
        _touch(src / "data.py", "py")
        _touch(src / "data.txt", "txt")
        dst = tmp_workspace / "py_archive.zip"
        result = await tool.execute({
            "source_path": str(src), "output_path": str(dst),
            "include_pattern": "*.py",
        }, ctx)
        assert result.success
        assert result.data["file_count"] == 1

    async def test_source_not_found(self, tool: ZipDirectoryTool, tmp_workspace: Path, ctx: ToolContext):
        result = await tool.execute({
            "source_path": str(tmp_workspace / "nope"),
        }, ctx)
        assert not result.success
        assert "not found" in result.error

    async def test_source_is_file_fails(self, tool: ZipDirectoryTool, tmp_workspace: Path, ctx: ToolContext):
        path = _touch(tmp_workspace / "not_a_dir.txt")
        result = await tool.execute({"source_path": str(path)}, ctx)
        assert not result.success
        assert "not a directory" in result.error

    async def test_traversal_blocked(self, tool: ZipDirectoryTool, ctx: ToolContext):
        result = await tool.execute({"source_path": "../outside_dir"}, ctx)
        assert not result.success
        assert "outside the workspace" in result.error


# ── Integration: ToolExecutor compatibility ───────────────────


class TestToolExecutorCompatibility:
    """Verify each tool works correctly with the ToolExecutor pattern."""

    async def test_tool_metadata_is_valid(self):
        """All tools must have tool_id, name, description, category."""
        from app.agents.framework.tools.filesystem import (
            CopyFileTool,
            CreateDirectoryTool,
            DeleteFileTool,
            EditFileTool,
            FileMetadataTool,
            ListDirectoryTool,
            MoveFileTool,
            ReadFileTool,
            SearchFilesTool,
            WriteFileTool,
            ZipDirectoryTool,
        )
        tools = [
            ReadFileTool(), WriteFileTool(), EditFileTool(), DeleteFileTool(),
            MoveFileTool(), CopyFileTool(), ListDirectoryTool(), SearchFilesTool(),
            FileMetadataTool(), CreateDirectoryTool(), ZipDirectoryTool(),
        ]
        for t in tools:
            assert t.tool_id, f"{type(t).__name__} missing tool_id"
            assert t.name, f"{type(t).__name__} missing name"
            assert t.description, f"{type(t).__name__} missing description"
            assert t.category, f"{type(t).__name__} missing category"
            assert t.input_schema, f"{type(t).__name__} missing input_schema"
            assert t.output_schema, f"{type(t).__name__} missing output_schema"

    async def test_tool_result_structure(self, tmp_workspace: Path, ctx: ToolContext, sandbox: WorkspaceSandbox):
        """All tools return ToolResult with success/error/data pattern."""
        tool = ReadFileTool()
        tool._sandbox = sandbox
        result = await tool.execute({"path": str(tmp_workspace / "nope.txt")}, ctx)
        assert isinstance(result, ToolResult)
        assert hasattr(result, "success")
        assert hasattr(result, "error")
        assert hasattr(result, "data")
        assert not result.success
        assert result.error is not None


# ── Edge case tests ───────────────────────────────────────────


class TestEdgeCases:
    async def test_empty_file_read(self, tmp_workspace: Path, ctx: ToolContext, sandbox: WorkspaceSandbox):
        empty = tmp_workspace / "empty.txt"
        empty.write_text("", encoding="utf-8")
        tool = ReadFileTool()
        tool._sandbox = sandbox
        result = await tool.execute({"path": str(empty)}, ctx)
        assert result.success
        assert result.data["content"] == ""
        assert result.data["line_count"] == 0

    async def test_write_empty_content(self, tmp_workspace: Path, ctx: ToolContext, sandbox: WorkspaceSandbox):
        tool = WriteFileTool()
        tool._sandbox = sandbox
        result = await tool.execute({"path": str(tmp_workspace / "empty.txt"), "content": ""}, ctx)
        assert result.success
        assert result.data["size_bytes"] == 0

    async def test_special_characters_in_filename(self, tmp_workspace: Path, ctx: ToolContext, sandbox: WorkspaceSandbox):
        tool = WriteFileTool()
        tool._sandbox = sandbox
        name = "file with spaces (1).txt"
        result = await tool.execute({"path": str(tmp_workspace / name), "content": "test"}, ctx)
        assert result.success
        assert (tmp_workspace / name).exists()

    async def test_very_large_content_warning(self, tmp_workspace: Path, ctx: ToolContext, sandbox: WorkspaceSandbox):
        tool = ReadFileTool()
        tool._sandbox = sandbox
        big = tmp_workspace / "big.bin"
        big.write_bytes(b"x" * (64 * 1024 * 1024 + 1))
        result = await tool.execute({"path": str(big)}, ctx)
        assert not result.success
        assert "too large" in result.error

    async def test_edit_empty_string_raises(self, tmp_workspace: Path, ctx: ToolContext, sandbox: WorkspaceSandbox):
        tool = EditFileTool()
        tool._sandbox = sandbox
        result = await tool.execute({
            "path": str(tmp_workspace / "x.txt"),
            "old_string": "", "new_string": "y",
        }, ctx)
        assert not result.success
        assert "cannot be empty" in result.error

    async def test_delete_non_empty_directory_fails(self, tmp_workspace: Path, ctx: ToolContext, sandbox: WorkspaceSandbox):
        tool = DeleteFileTool()
        tool._sandbox = sandbox
        d = tmp_workspace / "nonempty"
        d.mkdir()
        _touch(d / "file.txt")
        result = await tool.execute({"path": str(d)}, ctx)
        assert not result.success

    async def test_delete_non_empty_directory_recursive(self, tmp_workspace: Path, ctx: ToolContext, sandbox: WorkspaceSandbox):
        tool = DeleteFileTool()
        tool._sandbox = sandbox
        d = tmp_workspace / "nonempty"
        d.mkdir()
        _touch(d / "file.txt")
        result = await tool.execute({"path": str(d), "recursive": True}, ctx)
        assert result.success
        assert not d.exists()

    async def test_copy_to_self(self, tmp_workspace: Path, ctx: ToolContext, sandbox: WorkspaceSandbox):
        tool = CopyFileTool()
        tool._sandbox = sandbox
        src = _touch(tmp_workspace / "self.txt", "data")
        result_cp = await tool.execute({
            "source": str(src), "destination": str(tmp_workspace / "self_copy.txt"),
        }, ctx)
        assert result_cp.success


# ── Workspace-root guard ──────────────────────────────────────


class TestWorkspaceRootGuard:
    """The root guard must block destructive access but permit read-only access.

    It previously applied to every caller of ``resolve()``, so listing or
    searching the workspace root — the primary use case of those tools —
    failed with "cannot target workspace root".
    """

    def test_root_blocked_by_default(self, sandbox: WorkspaceSandbox, tmp_workspace: Path):
        with pytest.raises(PathTraversalError, match="workspace root"):
            sandbox.resolve(str(tmp_workspace))

    def test_root_allowed_for_read_only_callers(
        self, sandbox: WorkspaceSandbox, tmp_workspace: Path
    ):
        assert sandbox.resolve(str(tmp_workspace), allow_root=True) == tmp_workspace.resolve()

    def test_subpaths_unaffected(self, sandbox: WorkspaceSandbox, tmp_workspace: Path):
        target = tmp_workspace / "a.txt"
        _touch(target)
        assert sandbox.resolve(str(target)) == target.resolve()

    def test_git_still_blocked_even_when_root_allowed(
        self, sandbox: WorkspaceSandbox, tmp_workspace: Path
    ):
        (tmp_workspace / ".git").mkdir()
        with pytest.raises(PathTraversalError, match=".git"):
            sandbox.resolve(str(tmp_workspace / ".git"), allow_root=True)

    def test_traversal_still_blocked_when_root_allowed(self, sandbox: WorkspaceSandbox):
        with pytest.raises(PathTraversalError, match="outside the workspace"):
            sandbox.resolve("../../etc/passwd", allow_root=True)

    async def test_delete_tool_still_refuses_workspace_root(
        self, sandbox: WorkspaceSandbox, tmp_workspace: Path, ctx: ToolContext
    ):
        tool = DeleteFileTool()
        tool._sandbox = sandbox
        result = await tool.execute({"path": str(tmp_workspace)}, ctx)
        assert not result.success
        assert "workspace root" in result.error

    async def test_write_tool_still_refuses_workspace_root(
        self, sandbox: WorkspaceSandbox, tmp_workspace: Path, ctx: ToolContext
    ):
        tool = WriteFileTool()
        tool._sandbox = sandbox
        result = await tool.execute(
            {"path": str(tmp_workspace), "content": "x"}, ctx
        )
        assert not result.success
        assert "workspace root" in result.error
