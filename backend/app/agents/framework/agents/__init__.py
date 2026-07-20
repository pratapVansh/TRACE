"""Specialized agents for the TRACE AI framework (Milestone 10).

Current agents:
- ``DocumentAnalysisAgent`` — answers questions about uploaded industrial docs
- ``KnowledgeGraphAgent`` — explores and explains the knowledge graph
- ``MaintenanceAgent`` — preventive/corrective maintenance, procedures, risk
- ``ComplianceAgent`` — SOP/regulatory compliance, gap analysis, audit prep
- ``AssetIntelligenceAgent`` — asset overview, relationships, risk, maintenance
- ``RootCauseAnalysisAgent`` — incident investigation and corrective actions
- ``ReportGenerationAgent`` — structured reports and executive summaries

Available tool sets:
- Document tools: ``DocumentSearchTool``, ``DocumentSummaryTool``,
  ``DocumentMetadataTool``, ``DocumentComparisonTool``
- Graph tools: ``GraphSearchTool``, ``GraphNeighborTool``, ``GraphPathTool``,
  ``GraphStatisticsTool``
- Maintenance tools: ``MaintenanceSearchTool``, ``MaintenanceRecommendationTool``,
  ``MaintenanceHistoryTool``, ``MaintenanceChecklistTool``,
  ``MaintenanceRiskAssessmentTool``
- Compliance tools: ``ComplianceSearchTool``, ``ComplianceCheckTool``,
  ``ComplianceGapTool``, ``ComplianceRecommendationTool``
- Asset tools: ``AssetSearchTool``, ``AssetRelationshipTool``,
  ``AssetRiskTool``, ``AssetMaintenanceTool``, ``AssetSummaryTool``
- RCA tools: ``IncidentSearchTool``, ``EvidenceCollectionTool``,
  ``RootCauseTool``, ``SimilarIncidentTool``
- Report tools: ``ReportGenerationTool``, ``ExecutiveSummaryTool``,
  ``MarkdownReportTool``
"""

from app.agents.framework.agents.asset_agent import AssetIntelligenceAgent
from app.agents.framework.agents.asset_tools import (
    AssetMaintenanceTool,
    AssetRelationshipTool,
    AssetRiskTool,
    AssetSearchTool,
    AssetSummaryTool,
)
from app.agents.framework.agents.compliance_agent import ComplianceAgent
from app.agents.framework.agents.compliance_tools import (
    ComplianceCheckTool,
    ComplianceGapTool,
    ComplianceRecommendationTool,
    ComplianceSearchTool,
)
from app.agents.framework.agents.document_agent import DocumentAnalysisAgent
from app.agents.framework.agents.document_tools import (
    DocumentComparisonTool,
    DocumentMetadataTool,
    DocumentSearchTool,
    DocumentSummaryTool,
)
from app.agents.framework.agents.graph_agent import KnowledgeGraphAgent
from app.agents.framework.agents.graph_tools import (
    GraphNeighborTool,
    GraphPathTool,
    GraphSearchTool,
    GraphStatisticsTool,
)
from app.agents.framework.agents.maintenance_agent import MaintenanceAgent
from app.agents.framework.agents.maintenance_tools import (
    MaintenanceChecklistTool,
    MaintenanceHistoryTool,
    MaintenanceRecommendationTool,
    MaintenanceRiskAssessmentTool,
    MaintenanceSearchTool,
)
from app.agents.framework.agents.rca_agent import RootCauseAnalysisAgent
from app.agents.framework.agents.rca_tools import (
    EvidenceCollectionTool,
    IncidentSearchTool,
    RootCauseTool,
    SimilarIncidentTool,
)
from app.agents.framework.agents.report_agent import ReportGenerationAgent
from app.agents.framework.agents.report_tools import (
    ExecutiveSummaryTool,
    MarkdownReportTool,
    ReportGenerationTool,
)

__all__ = [
    "AssetIntelligenceAgent",
    "AssetMaintenanceTool",
    "AssetRelationshipTool",
    "AssetRiskTool",
    "AssetSearchTool",
    "AssetSummaryTool",
    "ComplianceAgent",
    "ComplianceCheckTool",
    "ComplianceGapTool",
    "ComplianceRecommendationTool",
    "ComplianceSearchTool",
    "DocumentAnalysisAgent",
    "DocumentComparisonTool",
    "DocumentMetadataTool",
    "DocumentSearchTool",
    "DocumentSummaryTool",
    "EvidenceCollectionTool",
    "ExecutiveSummaryTool",
    "GraphNeighborTool",
    "GraphPathTool",
    "GraphSearchTool",
    "GraphStatisticsTool",
    "IncidentSearchTool",
    "KnowledgeGraphAgent",
    "MaintenanceAgent",
    "MaintenanceChecklistTool",
    "MaintenanceHistoryTool",
    "MaintenanceRecommendationTool",
    "MaintenanceRiskAssessmentTool",
    "MaintenanceSearchTool",
    "MarkdownReportTool",
    "ReportGenerationAgent",
    "ReportGenerationTool",
    "RootCauseAnalysisAgent",
    "RootCauseTool",
    "SimilarIncidentTool",
]
