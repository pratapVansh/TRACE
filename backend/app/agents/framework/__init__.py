"""Production-ready agent framework for TRACE (Milestone 10).

All public names are importable directly from this package.

Memory layer (Prompt 2):
- ``Memory`` — abstract interface for all memory types
- ``ConversationMemory`` — wraps ``ConversationRepository``
- ``WorkingMemory`` — short-lived execution scratchpad
- ``MemoryManager`` — orchestrates memory types, merges into context
- ``ContextSummarizer`` / ``SimpleSummarizer`` — summarization interface

Tool framework (Prompt 3):
- ``FrameworkTool`` — base class with metadata, permissions, schemas
- ``ToolRegistry`` — register, unregister, get, list, lazy init
- ``ToolExecutor`` — validate, check permissions, execute, log
- ``ToolContext`` — shared context (user, permissions, working memory)
- ``ToolCategory`` — category enum for organisation
- ``ToolMetadata`` — declarative metadata dataclass
- ``ToolExecutionRecord`` — immutable execution log entry
- ``PingTool``, ``CurrentTimeTool``, ``SystemInfoTool`` — examples
"""

from app.agents.framework.base import BaseAgent
from app.agents.framework.workflow import (
    AgentRouter,
    MultiAgentExecutor,
    MultiAgentRequest,
    MultiAgentResponse,
    RoutingPlan,
    TimelineEntry,
)
from app.agents.framework.context import AgentContext
from app.agents.framework.exceptions import (
    AgentExecutionError,
    AgentFrameworkError,
    AgentNotFoundError,
    AgentRegistrationError,
    InvalidContextError,
    OrchestrationError,
    ToolExecutionError,
)
from app.agents.framework.factory import AgentFactory
from app.agents.framework.memory import (
    ConversationMemory,
    ContextSummarizer,
    Memory,
    MemoryManager,
    SimpleSummarizer,
    WorkingMemory,
)
from app.agents.framework.orchestrator import AIOrchestrator
from app.agents.framework.registry import AgentRegistry
from app.agents.framework.response import AgentResponse
from app.agents.framework.tool import Tool, ToolResult
from app.agents.framework.tools import (
    CurrentTimeTool,
    FrameworkTool,
    PingTool,
    SystemInfoTool,
    ToolCategory,
    ToolContext,
    ToolExecutionRecord,
    ToolExecutor,
    ToolMetadata,
    ToolRegistry as FrameworkToolRegistry,
)
from app.agents.framework.agents import (
    AssetIntelligenceAgent,
    AssetMaintenanceTool,
    AssetRelationshipTool,
    AssetRiskTool,
    AssetSearchTool,
    AssetSummaryTool,
    ComplianceAgent,
    ComplianceCheckTool,
    ComplianceGapTool,
    ComplianceRecommendationTool,
    ComplianceSearchTool,
    DocumentAnalysisAgent,
    DocumentComparisonTool,
    DocumentMetadataTool,
    DocumentSearchTool,
    DocumentSummaryTool,
    EvidenceCollectionTool,
    ExecutiveSummaryTool,
    GraphNeighborTool,
    GraphPathTool,
    GraphSearchTool,
    GraphStatisticsTool,
    IncidentSearchTool,
    KnowledgeGraphAgent,
    MaintenanceAgent,
    MaintenanceChecklistTool,
    MaintenanceHistoryTool,
    MaintenanceRecommendationTool,
    MaintenanceRiskAssessmentTool,
    MaintenanceSearchTool,
    MarkdownReportTool,
    ReportGenerationAgent,
    ReportGenerationTool,
    RootCauseAnalysisAgent,
    RootCauseTool,
    SimilarIncidentTool,
)

__all__ = [
    "AgentContext",
    "AgentExecutionError",
    "AgentFactory",
    "AgentFrameworkError",
    "AgentNotFoundError",
    "AgentRegistrationError",
    "AgentRegistry",
    "AgentResponse",
    "AIOrchestrator",
    "AssetIntelligenceAgent",
    "AssetMaintenanceTool",
    "AssetRelationshipTool",
    "AssetRiskTool",
    "AssetSearchTool",
    "AssetSummaryTool",
    "BaseAgent",
    "ComplianceAgent",
    "ComplianceCheckTool",
    "ComplianceGapTool",
    "ComplianceRecommendationTool",
    "ComplianceSearchTool",
    "ContextSummarizer",
    "ConversationMemory",
    "CurrentTimeTool",
    "DocumentAnalysisAgent",
    "DocumentComparisonTool",
    "DocumentMetadataTool",
    "DocumentSearchTool",
    "DocumentSummaryTool",
    "EvidenceCollectionTool",
    "ExecutiveSummaryTool",
    "FrameworkTool",
    "FrameworkToolRegistry",
    "GraphNeighborTool",
    "GraphPathTool",
    "GraphSearchTool",
    "GraphStatisticsTool",
    "IncidentSearchTool",
    "InvalidContextError",
    "KnowledgeGraphAgent",
    "MaintenanceAgent",
    "MaintenanceChecklistTool",
    "MaintenanceHistoryTool",
    "MaintenanceRecommendationTool",
    "MaintenanceRiskAssessmentTool",
    "MaintenanceSearchTool",
    "MarkdownReportTool",
    "Memory",
    "MemoryManager",
    "MultiAgentExecutor",
    "MultiAgentRequest",
    "MultiAgentResponse",
    "OrchestrationError",
    "PingTool",
    "ReportGenerationAgent",
    "ReportGenerationTool",
    "RootCauseAnalysisAgent",
    "RootCauseTool",
    "RoutingPlan",
    "SimilarIncidentTool",
    "SimpleSummarizer",
    "SystemInfoTool",
    "TimelineEntry",
    "Tool",
    "ToolCategory",
    "ToolContext",
    "ToolExecutionError",
    "ToolExecutionRecord",
    "ToolExecutor",
    "ToolMetadata",
    "ToolResult",
    "WorkingMemory",
]
