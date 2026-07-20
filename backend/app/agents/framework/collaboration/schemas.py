import time
from typing import Any

from pydantic import BaseModel, Field


class CollaborationContext(BaseModel):
    """Snapshot of the execution so far, shared with each agent before it runs.

    Provides a structured view of previous agents' work so the current agent
    can challenge findings, request evidence, or build on prior reasoning.
    """

    execution_history: list["ExecutionSnapshot"] = Field(default_factory=list)
    messages: list["AgentMessage"] = Field(default_factory=list)
    total_steps: int = 0
    current_step_index: int = 0

    def to_prompt_block(self) -> str:
        """Format as a markdown block for LLM prompt injection."""
        lines = ["## Collaboration Context — Prior Agent Outputs\n"]
        if not self.execution_history:
            lines.append("No prior agents have executed yet.\n")
        else:
            for snap in self.execution_history:
                lines.append(f"### {snap.agent_name} ({snap.agent_id})")
                lines.append(f"**Confidence**: {snap.confidence:.2f}")
                lines.append(f"**Tools used**: {', '.join(snap.tools_used) if snap.tools_used else 'none'}")
                if snap.reasoning:
                    lines.append(f"**Reasoning**: {snap.reasoning}")
                if snap.answer:
                    lines.append(f"**Findings**: {snap.answer[:500]}")
                lines.append("")

        if self.messages:
            lines.append("### Messages Addressed to You\n")
            for msg in self.messages:
                lines.append(f"- [{msg.message_type}] From **{msg.agent_id}**: {msg.content[:300]}")
            lines.append("")

        return "\n".join(lines)


class ExecutionSnapshot(BaseModel):
    """Record of one agent's execution for the collaboration trail."""

    agent_id: str
    agent_name: str
    step_id: str
    answer: str = ""
    reasoning: str = ""
    confidence: float = 0.0
    tools_used: list[str] = Field(default_factory=list)
    messages_posted: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "step_id": self.step_id,
            "answer": self.answer[:2000],
            "reasoning": self.reasoning[:1000],
            "confidence": self.confidence,
            "tools_used": self.tools_used,
            "messages_posted": self.messages_posted,
        }


class AgentMessage(BaseModel):
    """A structured message from one agent to another (or broadcast).

    Messages flow through ``WorkingMemory`` so every agent can participate
    in the conversation.  Message types:
    - ``analysis_summary`` — what this agent found
    - ``challenge`` — disagreement or gap in prior reasoning
    - ``evidence_request`` — ask another agent for specific data
    - ``evidence_response`` — answer to an evidence request
    - ``critique`` — methodological or evidence critique
    - ``suggestion`` — suggestion for next agent
    """

    agent_id: str
    message_type: str = "analysis_summary"
    content: str
    target_agent_id: str | None = None
    step_id: str | None = None
    confidence: float = 0.0
    timestamp: float = Field(default_factory=time.time)
