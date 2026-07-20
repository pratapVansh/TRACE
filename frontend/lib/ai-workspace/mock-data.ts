import {
  BookOpen,
  ClipboardCheck,
  GitBranch,
  Lightbulb,
  Search,
  ShieldCheck,
  Wrench,
  FileText,
} from "lucide-react";

import type {
  AiAgent,
  CopilotMessage,
  GraphInfoItem,
  GraphStat,
  ReferencedDocument,
  SourceExcerpt,
  SuggestedPrompt,
} from "@/types/ai-workspace";

export const SUGGESTED_PROMPTS: SuggestedPrompt[] = [];

export const COPILOT_MESSAGES: CopilotMessage[] = [];

export const REFERENCED_DOCUMENTS: ReferencedDocument[] = [];

export const SOURCE_EXCERPTS: SourceExcerpt[] = [];

export const GRAPH_STATS: GraphStat[] = [];

export const GRAPH_INFO_ITEMS: GraphInfoItem[] = [];

export const AI_AGENTS: AiAgent[] = [
  {
    id: "document_analysis",
    name: "Document Analysis Agent",
    description:
      "Answers questions about uploaded industrial documents — searches, summarises, and compares content across the document library.",
    capabilities: [
      "Document search and retrieval",
      "Content summarisation",
      "Metadata extraction",
      "Cross-document comparison",
    ],
    status: "active",
    icon: Search,
  },
  {
    id: "knowledge_graph",
    name: "Knowledge Graph Agent",
    description:
      "Explores the industrial knowledge graph — entity relationships, paths, neighbours, and graph statistics.",
    capabilities: [
      "Entity and relationship search",
      "Neighbourhood exploration",
      "Path finding between entities",
      "Graph statistics and schema",
    ],
    status: "active",
    icon: GitBranch,
  },
  {
    id: "maintenance",
    name: "Maintenance Agent",
    description:
      "Handles preventive, corrective, inspection, shutdown, startup, spare parts, PPE, and scheduling procedures.",
    capabilities: [
      "Preventive and corrective maintenance",
      "Inspection procedures",
      "Spare parts lookup",
      "Risk assessment",
    ],
    status: "active",
    icon: Wrench,
  },
  {
    id: "compliance",
    name: "Compliance Agent",
    description:
      "Checks compliance against SOPs, regulations, safety procedures — identifies missing documentation and audit readiness.",
    capabilities: [
      "SOP compliance checking",
      "Regulatory compliance",
      "Gap analysis",
      "Audit preparation",
    ],
    status: "active",
    icon: ShieldCheck,
  },
  {
    id: "asset_intelligence",
    name: "Asset Intelligence Agent",
    description:
      "Provides asset overview, relationships, risk profiles, maintenance history, and related documentation.",
    capabilities: [
      "Asset overview and details",
      "Equipment relationships",
      "Risk profiling",
      "Maintenance recommendations",
    ],
    status: "active",
    icon: Lightbulb,
  },
  {
    id: "root_cause_analysis",
    name: "Root Cause Analysis Agent",
    description:
      "Investigates incidents, collects evidence, identifies root causes, and recommends corrective actions.",
    capabilities: [
      "Incident investigation",
      "Evidence collection",
      "Root cause identification",
      "Similar incident analysis",
    ],
    status: "active",
    icon: ClipboardCheck,
  },
  {
    id: "report_generation",
    name: "Report Generation Agent",
    description:
      "Generates structured incident, maintenance, and compliance reports plus executive summaries.",
    capabilities: [
      "Incident reports",
      "Maintenance reports",
      "Compliance reports",
      "Executive summaries",
    ],
    status: "active",
    icon: FileText,
  },
];
