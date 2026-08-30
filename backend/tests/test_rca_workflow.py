"""Tests for the Root Cause Analysis agent's tool-calling contract.

The agent must always run ``evidence_collection`` before ``root_cause`` and
hand the collected summary over as ``evidence_summary``.  ``root_cause`` must
never be dispatched without one — an ungrounded analysis is worse than no
analysis, so the agent is expected to stay silent instead.
"""

import pytest

from app.agents.framework.agents.rca_agent import RootCauseAnalysisAgent
from app.agents.framework.context import AgentContext
from app.agents.framework.tool import ToolResult


class _RecordingExecutor:
    """Tool executor that records every call and replays canned results."""

    def __init__(self, results: dict[str, ToolResult]) -> None:
        self._results = results
        self.calls: list[tuple[str, dict]] = []

    @property
    def tool_ids(self) -> list[str]:
        return [tool_id for tool_id, _ in self.calls]

    def params_for(self, tool_id: str) -> dict:
        for called_id, params in self.calls:
            if called_id == tool_id:
                return params
        raise AssertionError(f"{tool_id} was never called")

    async def execute(self, tool_id: str, params: dict, context) -> ToolResult:
        self.calls.append((tool_id, params))
        return self._results.get(tool_id, ToolResult(data=None, error="unstubbed tool"))


def _incident_result() -> ToolResult:
    return ToolResult(data={
        "incidents": [{"name": "Pump P-101 vibration", "type": "Incident", "confidence": 0.8}],
        "documents": [{"document_name": "incident-log.pdf", "score": 0.7, "content": "vibration"}],
        "total_incidents": 1,
        "total_documents": 1,
    })


def _evidence_result() -> ToolResult:
    return ToolResult(data={
        "entity_id": "e1",
        "entity_name": "P-101",
        "graph_evidence": [{
            "entity_name": "Bearing B-7", "entity_type": "Component",
            "relationship": "PART_OF", "confidence": 0.9,
        }],
        "document_evidence": [{
            "document_name": "inspection-2024-03.pdf", "score": 0.8,
            "content": "bearing wear observed",
        }],
        "total_graph": 1,
        "total_documents": 1,
    })


def _empty_evidence_result() -> ToolResult:
    return ToolResult(data={
        "entity_id": "unknown", "entity_name": "P-101",
        "graph_evidence": [], "document_evidence": [],
        "total_graph": 0, "total_documents": 0,
    })


def _rca_result() -> ToolResult:
    return ToolResult(data={
        "incident_description": "test",
        "entity": "P-101",
        "analysis": "## Root Cause Analysis\nBearing wear per inspection-2024-03.pdf.",
    })


def _context(question: str) -> AgentContext:
    return AgentContext(user_id="u1", user_role="Engineer", question=question)


async def _run(question: str, results: dict[str, ToolResult]) -> _RecordingExecutor:
    executor = _RecordingExecutor(results)
    agent = RootCauseAnalysisAgent(tool_executor=executor)
    await agent.execute(_context(question))
    return executor


class TestEvidenceBeforeRootCause:
    @pytest.mark.asyncio
    async def test_evidence_collection_precedes_root_cause(self) -> None:
        executor = await _run("What caused the pump P-101 failure?", {
            "incident_search": _incident_result(),
            "evidence_collection": _evidence_result(),
            "root_cause": _rca_result(),
        })

        called = executor.tool_ids
        assert "evidence_collection" in called
        assert "root_cause" in called
        assert called.index("evidence_collection") < called.index("root_cause")

    @pytest.mark.asyncio
    async def test_collected_evidence_is_passed_through(self) -> None:
        executor = await _run("What caused the pump P-101 failure?", {
            "incident_search": _incident_result(),
            "evidence_collection": _evidence_result(),
            "root_cause": _rca_result(),
        })

        summary = executor.params_for("root_cause")["evidence_summary"]
        assert summary.strip()
        assert "Bearing B-7" in summary
        assert "inspection-2024-03.pdf" in summary

    @pytest.mark.asyncio
    async def test_root_cause_skipped_when_no_evidence_collected(self) -> None:
        """An empty evidence_collection result must abort the analysis."""
        executor = await _run("What caused the pump P-101 failure?", {
            "incident_search": _incident_result(),
            "evidence_collection": _empty_evidence_result(),
            "root_cause": _rca_result(),
        })

        assert "evidence_collection" in executor.tool_ids
        assert "root_cause" not in executor.tool_ids

    @pytest.mark.asyncio
    async def test_corrective_actions_also_collect_evidence_first(self) -> None:
        """The corrective-action path used to call root_cause with no evidence."""
        executor = await _run("Corrective actions for pump P-101 fault", {
            "incident_search": _incident_result(),
            "evidence_collection": _evidence_result(),
            "root_cause": _rca_result(),
        })

        called = executor.tool_ids
        assert called.index("evidence_collection") < called.index("root_cause")
        assert executor.params_for("root_cause")["evidence_summary"].strip()

    @pytest.mark.asyncio
    async def test_no_root_cause_call_ever_lacks_evidence(self) -> None:
        for question in (
            "What caused the pump P-101 failure?",
            "Corrective actions for pump P-101 fault",
            "Gather evidence for pump P-101 leak",
        ):
            executor = await _run(question, {
                "incident_search": _incident_result(),
                "evidence_collection": _evidence_result(),
                "root_cause": _rca_result(),
            })
            for tool_id, params in executor.calls:
                if tool_id == "root_cause":
                    assert params.get("evidence_summary", "").strip(), question
