"""Agent collaboration layer — inter-agent communication and result synthesis.

Provides a shared message bus (backed by ``WorkingMemory``) so agents can:
- read previous agents' analysis and reasoning
- challenge or critique earlier findings
- request additional evidence from specific agents
- exchange structured messages during execution

After the execution DAG completes, a ``SynthesisAgent`` produces a single
coherent answer instead of concatenating individual agent outputs.
"""

from app.agents.framework.collaboration.schemas import (
    AgentMessage,
    CollaborationContext,
    ExecutionSnapshot,
)
from app.agents.framework.collaboration.synth_agent import SynthesisAgent

__all__ = [
    "AgentMessage",
    "CollaborationContext",
    "SynthesisAgent",
]
