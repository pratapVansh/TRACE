"""Maintenance tools for the MaintenanceAgent.

All tools reuse existing services (HybridRetriever, GraphQueryService, LLMProvider)
and follow the same patterns as document_tools.py / graph_tools.py.
"""

from typing import Any

from app.agents.framework.tool import ToolResult
from app.agents.framework.tools.base import FrameworkTool
from app.agents.framework.tools.context import ToolContext
from app.agents.framework.tools.schemas import ToolCategory, ToolMetadata
from app.agents.framework.tools.search_helper import search_hybrid


class MaintenanceSearchTool(FrameworkTool):
    """Searches maintenance documentation and graph entities for equipment data."""

    metadata = ToolMetadata(
        tool_id="maintenance_search",
        name="Maintenance Search",
        description=(
            "Searches maintenance procedures, manuals, SOPs, and graph entities "
            "for equipment-specific information. Supports source filtering."
        ),
        category=ToolCategory.SEARCH,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Maintenance-related search query"},
                "top_k": {"type": "integer", "description": "Max results (default 10)"},
                "source": {
                    "type": "string",
                    "enum": ["all", "documents", "graph"],
                    "description": "Where to search (default all)",
                },
            },
            "required": ["query"],
        },
    )

    def __init__(
        self,
        hybrid_retriever: Any = None,
        graph_query_service: Any = None,
    ) -> None:
        self._hybrid = hybrid_retriever
        self._graph_svc = graph_query_service

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        query = params.get("query", "")
        top_k = min(params.get("top_k", 10), 50)
        source = params.get("source", "all")

        if not query.strip():
            return ToolResult(data=None, error="Search query cannot be empty.")

        sr = await search_hybrid(
            query=query,
            graph_svc=self._graph_svc,
            hybrid=self._hybrid,
            top_k=top_k,
            source=source,
            tool_name="MaintenanceSearchTool",
            context=context,
            cache=context.retrieval_cache,
            graph_item_fn=lambda e: {
                "id": e.id, "name": e.name, "type": e.type,
                "confidence": e.confidence, "aliases": e.aliases,
                "source_document": e.source_document,
            },
            doc_item_fn=lambda item: {
                "content": item.content[:2000], "score": item.score,
                "document_name": item.document_name, "document_id": item.document_id,
                "page_number": item.page_number, "source": item.source,
            },
        )

        if not sr.documents and not sr.entities:
            return ToolResult(
                data={"documents": [], "entities": [], "total_documents": 0, "total_entities": 0},
                error="No results found from any source.",
            )

        return ToolResult(
            data={
                "documents": sr.documents,
                "entities": sr.entities,
                "total_documents": sr.total_documents,
                "total_entities": sr.total_entities,
            },
            metadata={"doc_count": sr.total_documents, "entity_count": sr.total_entities},
        )


class MaintenanceRecommendationTool(FrameworkTool):
    """Recommends spare parts, tools, and PPE for maintenance tasks."""

    metadata = ToolMetadata(
        tool_id="maintenance_recommendation",
        name="Maintenance Recommendation",
        description=(
            "Recommends spare parts, required tools, and PPE "
            "for a specific equipment or maintenance task."
        ),
        category=ToolCategory.DOCUMENT,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "equipment_name": {"type": "string", "description": "Name of the equipment"},
                "maintenance_type": {
                    "type": "string",
                    "enum": ["preventive", "corrective", "inspection", "shutdown", "startup"],
                    "description": "Type of maintenance",
                },
                "issue_description": {"type": "string", "description": "Optional issue or symptom description"},
            },
            "required": ["equipment_name"],
        },
    )

    def __init__(self, llm_provider: Any = None) -> None:
        self._llm = llm_provider

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        equipment = params.get("equipment_name", "")
        maint_type = params.get("maintenance_type", "preventive")
        issue = params.get("issue_description", "")

        if not equipment.strip():
            return ToolResult(data=None, error="equipment_name is required.")

        prompt = (
            f"You are a maintenance engineer. For the equipment '{equipment}' "
            f"requiring '{maint_type}' maintenance"
        )
        if issue:
            prompt += f" (issue: {issue})"
        prompt += (
            ", provide a structured recommendation grounded ONLY in the available evidence.\n"
            "STRICT RULES:\n"
            "- Never invent part numbers, maintenance history, labor hours, or schedules.\n"
            "- Only reference information present in the retrieved context.\n"
            "- If evidence is missing, state: 'No supporting evidence found.'\n"
            "Format as a structured list with:\n"
            "1. Known maintenance requirements\n"
            "2. Required tools and PPE (only if evidenced)\n"
            "3. Reference documents"
        )

        if self._llm is not None:
            try:
                result = await self._llm.generate(prompt=prompt)
                recommendation_text = result if isinstance(result, str) else (result.get("text", "") if isinstance(result, dict) else str(result))
            except Exception as exc:
                return ToolResult(
                    data=self._fallback_recommendation(equipment, maint_type, issue),
                    error=f"LLM unavailable, using template: {exc}",
                )
        else:
            recommendation_text = self._fallback_recommendation(equipment, maint_type, issue)

        context.add_reasoning_step(
            f"MaintenanceRecommendationTool: recommendation for {equipment} ({maint_type})"
        )

        return ToolResult(
            data={
                "equipment": equipment,
                "maintenance_type": maint_type,
                "recommendation": recommendation_text,
            },
        )

    @staticmethod
    def _fallback_recommendation(equipment: str, maint_type: str, issue: str) -> str:
        return (
            f"**{equipment}** — {maint_type.title()} Maintenance\n\n"
            "**Spare Parts:**\n"
            f"- Standard seal kit for {equipment}\n"
            "- Gaskets and O-rings (verify sizes)\n"
            "- Lubricant (specified grade)\n\n"
            "**Required Tools:**\n"
            "- Standard tool kit (wrenches, screwdrivers)\n"
            "- Torque wrench\n"
            "- Measuring instruments\n\n"
            "**Required PPE:**\n"
            "- Safety glasses\n"
            "- Work gloves\n"
            "- Safety shoes\n"
            "- (If applicable) Hearing protection\n\n"
            "**Estimated Labor:** 2–4 hours\n"
            "> *Note: This is a template recommendation. Consult the equipment manual for exact specifications.*"
        )


class MaintenanceHistoryTool(FrameworkTool):
    """Retrieves maintenance history for equipment from the knowledge graph."""

    metadata = ToolMetadata(
        tool_id="maintenance_history",
        name="Maintenance History",
        description="Retrieves past maintenance records and events for a specific equipment or entity.",
        category=ToolCategory.KNOWLEDGE_GRAPH,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "equipment_id": {"type": "string", "description": "Entity ID of the equipment"},
                "equipment_name": {"type": "string", "description": "Name to search if ID is unknown"},
                "limit": {"type": "integer", "description": "Max history records (default 10)"},
            },
        },
    )

    def __init__(self, graph_query_service: Any = None) -> None:
        self._graph_svc = graph_query_service

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        equipment_id = params.get("equipment_id", "")
        equipment_name = params.get("equipment_name", "")
        limit = min(params.get("limit", 10), 50)

        if not equipment_id and not equipment_name:
            return ToolResult(data=None, error="Either equipment_id or equipment_name is required.")

        if self._graph_svc is None:
            return ToolResult(data=None, error="Graph query service is not available.")

        resolved_id = equipment_id
        resolved_name = ""

        # Resolve name → ID if needed
        if not resolved_id and equipment_name:
            try:
                results, _ = await self._graph_svc.search_entities(
                    query=equipment_name, limit=5,
                )
                if results:
                    resolved_id = results[0].id
                    resolved_name = results[0].name
                else:
                    return ToolResult(
                        data={"history": [], "total": 0},
                        error=f"No entity found matching '{equipment_name}'.",
                    )
            except Exception as exc:
                return ToolResult(data=None, error=f"Entity lookup failed: {exc}")

        # Get neighbors to find maintenance-related connections
        try:
            entity, neighbors, total = await self._graph_svc.get_neighbors(
                entity_id=resolved_id,
                depth=2,
                limit=limit,
            )
        except Exception as exc:
            return ToolResult(data=None, error=f"Failed to retrieve history: {exc}")

        if entity is None:
            return ToolResult(data=None, error=f"Entity '{resolved_id}' not found.")

        # Filter for maintenance-relevant relationships
        maintenance_keywords = [
            "maintenance", "inspection", "repair", "replacement",
            "overhaul", "service", "check", "test", "calibrate",
        ]
        history: list[dict] = []
        for n in neighbors:
            rel = n.relationship
            rel_lower = rel.type.lower()
            if any(kw in rel_lower for kw in maintenance_keywords) or any(
                kw in n.entity.name.lower() for kw in maintenance_keywords
            ):
                history.append({
                    "entity_name": n.entity.name,
                    "entity_type": n.entity.type,
                    "relationship": rel.type,
                    "relationship_source": rel.source,
                    "relationship_target": rel.target,
                    "confidence": n.entity.confidence,
                    "source_document": n.entity.source_document,
                    "depth": n.depth,
                })

        name = entity.name or resolved_name or resolved_id
        context.add_reasoning_step(
            f"MaintenanceHistoryTool: {len(history)} record(s) for {name}"
        )

        return ToolResult(
            data={
                "equipment_id": resolved_id,
                "equipment_name": name,
                "history": history,
                "total": len(history),
            },
            metadata={"history_count": len(history), "neighbor_count": total},
        )


class MaintenanceChecklistTool(FrameworkTool):
    """Generates a structured checklist for a maintenance procedure."""

    metadata = ToolMetadata(
        tool_id="maintenance_checklist",
        name="Maintenance Checklist",
        description=(
            "Generates a step-by-step checklist for preventive, corrective, "
            "inspection, shutdown, or startup procedures."
        ),
        category=ToolCategory.DOCUMENT,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "procedure_type": {
                    "type": "string",
                    "enum": ["preventive", "corrective", "inspection", "shutdown", "startup"],
                    "description": "Type of maintenance procedure",
                },
                "equipment_name": {"type": "string", "description": "Target equipment"},
                "context": {"type": "string", "description": "Optional additional context"},
            },
            "required": ["procedure_type", "equipment_name"],
        },
    )

    def __init__(self, llm_provider: Any = None, hybrid_retriever: Any = None) -> None:
        self._llm = llm_provider
        self._hybrid = hybrid_retriever

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        proc_type = params.get("procedure_type", "preventive")
        equipment = params.get("equipment_name", "")
        extra_context = params.get("context", "")

        if not equipment.strip():
            return ToolResult(data=None, error="equipment_name is required.")

        # Attempt document retrieval for grounding
        grounding_docs: list[str] = []
        if self._hybrid is not None:
            try:
                search_query = f"{proc_type} maintenance {equipment} procedure checklist"
                unified = await self._hybrid.retrieve(query=search_query, top_k=5)
                grounding_docs = [
                    f"[{item.document_name}] {item.content[:500]}"
                    for item in unified.items
                ]
            except Exception:
                pass

        prompt = (
            f"Generate a maintenance checklist for {proc_type} on {equipment} grounded ONLY in the evidence below.\n"
        )
        if extra_context:
            prompt += f"Context: {extra_context}\n"
        if grounding_docs:
            prompt += f"\nGrounding references:\n" + "\n".join(grounding_docs[:3])
        prompt += (
            "\n\nSTRICT RULES:\n"
            "- Never invent steps, procedures, or schedules not present in the grounding references.\n"
            "- If no evidence exists for a section, write: 'No supporting evidence found.'\n"
            "- Only include sections where evidence exists.\n"
            "Format as:\n"
            "## {Procedure Type} Checklist — {Equipment}\n"
            "### Preparation\n1. ...\n"
            "### Steps\n1. ...\n"
            "### Completion\n1. ...\n"
            "### Safety Notes\n- ...\n"
            "### Required PPE\n- ..."
        )

        checklist_text = ""

        if self._llm is not None:
            try:
                result = await self._llm.generate(prompt=prompt)
                checklist_text = result if isinstance(result, str) else (result.get("text", "") if isinstance(result, dict) else str(result))
            except Exception as exc:
                checklist_text = self._fallback_checklist(proc_type, equipment, extra_context)
                context.add_reasoning_step(f"MaintenanceChecklistTool: LLM unavailable — {exc}")
        else:
            checklist_text = self._fallback_checklist(proc_type, equipment, extra_context)

        context.add_reasoning_step(
            f"MaintenanceChecklistTool: {proc_type} checklist for {equipment}"
        )

        return ToolResult(
            data={
                "procedure_type": proc_type,
                "equipment": equipment,
                "checklist": checklist_text,
                "grounding_documents": len(grounding_docs),
            },
        )

    @staticmethod
    def _fallback_checklist(proc_type: str, equipment: str, extra: str) -> str:
        P = proc_type.title()
        lines = [
            f"## {P} Checklist — {equipment}",
            "",
            "### Preparation",
            "1. Review equipment manual and maintenance history",
            "2. Gather required tools and spare parts",
            "3. Ensure work area is clean and well-lit",
            "4. Verify lockout/tagout (LOTO) is in place",
            "5. Don required PPE",
            "",
            "### Steps",
            "1. Isolate equipment from power sources",
            "2. Release stored energy (pneumatic, hydraulic, spring)",
            "3. Perform visual inspection for damage, leaks, wear",
            "4. " + (
                "Replace worn components per schedule" if proc_type == "preventive" else
                "Diagnose root cause and replace faulty components" if proc_type == "corrective" else
                "Measure tolerances and record readings" if proc_type == "inspection" else
                "Follow controlled shutdown sequence per SOP" if proc_type == "shutdown" else
                "Follow controlled startup sequence per SOP"
            ),
            "5. Clean and lubricate as required",
            "6. Reassemble and verify all fasteners are torqued",
            "",
            "### Completion",
            "1. Remove LOTO and verify equipment is safe to operate",
            "2. Perform functional test",
            "3. Record work details in maintenance log",
            "4. Tag equipment with maintenance status",
            "5. Report any unresolved issues",
            "",
            "### Safety Notes",
            "- Always follow LOTO procedures",
            "- Verify zero energy state before working",
            "- Use appropriate lifting techniques for heavy components",
            "- Check MSDS for any chemicals used",
            "",
            "### Required PPE",
            "- Safety glasses",
            "- Work gloves",
            "- Safety shoes",
            "- Hard hat (if required)",
        ]
        if extra:
            lines.extend(["", f"### Additional Context", extra])
        return "\n".join(lines)


class MaintenanceRiskAssessmentTool(FrameworkTool):
    """Assesses risks for a maintenance task and suggests mitigations."""

    metadata = ToolMetadata(
        tool_id="maintenance_risk_assessment",
        name="Maintenance Risk Assessment",
        description=(
            "Evaluates risks for a maintenance task, provides severity/likelihood "
            "ratings, and recommends mitigations."
        ),
        category=ToolCategory.REPORTING,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "equipment_name": {"type": "string", "description": "Equipment being maintained"},
                "task_description": {"type": "string", "description": "Description of the maintenance task"},
                "environment_factors": {
                    "type": "string",
                    "description": "Environmental factors (height, confined space, electrical, etc.)",
                },
            },
            "required": ["equipment_name", "task_description"],
        },
    )

    def __init__(self, llm_provider: Any = None) -> None:
        self._llm = llm_provider

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        equipment = params.get("equipment_name", "")
        task = params.get("task_description", "")
        env = params.get("environment_factors", "")

        if not equipment.strip() or not task.strip():
            return ToolResult(data=None, error="Both equipment_name and task_description are required.")

        prompt = (
            f"Perform a risk assessment for the following maintenance task:\n"
            f"Equipment: {equipment}\n"
            f"Task: {task}\n"
        )
        if env:
            prompt += f"Environmental factors: {env}\n"
        prompt += (
            "STRICT RULES:\n"
            "- Never invent hazards, controls, or procedures not grounded in evidence.\n"
            "- Only rate risks that are directly supported by the task description or evidence.\n"
            "- If evidence is missing, state: 'No supporting evidence found.'\n"
            "Provide based on available evidence:\n"
            "1. Hazard identification\n"
            "2. Risk rating\n"
            "3. Recommended control measures\n"
            "Format as a structured risk assessment."
        )

        assessment_text = ""

        if self._llm is not None:
            try:
                result = await self._llm.generate(prompt=prompt)
                assessment_text = result if isinstance(result, str) else (result.get("text", "") if isinstance(result, dict) else str(result))
            except Exception as exc:
                assessment_text = self._fallback_assessment(equipment, task, env)
                context.add_reasoning_step(f"MaintenanceRiskAssessmentTool: LLM unavailable — {exc}")
        else:
            assessment_text = self._fallback_assessment(equipment, task, env)

        context.add_reasoning_step(
            f"MaintenanceRiskAssessmentTool: assessment for {equipment}"
        )

        return ToolResult(
            data={
                "equipment": equipment,
                "task_description": task,
                "assessment": assessment_text,
            },
        )

    @staticmethod
    def _fallback_assessment(equipment: str, task: str, env: str) -> str:
        lines = [
            f"## Risk Assessment — {equipment}",
            "",
            f"**Task:** {task}",
            "",
            "### Hazard Identification",
            "- Mechanical energy (moving parts, stored energy)",
            "- Electrical shock (if equipment is powered)",
            "- Chemical exposure (lubricants, cleaning agents)",
            "- Ergonomic strain (awkward positions, heavy lifting)",
            "",
            "### Risk Rating",
            "| Hazard | Severity (1–5) | Likelihood (1–5) | Overall |",
            "|--------|---------------|-----------------|---------|",
            "| Mechanical | 4 | 3 | High |",
            "| Electrical | 5 | 2 | Medium |",
            "| Chemical | 3 | 2 | Low |",
            "| Ergonomic | 2 | 3 | Low |",
            "",
            "### Control Measures",
            "1. Implement lockout/tagout (LOTO) before starting",
            "2. Verify zero energy state with a qualified technician",
            "3. Use appropriate ventilation if chemicals are present",
            "4. Use mechanical handling aids for heavy components",
            "",
            "### Required PPE",
            "- Safety glasses with side shields",
            "- Cut-resistant gloves",
            "- Safety shoes with steel toe",
            "- (If applicable) Arc flash PPE, respirator, fall protection",
            "",
            "### Emergency Procedures",
            "- First aid kit must be accessible",
            "- Emergency stop locations identified",
            "- Communication device available for emergency calls",
            "- Nearest fire extinguisher identified",
        ]
        if env:
            lines.extend(["", "### Environmental Factors", env])
        return "\n".join(lines)
