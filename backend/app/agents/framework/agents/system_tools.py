"""System tools for the framework agents."""
import uuid
from typing import Any

from app.agents.framework.tool import ToolResult
from app.agents.framework.tools.base import FrameworkTool
from app.agents.framework.tools.context import ToolContext
from app.agents.framework.tools.schemas import ToolCategory, ToolMetadata
from app.core.authorization import Permission


class DashboardTool(FrameworkTool):
    """Retrieves system dashboard statistics."""

    metadata = ToolMetadata(
        tool_id="dashboard_stats",
        name="System Dashboard Statistics",
        description="Get system dashboard statistics, including document counts and chunk counts.",
        category=ToolCategory.SYSTEM,
        permissions={Permission.DASHBOARD},
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    )

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        agent_ctx = context._agent_context
        if not agent_ctx or not agent_ctx.session:
            return ToolResult(data=None, error="Database session not available.")
            
        graph_store = agent_ctx.metadata.get("graph_store")
        
        from app.services.dashboard_service import DashboardService
        service = DashboardService(session=agent_ctx.session, graph_store=graph_store)
        data = await service.get_dashboard()
        
        context.add_reasoning_step("DashboardTool: retrieved dashboard stats")
        return ToolResult(data=data.model_dump())


class ConversationHistoryTool(FrameworkTool):
    """Retrieves conversation history."""

    metadata = ToolMetadata(
        tool_id="conversation_history",
        name="Conversation History",
        description="Retrieve the history of a specific conversation.",
        category=ToolCategory.SYSTEM,
        permissions={Permission.COPILOT},
        input_schema={
            "type": "object",
            "properties": {
                "conversation_id": {"type": "string", "description": "The UUID of the conversation."},
                "limit": {"type": "integer", "description": "Number of recent messages to return. Default 20."}
            },
            "required": ["conversation_id"],
        },
    )

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        conversation_id = params["conversation_id"]
        limit = params.get("limit", 20)
        
        agent_ctx = context._agent_context
        if not agent_ctx or not agent_ctx.session:
            return ToolResult(data=None, error="Database session not available.")
            
        from app.repositories.conversation_repository import ConversationRepository
        repo = ConversationRepository(agent_ctx.session)
        try:
            cid = uuid.UUID(conversation_id)
        except (ValueError, AttributeError):
            return ToolResult(data=None, error=f"Invalid conversation_id: {conversation_id}")
            
        conversation = await repo.get_conversation(cid)
        if not conversation:
            return ToolResult(data=None, error="Conversation not found.")
            
        messages = await repo.get_messages(cid)
        context.add_reasoning_step(f"ConversationHistoryTool: retrieved {len(messages[-limit:])} messages")
        return ToolResult(
            data={
                "conversation": {
                    "id": str(conversation.id),
                    "title": conversation.title,
                },
                "messages": [
                    {
                        "id": str(m.id),
                        "role": m.role,
                        "content": m.content,
                        "created_at": m.created_at.isoformat(),
                    }
                    for m in messages[-limit:]
                ],
            }
        )
