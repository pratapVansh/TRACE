import logging
import time
from datetime import datetime, timezone
from typing import Any

from app.agents.framework.tool import ToolResult
from app.agents.framework.tools.context import ToolContext
from app.agents.framework.tools.registry import ToolRegistry
from app.agents.framework.tools.schemas import ToolExecutionRecord
from app.core.observability import metrics, get_tracer, trace_span

logger = logging.getLogger(__name__)


import asyncio

class ToolExecutor:
    """Validates, executes, and records tool invocations with reliability patterns.

    Every tool call goes through this class so that permission
    checking, timing, error handling, retries, circuit breaking,
    and logging are centralised and consistent across all agents.
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry
        self._failure_counts: dict[str, int] = {}
        self._circuit_open_until: dict[str, float] = {}
        self._max_failures = 3
        self._circuit_timeout = 60.0
        self._tool_timeout = 30.0
        self._max_retries = 2

    # ── Public API ─────────────────────────────────────────────

    def _handle_failure(self, tool_id: str) -> None:
        self._failure_counts[tool_id] = self._failure_counts.get(tool_id, 0) + 1
        if self._failure_counts[tool_id] >= self._max_failures:
            self._circuit_open_until[tool_id] = time.time() + self._circuit_timeout
            logger.warning("Circuit breaker OPEN for tool %s", tool_id)

    async def execute(
        self,
        tool_id: str,
        params: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        start = time.perf_counter()
        started_at = datetime.now(timezone.utc)

        # 0. Validate tool_id
        if not tool_id or not isinstance(tool_id, str):
            return self._error_result(
                tool_id=str(tool_id) if tool_id is not None else "",
                tool_name=str(tool_id) if tool_id is not None else "",
                context=context,
                error=f"tool_id must be a non-empty string, got {type(tool_id).__name__}.",
            )

        # 1. Resolve tool
        try:
            tool = self._registry.get_tool(tool_id)
        except KeyError:
            return self._error_result(tool_id, tool_id, context, f"Tool '{tool_id}' not found in registry.")
        except Exception as exc:
            return self._error_result(tool_id, tool_id, context, f"Failed to resolve tool '{tool_id}': {exc}")

        # 2. Circuit Breaker Check
        now_ts = time.time()
        if tool_id in self._circuit_open_until:
            if now_ts < self._circuit_open_until[tool_id]:
                return self._error_result(tool_id, tool.name, context, "Circuit breaker open: tool failed too many times recently.")
            else:
                del self._circuit_open_until[tool_id]
                self._failure_counts[tool_id] = 0
                logger.info("Circuit breaker HALF-OPEN for tool %s", tool_id)

        # 3. Permission check
        result = self._check_permissions(tool.required_permissions, context)
        if result is not None:
            return result

        # 4. Basic parameter validation
        result = self._validate_params(tool.tool_id, params)
        if result is not None:
            return result

        # 5. Execute with Timeout and Retries
        tracer = get_tracer("tool_executor")
        tool_result = None
        last_exc = None

        for attempt in range(1, self._max_retries + 2):
            try:
                with trace_span(tracer, f"tool.{tool.tool_id}.execute", {
                    "tool_id": tool.tool_id,
                    "tool_name": tool.name,
                    "agent_name": context.agent_name or "",
                    "attempt": attempt
                }):
                    tool_result = await asyncio.wait_for(tool.execute(params, context), timeout=self._tool_timeout)
                    
                if tool_result.success:
                    self._failure_counts[tool_id] = 0
                    break
                else:
                    last_exc = Exception(tool_result.error)
            except asyncio.TimeoutError:
                last_exc = Exception("Tool execution timed out.")
            except Exception as exc:
                last_exc = exc

            # Backoff before retry if not the last attempt
            if attempt <= self._max_retries:
                logger.warning("Tool %s failed attempt %d, retrying...", tool_id, attempt)
                await asyncio.sleep(1.0 * attempt)

        elapsed_ms = (time.perf_counter() - start) * 1000
        metrics.record_histogram(f"tool.{tool.tool_id}.time", elapsed_ms / 1000)

        if tool_result is None or not tool_result.success:
            self._handle_failure(tool_id)
            metrics.increment(f"tool.{tool.tool_id}.errors")
            error_msg = f"{type(last_exc).__name__}: {last_exc}" if last_exc else (tool_result.error if tool_result else "Unknown error")
            logger.error("Tool %s failed after %d attempts: %s", tool_id, self._max_retries + 1, error_msg)
            
            return self._record(
                ToolExecutionRecord(
                    tool_id=tool.tool_id,
                    tool_name=tool.name,
                    agent_name=context.agent_name,
                    conversation_id=context.conversation_id,
                    success=False,
                    started_at=started_at,
                    elapsed_ms=elapsed_ms,
                    error=error_msg,
                )
            )

        # 6. Log + return
        return self._record(
            ToolExecutionRecord(
                tool_id=tool.tool_id,
                tool_name=tool.name,
                agent_name=context.agent_name,
                conversation_id=context.conversation_id,
                success=tool_result.success,
                started_at=started_at,
                elapsed_ms=elapsed_ms,
                error=tool_result.error,
                metadata=tool_result.metadata,
            ),
            result=tool_result,
        )

    # ── Permission helpers ────────────────────────────────────

    def _check_permissions(
        self,
        required: set[str],
        context: ToolContext,
    ) -> ToolResult | None:
        """Return an error ``ToolResult`` if permissions are insufficient."""
        if not required:
            return None
        missing = required - context.permissions
        if missing:
            return ToolResult(
                data=None,
                error=(
                    f"Missing required permission(s): "
                    f"{', '.join(sorted(missing))}"
                ),
            )
        return None

    # ── Validation helpers ────────────────────────────────────

    @staticmethod
    def _validate_params(tool_id: str, params: Any) -> ToolResult | None:
        """Return an error ``ToolResult`` if params are invalid."""
        if params is None:
            return ToolResult(
                data=None,
                error=(
                    f"Parameters for tool '{tool_id}' cannot be None."
                ),
            )
        if not isinstance(params, dict):
            return ToolResult(
                data=None,
                error=(
                    f"Parameters for tool '{tool_id}' must be a dict, "
                    f"got {type(params).__name__}."
                ),
            )
        return None

    # ── Recording helpers ─────────────────────────────────────

    @staticmethod
    def _record(
        record: ToolExecutionRecord,
        result: ToolResult | None = None,
    ) -> ToolResult:
        """Log the execution record and return the result."""
        level = "ERROR" if not record.success else "INFO"
        logger.log(
            getattr(logging, level, logging.INFO),
            "Tool %s | agent=%s conv=%s success=%s elapsed=%.1fms%s",
            record.tool_name,
            record.agent_name,
            record.conversation_id,
            record.success,
            record.elapsed_ms,
            f" error={record.error}" if record.error else "",
        )
        if result is not None:
            return result
        return ToolResult(
            data=None,
            error=record.error,
            metadata={"tool_id": record.tool_id},
        )

    @staticmethod
    def _error_result(
        tool_id: str,
        tool_name: str,
        context: ToolContext,
        error: str,
    ) -> ToolResult:
        """Build a failed ``ToolResult`` without an execution attempt."""
        logger.error(
            "Tool %s | agent=%s conv=%s error=%s",
            tool_name,
            context.agent_name,
            context.conversation_id,
            error,
        )
        return ToolResult(
            data=None,
            error=error,
            metadata={"tool_id": tool_id},
        )
