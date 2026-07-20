"""Conversation Agent for analyzing conversation history."""

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


_CONVERSATION_TASKS = [
    "conversation",
    "history",
    "chat history",
    "summarize chat",
    "previous messages"
]


class ConversationAgent(BaseAgent):
    """Analyzes conversation history and meta-chat."""

    agent_id = "conversation_agent"
    name = "Conversation Agent"
    description = "Analyzes conversation history and meta-chat."
    supported_tasks = _CONVERSATION_TASKS
    required_permissions: set[Permission] = {Permission.COPILOT}

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
            execution_id="conv-" + (context.conversation_id or "tmp"),
            user_permissions=perm_strings,
        )

        if not self._tool_executor or not self._llm:
            return AgentResponse(
                answer="Missing dependencies for conversation processing.",
                confidence=0.0,
                confidence_explanation="Missing tools or LLM",
                agent_name=self.name
            )

        # Let's fetch history using the tool
        if context.conversation_id:
            tool_res = await self._tool_executor.execute("conversation_history", {"conversation_id": context.conversation_id, "limit": 10}, tool_ctx)
            tools_used.append("conversation_history")
            
            prompt = (
                f"User Question: {question}\n\n"
                f"Conversation History:\n{tool_res.data}\n\n"
                "Formulate an appropriate response analyzing or summarizing the chat history."
            )
        else:
            prompt = (
                f"User Question: {question}\n\n"
                "There is no active conversation context."
            )

        try:
            answer = await self._llm.generate(
                prompt=prompt, 
                system_prompt=(
                    "You are the Conversation Agent. You ONLY summarize or retrieve information "
                    "present in the chat history. Never invent details about past conversations. "
                    "If the history contains no relevant information, state: 'No supporting evidence found.'"
                )
            )
            confidence = 1.0
        except Exception as e:
            answer = f"Error generating conversation analysis: {e}"
        
        _expl = "Processed conversation history"
        return AgentResponse(
            confidence_explanation=_expl,
            answer=annotate_answer(answer, tools_used=tools_used, confidence=confidence, confidence_explanation=_expl),
            confidence=confidence,
            tools_used=tools_used,
            agent_name=self.name,
        )
