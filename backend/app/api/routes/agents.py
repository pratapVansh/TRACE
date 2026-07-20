"""Agent API routes — single and multi-agent execution."""

import json

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.authorization import require_permission
from app.api.deps import (
    get_ai_orchestrator,
    get_current_user,
)
from app.core.authorization import PERMISSIONS
from app.core.logging import logger
from app.agents.framework.exceptions import (
    AgentFrameworkError,
    InvalidContextError,
    OrchestrationError,
)
from app.agents.framework.orchestrator import AIOrchestrator
from app.agents.framework.response import AgentResponse
from app.agents.framework.workflow.schemas import (
    MultiAgentRequest,
    MultiAgentResponse,
)
from app.schemas.auth import UserMeResponse

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentExecuteRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None
    agent_id: str | None = None


@router.post("/execute", response_model=AgentResponse)
async def execute_agent(
    request: AgentExecuteRequest,
    current_user: UserMeResponse = Depends(
        require_permission(PERMISSIONS.AI_AGENTS),
    ),
    orchestrator: AIOrchestrator = Depends(get_ai_orchestrator),
) -> AgentResponse:
    """Execute a single agent to answer a question.

    When ``agent_id`` is omitted the orchestrator selects the best
    agent automatically.  When ``conversation_id`` is provided the
    conversation history is loaded from the existing Conversation
    system and injected into the agent context.
    """
    import asyncio
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
    from app.core.telemetry import trace_span, metrics
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=5),
        retry=retry_if_exception_type((AgentFrameworkError, TimeoutError)),
        reraise=True
    )
    async def _run_with_retry():
        return await asyncio.wait_for(
            orchestrator.execute(
                question=request.question,
                user_id=str(current_user.id),
                user_role=current_user.role,
                conversation_id=request.conversation_id,
                agent_id=request.agent_id,
            ),
            timeout=60.0
        )
        
    try:
        with trace_span("execute_single_agent", {"agent_id": request.agent_id}):
            result = await _run_with_retry()
            metrics.record_metric("agent_confidence", result.confidence, {"agent_id": result.agent_name})
            return result
    except (asyncio.TimeoutError, TimeoutError):
        logger.warning("Agent execution timed out.")
        metrics.record_event("agent_timeout", {"agent_id": request.agent_id})
        return AgentResponse(
            answer="The request timed out. Please try again with a narrower scope.",
            confidence=0.0,
            confidence_explanation="Execution timeout.",
            agent_name="System",
        )
    except asyncio.CancelledError:
        logger.warning("Agent execution was cancelled.")
        metrics.record_event("agent_cancelled", {"agent_id": request.agent_id})
        return AgentResponse(
            answer="The request was cancelled.",
            confidence=0.0,
            confidence_explanation="Execution cancelled.",
            agent_name="System",
        )
    except InvalidContextError as exc:
        logger.warning("Invalid context: %s", exc)
        metrics.record_event("agent_invalid_context", {"error": str(exc)})
        return AgentResponse(
            answer=f"Invalid context provided: {exc}",
            confidence=0.0,
            confidence_explanation="Missing or invalid required context.",
            agent_name="System",
        )
    except Exception as exc:
        logger.exception("Agent execution failed")
        metrics.record_event("agent_exception", {"error": str(exc), "agent_id": request.agent_id})
        return AgentResponse(
            answer="The system encountered an error while processing your request. Please verify the asset exists and try again.",
            confidence=0.0,
            confidence_explanation=f"System error: {str(exc)}",
            agent_name="System",
            reasoning=str(exc)
        )


@router.post("/execute-multi", response_model=MultiAgentResponse)
async def execute_multi_agent(
    request: MultiAgentRequest,
    current_user: UserMeResponse = Depends(
        require_permission(PERMISSIONS.AI_AGENTS),
    ),
    orchestrator: AIOrchestrator = Depends(get_ai_orchestrator),
) -> MultiAgentResponse:
    """Execute a multi-agent workflow.

    Automatically routes the question to the appropriate agent(s),
    supports chaining, parallel execution, and fallback.  Shared
    memory is passed between agents for context continuity.

    Request fields:
    - ``question`` — the user's question (required)
    - ``conversation_id`` — optional conversation for history
    - ``agent_ids`` — explicit list of agents (skips auto-routing)
    - ``mode`` — ``"auto"`` | ``"single"`` | ``"sequential"`` | ``"parallel"``

    Returns a ``MultiAgentResponse`` with combined answer, citations,
    confidence, execution timeline, and tools used.
    """
    import asyncio
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
    from app.core.telemetry import trace_span, metrics
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=5),
        retry=retry_if_exception_type((AgentFrameworkError, TimeoutError)),
        reraise=True
    )
    async def _run_multi_with_retry():
        return await asyncio.wait_for(
            orchestrator.execute_multi(
                question=request.question,
                user_id=str(current_user.id),
                user_role=current_user.role,
                conversation_id=request.conversation_id,
                agent_ids=request.agent_ids,
                mode=request.mode,
            ),
            timeout=120.0  # Multi-agent might take longer
        )
        
    try:
        with trace_span("execute_multi_agent", {"mode": request.mode}):
            result = await _run_multi_with_retry()
            metrics.record_metric("multi_agent_confidence", result.confidence, {"mode": request.mode})

            # Save the conversation turn to the database
            from app.api.deps import get_db
            from app.repositories.conversation_repository import ConversationRepository
            async for session in get_db():
                repo = ConversationRepository(session)
                conv_id = result.conversation_id or request.conversation_id
                
                import uuid
                if not conv_id:
                    conv = await repo.create_conversation(
                        user_id=uuid.UUID(str(current_user.id)), 
                        title=request.question[:50]
                    )
                    conv_id = str(conv.id)
                    result.conversation_id = conv_id
                    
                cid = uuid.UUID(conv_id)
                await repo.add_message(
                    conversation_id=cid,
                    role="user",
                    content=request.question,
                )
                await repo.add_message(
                    conversation_id=cid,
                    role="assistant",
                    content=result.answer,
                    citations=result.citations if result.citations else None,
                    tool_outputs=None, # or agent results timeline
                )
                await session.commit()
                break

            return result
    except (asyncio.TimeoutError, TimeoutError):
        logger.warning("Multi-agent execution timed out.")
        metrics.record_event("multi_agent_timeout", {"mode": request.mode})
        return MultiAgentResponse(
            answer="The multi-agent workflow timed out. Please try again with a narrower scope.",
            confidence=0.0,
            confidence_explanation="Execution timeout.",
        )
    except asyncio.CancelledError:
        logger.warning("Multi-agent execution was cancelled.")
        metrics.record_event("multi_agent_cancelled", {"mode": request.mode})
        return MultiAgentResponse(
            answer="The multi-agent workflow was cancelled.",
            confidence=0.0,
            confidence_explanation="Execution cancelled.",
        )
    except InvalidContextError as exc:
        logger.warning("Invalid context for multi-agent: %s", exc)
        metrics.record_event("multi_agent_invalid_context", {"error": str(exc)})
        return MultiAgentResponse(
            answer=f"Invalid context provided: {exc}",
            confidence=0.0,
            confidence_explanation="Missing or invalid required context.",
        )
    except Exception as exc:
        logger.exception("Multi-agent execution failed")
        metrics.record_event("multi_agent_exception", {"error": str(exc)})
        return MultiAgentResponse(
            answer="The system encountered an error while processing your multi-agent workflow. Please try again.",
            confidence=0.0,
            confidence_explanation=f"System error: {str(exc)}",
            reasoning=str(exc)
        )


@router.post("/stream-multi")
async def stream_multi_agent(
    request: MultiAgentRequest,
    current_user: UserMeResponse = Depends(
        require_permission(PERMISSIONS.AI_AGENTS),
    ),
    orchestrator: AIOrchestrator = Depends(get_ai_orchestrator),
) -> StreamingResponse:
    """Stream a multi-agent workflow via SSE.

    Each completed agent emits an ``agent_progress`` event.
    A final ``done`` event carries the complete ``MultiAgentResponse``.
    """

    async def event_stream():
        try:
            async for event in orchestrator.stream_multi(
                question=request.question,
                user_id=str(current_user.id),
                user_role=current_user.role,
                conversation_id=request.conversation_id,
                agent_ids=request.agent_ids,
                mode=request.mode,
            ):
                yield event
        except Exception:
            logger.exception("Multi-agent stream error")
            yield f"event: error\ndata: {json.dumps({'message': 'Internal server error'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
