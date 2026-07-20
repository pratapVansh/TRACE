from pydantic import BaseModel, Field

from app.agents.framework.response import AgentResponse
from app.schemas.rag import Citation, GraphCitation


class TimelineEntry(BaseModel):
    """One entry in the multi-agent execution timeline."""

    agent_id: str
    agent_name: str
    start_time: float
    end_time: float
    duration: float = 0.0
    confidence: float = 0.0
    tools_used: list[str] = Field(default_factory=list)
    status: str = "success"


class MultiAgentRequest(BaseModel):
    """Request model for multi-agent execution."""

    question: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None
    agent_ids: list[str] | None = None
    mode: str = "auto"


class MultiAgentResponse(BaseModel):
    """Combined response from one or more agents.

    Fields:
    - ``answer`` — the final merged or best answer
    - ``agent_results`` — individual ``AgentResponse`` from each agent
    - ``citations`` / ``graph_citations`` — deduplicated across agents
    - ``confidence`` — aggregated confidence across all agent results
    - ``execution_time`` — total wall-clock time
    - ``execution_order`` — ordered list of agent ids that ran
    - ``timeline`` — per-agent timing and metadata
    - ``all_tools_used`` — union of tools invoked across all agents
    - ``parallel_groups`` — which agents ran in parallel (if any)
    """

    answer: str = ""
    agent_results: list[AgentResponse] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    graph_citations: list[GraphCitation] = Field(default_factory=list)
    confidence: float = 0.0
    confidence_explanation: str = ""
    reasoning: str = ""
    execution_time: float = 0.0
    execution_order: list[str] = Field(default_factory=list)
    timeline: list[TimelineEntry] = Field(default_factory=list)
    all_tools_used: list[str] = Field(default_factory=list)
    parallel_groups: list[list[str]] | None = None
    conversation_id: str | None = None
