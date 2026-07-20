from abc import ABC, abstractmethod
from typing import Any

from app.agents.framework.tool import ToolResult
from app.agents.framework.tools.context import ToolContext
from app.agents.framework.tools.schemas import ToolCategory, ToolMetadata


class FrameworkTool(ABC):
    """Base class for every tool in the framework.

    Extends the lightweight ``Tool`` contract with metadata,
    permissions, and input/output schema declarations that the
    ``ToolExecutor`` uses for validation, permission checking, and
    introspection.

    Subclasses must define:

    * Class-level ``metadata: ToolMetadata``
    * ``execute(params, context) -> ToolResult``
    """

    metadata: ToolMetadata

    # ── Derived properties (convenience) ───────────────────────

    @property
    def tool_id(self) -> str:
        return self.metadata.tool_id

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def description(self) -> str:
        return self.metadata.description

    @property
    def category(self) -> ToolCategory:
        return self.metadata.category

    @property
    def required_permissions(self) -> set[str]:
        return self.metadata.permissions

    @property
    def input_schema(self) -> dict[str, Any]:
        return self.metadata.input_schema

    @property
    def output_schema(self) -> dict[str, Any]:
        return self.metadata.output_schema

    # ── Execution ──────────────────────────────────────────────

    @abstractmethod
    async def execute(
        self,
        params: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        """Execute the tool's core logic.

        Args:
            params: Tool-specific parameters (already validated
                against ``input_schema`` by the executor).
            context: Shared ``ToolContext`` carrying user identity,
                permissions, working memory, and execution metadata.

        Returns:
            A ``ToolResult`` with the output data or an error.
        """

    # ── Standardized Helpers ────────────────────────────────────

    async def resolve_entity(
        self,
        entity_id: str,
        entity_name: str,
        graph_svc: Any,
        context: ToolContext,
    ) -> tuple[str, str, ToolResult | None]:
        """Standardized entity resolution from Graph Query Service.

        Args:
            entity_id: The requested ID (if any).
            entity_name: The requested name (if any).
            graph_svc: The GraphQueryService instance.
            context: The ToolContext for logging.

        Returns:
            (resolved_id, resolved_name, error_result)
            If error_result is not None, the caller should return it immediately.
        """
        if not entity_id and not entity_name:
            return "", "", ToolResult(data=None, error="Either entity_id or entity_name is required.")
        if graph_svc is None:
            return "", "", ToolResult(data=None, error="Graph query service is not available.")

        resolved_id = entity_id
        resolved_name = ""

        if not resolved_id and entity_name:
            try:
                results, _ = await graph_svc.search_entities(query=entity_name, limit=5)
                if results:
                    resolved_id = results[0].id
                    resolved_name = results[0].name
                else:
                    return "", "", ToolResult(
                        data={"relationships": [], "total": 0} if "relationship" in self.tool_id else None,
                        error=f"No entity found matching '{entity_name}'."
                    )
            except Exception as exc:
                context.add_reasoning_step(f"{self.name}: entity lookup failed — {exc}")
                return "", "", ToolResult(data=None, error=f"Entity lookup failed: {exc}")

        return resolved_id, resolved_name, None

    async def generate_with_llm(
        self,
        prompt: str,
        llm_provider: Any,
        context: ToolContext,
        fallback_value: str = "",
    ) -> str:
        """Standardized LLM generation with exception handling and logging.

        Args:
            prompt: The prompt to send to the LLM.
            llm_provider: The LLMProvider instance.
            context: The ToolContext for logging.
            fallback_value: Value to return on failure or if provider is missing.

        Returns:
            The LLM response or fallback_value on failure.
        """
        if llm_provider is None:
            context.add_reasoning_step(f"{self.name}: LLM provider unavailable, using fallback.")
            return fallback_value

        try:
            result = await llm_provider.generate(prompt=prompt)
            return result.strip() if result else fallback_value
        except Exception as exc:
            context.add_reasoning_step(f"{self.name}: LLM generation failed — {exc}")
            return fallback_value
