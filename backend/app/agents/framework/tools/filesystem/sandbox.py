"""Workspace sandbox — prevents path traversal outside the workspace root."""

import os
from pathlib import Path


class PathTraversalError(Exception):
    """Raised when a path attempts to escape the workspace sandbox."""


class WorkspaceSandbox:
    """Restricts all file operations to within a configured workspace root."""

    def __init__(self, workspace_root: str | Path) -> None:
        self._root = Path(workspace_root).resolve()

    @property
    def root(self) -> Path:
        return self._root

    def _prevent_symlink_attack(self, path: Path) -> None:
        """Check if any part of the path is a symlink pointing outside the workspace."""
        current = path
        while current != current.parent:
            if current.is_symlink():
                try:
                    target = current.resolve()
                    if not self._is_within(target):
                        raise PathTraversalError(f"Symlink attack detected: {current} points outside workspace.")
                except OSError:
                    pass
            current = current.parent

    def _prevent_unsafe_operations(
        self, path: Path, *, allow_root: bool = False
    ) -> None:
        """Prevent modifying critical workspace files like .git or system files.

        ``allow_root`` is set by read-only callers. Targeting the workspace
        root is destructive for a delete/move/write, but it is the normal
        case for listing or searching the workspace, so the root guard must
        not apply to those.
        """
        if ".git" in path.parts:
            raise PathTraversalError("Unsafe operation: cannot modify .git directory.")
        if path == self._root and not allow_root:
            raise PathTraversalError("Unsafe operation: cannot target workspace root.")

    def resolve(self, path: str | Path, *, allow_root: bool = False) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self._root / candidate

        self._prevent_symlink_attack(candidate)
        candidate = candidate.resolve()

        if not self._is_within(candidate):
            raise PathTraversalError(
                f"Path '{candidate}' is outside the workspace root '{self._root}'."
            )

        self._prevent_unsafe_operations(candidate, allow_root=allow_root)
        return candidate

    def resolve_parent(self, path: str | Path) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self._root / candidate

        self._prevent_symlink_attack(candidate)

        try:
            resolved = candidate.resolve(strict=False)
        except OSError:
            resolved = candidate.absolute()

        if not self._is_within(resolved):
            raise PathTraversalError(
                f"Path '{resolved}' is outside the workspace root '{self._root}'."
            )

        self._prevent_unsafe_operations(resolved)
        return resolved

    def relativize(self, path: str | Path) -> str:
        resolved = self.resolve(path, allow_root=True)
        try:
            return str(resolved.relative_to(self._root))
        except ValueError:
            return str(resolved)

    def _is_within(self, candidate: Path) -> bool:
        try:
            candidate.relative_to(self._root)
            return True
        except ValueError:
            return False
