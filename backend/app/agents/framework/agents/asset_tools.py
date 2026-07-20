"""Asset-intelligence tools for the AssetIntelligenceAgent.

Reuses GraphQueryService, HybridRetriever, DocumentService, and LLMProvider.
Follows the same patterns as maintenance_tools.py / compliance_tools.py.
"""

from typing import Any

from app.agents.framework.tool import ToolResult
from app.agents.framework.tools.base import FrameworkTool
from app.agents.framework.tools.context import ToolContext
from app.agents.framework.tools.schemas import ToolCategory, ToolMetadata
from app.agents.framework.tools.search_helper import search_hybrid

_ASSET_TYPES = [
    "pump", "valve", "motor", "tank", "pipe", "compressor",
    "conveyor", "fan", "filter", "heat exchanger", "boiler",
    "generator", "turbine", "separator", "instrument",
    "controller", "actuator", "sensor", "transmitter",
    "vessel", "column", "reactor", "furnace", "cooler",
]


class AssetSearchTool(FrameworkTool):
    """Searches for assets in the knowledge graph and documents."""

    metadata = ToolMetadata(
        tool_id="asset_search",
        name="Asset Search",
        description=(
            "Searches for equipment and assets in the knowledge graph "
            "and document store. Supports type filtering."
        ),
        category=ToolCategory.SEARCH,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Asset name or keyword"},
                "asset_type": {"type": "string", "description": "Optional type filter (e.g. Pump, Valve, Motor)"},
                "limit": {"type": "integer", "description": "Max results (default 10)"},
                "source": {
                    "type": "string",
                    "enum": ["all", "graph", "documents"],
                    "description": "Search source (default all)",
                },
            },
            "required": ["query"],
        },
    )

    def __init__(
        self,
        graph_query_service: Any = None,
        hybrid_retriever: Any = None,
    ) -> None:
        self._graph_svc = graph_query_service
        self._hybrid = hybrid_retriever

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        query = params.get("query", "")
        asset_type = params.get("asset_type", "")
        limit = min(params.get("limit", 10), 50)
        source = params.get("source", "all")

        if not query.strip():
            return ToolResult(data=None, error="Search query cannot be empty.")

        sr = await search_hybrid(
            query=query,
            graph_svc=self._graph_svc,
            hybrid=self._hybrid,
            top_k=limit,
            source=source,
            tool_name="AssetSearchTool",
            context=context,
            entity_type=asset_type or None,
            doc_query_augment=f"{asset_type} equipment asset" if asset_type else "equipment asset",
            cache=context.retrieval_cache,
            graph_item_fn=lambda e: {
                "id": e.id, "name": e.name, "type": e.type,
                "confidence": e.confidence, "aliases": e.aliases,
                "source_document": e.source_document,
            },
            doc_item_fn=lambda item: {
                "content": item.content[:2000], "score": item.score,
                "document_name": item.document_name, "document_id": item.document_id,
                "source": item.source,
            },
        )

        if not sr.entities and not sr.documents:
            return ToolResult(
                data={"assets": [], "documents": [], "total_assets": 0, "total_documents": 0},
                error="No assets found.",
            )

        return ToolResult(
            data={
                "assets": sr.entities,
                "documents": sr.documents,
                "total_assets": sr.total_entities,
                "total_documents": sr.total_documents,
            },
            metadata={"asset_count": sr.total_entities, "doc_count": sr.total_documents},
        )


class AssetRelationshipTool(FrameworkTool):
    """Discovers relationships and connections between assets."""

    metadata = ToolMetadata(
        tool_id="asset_relationship",
        name="Asset Relationship",
        description=(
            "Finds connected assets, equipment hierarchies, and parts. "
            "Shows how assets relate to each other in the knowledge graph."
        ),
        category=ToolCategory.KNOWLEDGE_GRAPH,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "asset_id": {"type": "string", "description": "Asset/entity ID in the knowledge graph"},
                "asset_name": {"type": "string", "description": "Asset name to search if ID is unknown"},
                "depth": {"type": "integer", "description": "Traversal depth (default 1, max 3)"},
                "rel_types": {"type": "string", "description": "Optional relationship type filter"},
                "limit": {"type": "integer", "description": "Max neighbors (default 30)"},
            },
            "required": [],
        },
    )

    def __init__(self, graph_query_service: Any = None) -> None:
        self._graph_svc = graph_query_service

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        asset_id = params.get("asset_id", "")
        asset_name = params.get("asset_name", "")
        depth = min(params.get("depth", 1), 3)
        rel_types_raw = params.get("rel_types", "")
        limit = min(params.get("limit", 30), 100)

        if not asset_id and not asset_name:
            return ToolResult(data=None, error="Either asset_id or asset_name is required.")
        if self._graph_svc is None:
            return ToolResult(data=None, error="Graph query service is not available.")

        resolved_id, resolved_name, err = await self.resolve_entity(asset_id, asset_name, self._graph_svc, context)
        if err:
            return err

        parsed_rels: list[str] | None = None
        if rel_types_raw.strip():
            parsed_rels = [t.strip().upper() for t in rel_types_raw.split(",") if t.strip()]

        try:
            entity, neighbors, total = await self._graph_svc.get_neighbors(
                entity_id=resolved_id,
                depth=depth,
                rel_types=parsed_rels,
                limit=limit,
            )
        except Exception as exc:
            return ToolResult(data=None, error=f"Failed to retrieve relationships: {exc}")

        if entity is None:
            return ToolResult(data=None, error=f"Asset '{resolved_id}' not found.")

        name = entity.name or resolved_name or asset_name or resolved_id

        relationships: list[dict] = []
        for n in neighbors:
            relationships.append({
                "direction": "outgoing",
                "source_id": n.relationship.source,
                "source_name": name if n.relationship.source == resolved_id else "",
                "target_id": n.relationship.target,
                "target_name": n.entity.name,
                "target_type": n.entity.type,
                "relationship_type": n.relationship.type,
                "depth": n.depth,
                "confidence": n.entity.confidence,
            })

        by_type: dict[str, int] = {}
        for r in relationships:
            by_type[r["relationship_type"]] = by_type.get(r["relationship_type"], 0) + 1

        context.add_reasoning_step(
            f"AssetRelationshipTool: {len(relationships)} connection(s) for {name} "
            f"({len(by_type)} relationship type(s))"
        )

        return ToolResult(
            data={
                "asset_id": resolved_id,
                "asset_name": name,
                "relationships": relationships,
                "total": len(relationships),
                "relationship_breakdown": by_type,
            },
            metadata={"relationship_count": len(relationships), "depth": depth},
        )


class AssetRiskTool(FrameworkTool):
    """Assesses risk profile for an asset based on graph and document data."""

    metadata = ToolMetadata(
        tool_id="asset_risk",
        name="Asset Risk Profile",
        description=(
            "Evaluates risk for an asset by analyzing connected entities, "
            "incident history, maintenance gaps, and operational context."
        ),
        category=ToolCategory.REPORTING,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "asset_id": {"type": "string", "description": "Asset/entity ID"},
                "asset_name": {"type": "string", "description": "Asset name (used if ID is unavailable)"},
            },
            "required": [],
        },
    )

    def __init__(
        self,
        graph_query_service: Any = None,
        hybrid_retriever: Any = None,
        llm_provider: Any = None,
    ) -> None:
        self._graph_svc = graph_query_service
        self._hybrid = hybrid_retriever
        self._llm = llm_provider

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        asset_id = params.get("asset_id", "")
        asset_name = params.get("asset_name", "")

        if not asset_id and not asset_name:
            return ToolResult(data=None, error="Either asset_id or asset_name is required.")

        resolved_id = asset_id
        resolved_name = asset_name

        evidence_docs: list[dict] = []
        neighbors: list[dict] = []

        # Gather evidence
        search_term = resolved_name or resolved_id
        if self._graph_svc is not None:
            try:
                if not resolved_id and resolved_name:
                    results, _ = await self._graph_svc.search_entities(query=resolved_name, limit=3)
                    if results:
                        resolved_id = results[0].id
                        resolved_name = results[0].name

                if resolved_id:
                    entity, nbrs, total = await self._graph_svc.get_neighbors(
                        entity_id=resolved_id, depth=2, limit=50,
                    )
                    if entity:
                        resolved_name = entity.name
                    for n in nbrs:
                        neighbors.append({
                            "name": n.entity.name,
                            "type": n.entity.type,
                            "relationship": n.relationship.type,
                            "confidence": n.entity.confidence,
                        })
            except Exception:
                pass

        if self._hybrid is not None:
            try:
                unified = await self._hybrid.retrieve(
                    query=f"{search_term} risk hazard safety incident", top_k=8,
                )
                for item in unified.items:
                    evidence_docs.append({
                        "content": item.content[:800],
                        "score": item.score,
                        "document_name": item.document_name,
                    })
            except Exception:
                pass

        risk_score, risk_level, findings = self._compute_risk(
            resolved_name, neighbors, evidence_docs,
        )

        llm_analysis = ""
        if self._llm is not None:
            try:
                prompt = self._build_risk_prompt(resolved_name, neighbors, evidence_docs, findings)
                result = await self._llm.generate(prompt=prompt)
                llm_analysis = result if isinstance(result, str) else (
                    result.get("text", "") if isinstance(result, dict) else str(result)
                )
            except Exception:
                llm_analysis = self._fallback_risk_analysis(resolved_name, risk_level, findings)

        if not llm_analysis:
            llm_analysis = self._fallback_risk_analysis(resolved_name, risk_level, findings)

        context.add_reasoning_step(
            f"AssetRiskTool: {resolved_name} → risk={risk_level} ({risk_score:.0%})"
        )

        return ToolResult(
            data={
                "asset_id": resolved_id or "unknown",
                "asset_name": resolved_name or search_term,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "findings": findings,
                "analysis": llm_analysis,
                "evidence_documents": len(evidence_docs),
                "evidence_relationships": len(neighbors),
            },
            metadata={"risk_score": risk_score, "risk_level": risk_level},
        )

    @staticmethod
    def _compute_risk(
        name: str, neighbors: list[dict], docs: list[dict],
    ) -> tuple[float, str, list[dict]]:
        findings: list[dict] = []

        risk_keywords = ["incident", "failure", "breakdown", "fault", "hazard", "critical"]
        has_incident = any(
            any(kw in n["name"].lower() or kw in n["relationship"].lower() for kw in risk_keywords)
            for n in neighbors
        )
        if has_incident:
            findings.append({
                "type": "incident_history",
                "severity": "high",
                "detail": "Asset has connections to incident- or failure-related entities.",
            })

        maintenance_keywords = ["maintenance", "overdue", "missed", "inspection"]
        has_maintenance_gap = any(
            any(kw in n["name"].lower() or kw in n["relationship"].lower() for kw in maintenance_keywords)
            for n in neighbors
        )
        if has_maintenance_gap:
            findings.append({
                "type": "maintenance_gap",
                "severity": "medium",
                "detail": "Asset has maintenance-related flags or gaps.",
            })

        has_docs = len(docs) > 0
        if not has_docs:
            findings.append({
                "type": "missing_documentation",
                "severity": "low",
                "detail": "No operational or risk documents found for this asset.",
            })

        if not neighbors:
            findings.append({
                "type": "isolated_asset",
                "severity": "medium",
                "detail": "Asset has no connections in the knowledge graph — may be missing contextual data.",
            })

        base_score = 0.3
        for f in findings:
            if f["severity"] == "high":
                base_score += 0.25
            elif f["severity"] == "medium":
                base_score += 0.15
            elif f["severity"] == "low":
                base_score += 0.05

        final_score = min(base_score, 1.0)
        level = (
            "Critical" if final_score >= 0.8 else
            "High" if final_score >= 0.6 else
            "Medium" if final_score >= 0.4 else
            "Low"
        )
        return round(final_score, 2), level, findings

    @staticmethod
    def _build_risk_prompt(name: str, neighbors: list[dict], docs: list[dict], findings: list[dict]) -> str:
        prompt = f"Analyze the risk profile for asset '{name}' grounded ONLY in the evidence below.\n\n"
        if findings:
            prompt += "Identified risk factors:\n"
            for f in findings:
                prompt += f"- [{f['severity'].upper()}] {f['detail']}\n"
            prompt += "\n"
        if docs:
            prompt += "Reference documents:\n"
            for d in docs[:3]:
                prompt += f"- {d['document_name']}: {d['content'][:300]}\n"
        prompt += (
            "\nSTRICT RULES:\n"
            "- Never invent risk factors, mitigations, or monitoring steps not in the evidence.\n"
            "- Every assessment claim MUST cite specific risk factors from the data above.\n"
            "- If no evidence exists for a section, state: 'No supporting evidence found.'\n"
            "Based on available evidence:\n"
            "1. Overall risk assessment\n"
            "2. Key risk drivers from evidence\n"
            "3. Recommended mitigations\n"
            "4. Monitoring recommendations"
        )
        return prompt

    @staticmethod
    def _fallback_risk_analysis(name: str, level: str, findings: list[dict]) -> str:
        lines = [
            f"**Risk Profile — {name}**",
            f"**Overall Risk Level:** {level}",
            "",
            "### Risk Factors",
        ]
        if findings:
            for f in findings:
                lines.append(f"- **[{f['severity'].upper()}]** {f['detail']}")
        else:
            lines.append("- No significant risk factors identified.")
        lines.extend([
            "",
            "### Recommendations",
            "- Monitor asset condition regularly",
            "- Maintain up-to-date documentation",
            "- Schedule preventive maintenance per manufacturer guidelines",
            "- Review and update risk register periodically",
        ])
        return "\n".join(lines)


class AssetMaintenanceTool(FrameworkTool):
    """Retrieves maintenance status, history, and recommendations for an asset."""

    metadata = ToolMetadata(
        tool_id="asset_maintenance",
        name="Asset Maintenance Status",
        description=(
            "Provides maintenance status, history, and recommendations "
            "for an asset by analyzing graph connections and documents."
        ),
        category=ToolCategory.KNOWLEDGE_GRAPH,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "asset_id": {"type": "string", "description": "Asset/entity ID in the knowledge graph"},
                "asset_name": {"type": "string", "description": "Asset name (used if ID is unavailable)"},
                "include_recommendations": {
                    "type": "boolean",
                    "description": "Whether to include maintenance recommendations (default true)",
                },
            },
            "required": [],
        },
    )

    def __init__(
        self,
        graph_query_service: Any = None,
        hybrid_retriever: Any = None,
        llm_provider: Any = None,
    ) -> None:
        self._graph_svc = graph_query_service
        self._hybrid = hybrid_retriever
        self._llm = llm_provider

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        asset_id = params.get("asset_id", "")
        asset_name = params.get("asset_name", "")
        include_recs = params.get("include_recommendations", True)

        if not asset_id and not asset_name:
            return ToolResult(data=None, error="Either asset_id or asset_name is required.")

        resolved_id = asset_id
        resolved_name = asset_name
        maintenance_records: list[dict] = []
        related_docs: list[dict] = []

        if self._graph_svc is not None:
            try:
                if not resolved_id and resolved_name:
                    results, _ = await self._graph_svc.search_entities(query=resolved_name, limit=3)
                    if results:
                        resolved_id = results[0].id
                        resolved_name = results[0].name

                if resolved_id:
                    entity, nbrs, total = await self._graph_svc.get_neighbors(
                        entity_id=resolved_id, depth=2, limit=30,
                    )
                    if entity:
                        resolved_name = entity.name

                    maint_keywords = [
                        "maintenance", "inspection", "repair", "service",
                        "overhaul", "check", "log", "record", "history",
                    ]
                    for n in nbrs:
                        rel = n.relationship.type.lower()
                        e_name = n.entity.name.lower()
                        if any(kw in rel or kw in e_name for kw in maint_keywords):
                            maintenance_records.append({
                                "entity_name": n.entity.name,
                                "entity_type": n.entity.type,
                                "relationship": n.relationship.type,
                                "confidence": n.entity.confidence,
                                "source_document": n.entity.source_document,
                                "depth": n.depth,
                            })
            except Exception:
                pass

        search_term = resolved_name or resolved_id
        if self._hybrid is not None:
            try:
                unified = await self._hybrid.retrieve(
                    query=f"{search_term} maintenance inspection service record", top_k=8,
                )
                for item in unified.items:
                    related_docs.append({
                        "content": item.content[:600],
                        "score": item.score,
                        "document_name": item.document_name,
                    })
            except Exception:
                pass

        recommendations = ""
        if include_recs and self._llm is not None:
            try:
                prompt = (
                    f"Provide maintenance recommendations for asset '{resolved_name or search_term}' "
                    f"grounded ONLY in the evidence below.\n"
                )
                if maintenance_records:
                    prompt += "Maintenance history:\n"
                    for r in maintenance_records[:5]:
                        prompt += f"- {r['relationship']}: {r['entity_name']}\n"
                if related_docs:
                    prompt += "\nReference documents:\n"
                    for d in related_docs[:3]:
                        prompt += f"- {d['document_name']}: {d['content'][:300]}\n"
                prompt += (
                    "\nSTRICT RULES:\n"
                    "- Never invent schedules, spare parts, downtime estimates, or part numbers.\n"
                    "- Only reference information present in the maintenance history or reference documents above.\n"
                    "- If no evidence exists for a recommendation, state: 'No supporting evidence found.'\n"
                    "Based on available evidence:\n"
                    "1. Known maintenance requirements\n"
                    "2. Priority actions from evidence\n"
                    "3. Reference documents"
                )
                result = await self._llm.generate(prompt=prompt)
                recommendations = result if isinstance(result, str) else (
                    result.get("text", "") if isinstance(result, dict) else str(result)
                )
            except Exception:
                recommendations = self._fallback_maintenance_rec(resolved_name or search_term)

        if include_recs and not recommendations:
            recommendations = self._fallback_maintenance_rec(resolved_name or search_term)

        context.add_reasoning_step(
            f"AssetMaintenanceTool: {len(maintenance_records)} record(s) for {resolved_name or search_term}"
        )

        return ToolResult(
            data={
                "asset_id": resolved_id or "unknown",
                "asset_name": resolved_name or search_term,
                "maintenance_records": maintenance_records,
                "total_records": len(maintenance_records),
                "related_documents": len(related_docs),
                "recommendations": recommendations,
            },
            metadata={"record_count": len(maintenance_records)},
        )

    @staticmethod
    def _fallback_maintenance_rec(name: str) -> str:
        return (
            f"**Maintenance Recommendations — {name}**\n\n"
            "### Recommended Schedule\n"
            "- **Daily:** Visual inspection, check for leaks, vibration, noise\n"
            "- **Weekly:** Clean external surfaces, verify lubricant levels\n"
            "- **Monthly:** Inspect critical components, test safety devices\n"
            "- **Quarterly:** Detailed inspection, change lubricants\n"
            "- **Annually:** Major overhaul, replace wear components\n\n"
            "### Priority Actions\n"
            "1. Review manufacturer maintenance manual for exact intervals\n"
            "2. Check for any open work orders or overdue inspections\n"
            "3. Ensure required spare parts are in stock\n\n"
            "> *Based on standard industrial maintenance practices.*"
        )


class AssetSummaryTool(FrameworkTool):
    """Generates a comprehensive summary of an asset from all available sources."""

    metadata = ToolMetadata(
        tool_id="asset_summary",
        name="Asset Summary",
        description=(
            "Generates a comprehensive asset overview by combining "
            "knowledge graph data, document references, risk profile, "
            "and maintenance status into a single summary."
        ),
        category=ToolCategory.REPORTING,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "asset_id": {"type": "string", "description": "Asset/entity ID"},
                "asset_name": {"type": "string", "description": "Asset name (used if ID is unavailable)"},
            },
            "required": [],
        },
    )

    def __init__(
        self,
        graph_query_service: Any = None,
        hybrid_retriever: Any = None,
        llm_provider: Any = None,
    ) -> None:
        self._graph_svc = graph_query_service
        self._hybrid = hybrid_retriever
        self._llm = llm_provider

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        asset_id = params.get("asset_id", "")
        asset_name = params.get("asset_name", "")

        if not asset_id and not asset_name:
            return ToolResult(data=None, error="Either asset_id or asset_name is required.")

        resolved_id = asset_id
        resolved_name = asset_name

        info: dict[str, Any] = {
            "asset_id": resolved_id or "unknown",
            "asset_name": resolved_name or "unknown",
            "type": "",
            "aliases": [],
            "confidence": 0.0,
            "neighbor_count": 0,
            "neighbor_types": [],
            "document_count": 0,
            "source_document": "",
        }

        relationships: list[dict] = []
        documents: list[dict] = []

        # Phase 1: Graph data
        if self._graph_svc is not None:
            try:
                if not resolved_id and resolved_name:
                    results, _ = await self._graph_svc.search_entities(query=resolved_name, limit=3)
                    if results:
                        resolved_id = results[0].id
                        resolved_name = results[0].name
                        info["type"] = results[0].type
                        info["aliases"] = results[0].aliases
                        info["confidence"] = results[0].confidence
                        info["source_document"] = results[0].source_document

                if resolved_id:
                    entity, nbrs, total = await self._graph_svc.get_neighbors(
                        entity_id=resolved_id, depth=1, limit=30,
                    )
                    if entity:
                        info["type"] = entity.type or info["type"]
                        info["aliases"] = entity.aliases or info["aliases"]
                        info["confidence"] = entity.confidence or info["confidence"]
                        info["source_document"] = entity.source_document or info["source_document"]

                    info["neighbor_count"] = total
                    seen_types: set[str] = set()
                    for n in nbrs:
                        seen_types.add(n.entity.type)
                        relationships.append({
                            "target_name": n.entity.name,
                            "target_type": n.entity.type,
                            "relationship": n.relationship.type,
                        })
                    info["neighbor_types"] = sorted(seen_types)
            except Exception:
                pass

        # Phase 2: Document data
        search_term = resolved_name or resolved_id
        if self._hybrid is not None:
            try:
                unified = await self._hybrid.retrieve(query=search_term, top_k=8)
                for item in unified.items:
                    documents.append({
                        "document_name": item.document_name,
                        "score": item.score,
                        "content_preview": item.content[:300],
                    })
                info["document_count"] = len(documents)
            except Exception:
                pass

        # Phase 3: Generate narrative
        narrative = ""
        if self._llm is not None:
            try:
                prompt = self._build_summary_prompt(resolved_name, info, relationships, documents)
                result = await self._llm.generate(prompt=prompt)
                narrative = result if isinstance(result, str) else (
                    result.get("text", "") if isinstance(result, dict) else str(result)
                )
            except Exception:
                narrative = self._fallback_summary(resolved_name, info, relationships, documents)

        if not narrative:
            narrative = self._fallback_summary(resolved_name, info, relationships, documents)

        context.add_reasoning_step(
            f"AssetSummaryTool: summary generated for {resolved_name}"
        )

        return ToolResult(
            data={
                "asset_id": resolved_id or "unknown",
                "asset_name": resolved_name or search_term,
                "asset_type": info["type"],
                "aliases": info["aliases"],
                "confidence": info["confidence"],
                "neighbor_count": info["neighbor_count"],
                "neighbor_types": info["neighbor_types"],
                "document_count": info["document_count"],
                "top_relationships": relationships[:10],
                "top_documents": documents[:5],
                "summary": narrative,
            },
            metadata={
                "has_graph_data": info["neighbor_count"] > 0 or bool(info["type"]),
                "has_document_data": info["document_count"] > 0,
            },
        )

    @staticmethod
    def _build_summary_prompt(
        name: str, info: dict, relationships: list[dict], documents: list[dict],
    ) -> str:
        prompt = f"Generate a comprehensive asset summary for '{name}'.\n\n"
        if info.get("type"):
            prompt += f"Type: {info['type']}\n"
        if info.get("aliases"):
            prompt += f"Aliases: {', '.join(info['aliases'])}\n"
        if info.get("neighbor_count", 0) > 0:
            prompt += f"Connected entities: {info['neighbor_count']}\n"
            prompt += f"Neighbor types: {', '.join(info['neighbor_types'])}\n"
        if relationships:
            prompt += "\nKey connections:\n"
            for r in relationships[:8]:
                prompt += f"- {r['relationship']} → {r['target_name']} ({r['target_type']})\n"
        if documents:
            prompt += "\nRelated documents:\n"
            for d in documents[:5]:
                prompt += f"- {d['document_name']} (relevance: {d['score']:.2f})\n"
        prompt += (
            "\nProvide:\n"
            "1. Asset overview (type, purpose, key identifiers)\n"
            "2. Connected systems and equipment\n"
            "3. Available documentation\n"
            "4. Operational context\n"
            "Format as a structured briefing."
        )
        return prompt

    @staticmethod
    def _fallback_summary(
        name: str, info: dict, relationships: list[dict], documents: list[dict],
    ) -> str:
        lines = [f"## Asset Summary — {name}", ""]
        if info.get("type"):
            lines.append(f"**Type:** {info['type']}")
        if info.get("aliases"):
            lines.append(f"**Aliases:** {', '.join(info['aliases'])}")
        lines.append(f"**Confidence:** {info.get('confidence', 0.0):.0%}")
        lines.append("")

        if relationships:
            lines.append(f"### Connected Assets ({len(relationships)})")
            by_rel: dict[str, list[str]] = {}
            for r in relationships:
                by_rel.setdefault(r["relationship"], []).append(r["target_name"])
            for rel_type, targets in sorted(by_rel.items(), key=lambda x: -len(x[1]))[:5]:
                lines.append(f"- **{rel_type}** → {', '.join(targets[:3])}")
                if len(targets) > 3:
                    lines[-1] += f" (+{len(targets) - 3} more)"
            lines.append("")

        if documents:
            lines.append(f"### Related Documents ({len(documents)})")
            for d in documents[:5]:
                lines.append(f"- **{d['document_name']}** (relevance: {d['score']:.2f})")
            lines.append("")

        if not relationships and not documents:
            lines.append("No data found in the knowledge graph or document store.")
            lines.append("Try registering this asset or uploading relevant documentation.")

        return "\n".join(lines)
