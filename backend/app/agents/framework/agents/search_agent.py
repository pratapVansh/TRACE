"""Search Agent for general purpose search capabilities."""

from typing import Any

from app.ai.base import LLMProvider
from app.agents.framework.base import BaseAgent
from app.agents.framework.context import AgentContext
from app.agents.framework.response import AgentResponse
from app.agents.framework.tools.context import ToolContext
from app.agents.framework.tools.executor import ToolExecutor
from app.agents.framework.agents.no_evidence import annotate_answer
from app.core.authorization import Permission
from app.core.authorization.permissions import get_permissions_for_role


_SEARCH_TASKS = [
    "search",
    "find",
    "look up",
    "query",
    "retrieve"
]


class SearchAgent(BaseAgent):
    """General purpose semantic and hybrid search agent."""

    agent_id = "search_agent"
    name = "Search Agent"
    description = "General purpose semantic and hybrid search agent."
    supported_tasks = _SEARCH_TASKS
    required_permissions: set[Permission] = {Permission.SEARCH}

    def __init__(
        self,
        tool_executor: ToolExecutor | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self._tool_executor = tool_executor
        self._llm = llm_provider

    async def execute(self, context: AgentContext) -> AgentResponse:
        question = context.question
        tools_used: list[str] = []
        confidence = 0.0
        
        user_permissions = get_permissions_for_role(context.user_role)
        perm_strings = {p.value for p in user_permissions}

        tool_ctx = ToolContext.from_agent_context(
            context,
            agent_name=self.name,
            execution_id="srch-tmp",
            user_permissions=perm_strings,
        )

        if not self._tool_executor or not self._llm:
            return AgentResponse(
                answer="Missing dependencies for search processing.",
                confidence=0.0,
                confidence_explanation="Missing tools or LLM",
                agent_name=self.name
            )

        tool_res = await self._tool_executor.execute(
            "document_search", 
            {"query": question, "limit": 5, "search_type": "hybrid"}, 
            tool_ctx
        )
        tools_used.append("document_search")
        
        prompt = (
            f"User Question: {question}\n\n"
            f"Search Results:\n{tool_res.data}\n\n"
            "Formulate an appropriate response answering the question based on the search results."
        )

        try:
            answer = await self._llm.generate(
                prompt=prompt, 
                system_prompt=(
                    "You are the Search Agent. You ONLY report information present in the search results. "
                    "Never invent facts, figures, or details. "
                    "If the search results contain no relevant information, state: 'No supporting evidence found.'"
                )
            )
            confidence = 0.9 if not tool_res.error else 0.2
        except Exception as e:
            answer = f"Error generating search analysis: {e}"
        
        _expl = "Processed search results"
        return AgentResponse(
            confidence_explanation=_expl,
            answer=annotate_answer(answer, tools_used=tools_used, confidence=confidence, confidence_explanation=_expl),
            confidence=confidence,
            tools_used=tools_used,
            agent_name=self.name,
        )
