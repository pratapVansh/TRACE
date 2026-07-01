import {
  BookOpen,
  ClipboardCheck,
  GitBranch,
  Lightbulb,
  Search,
  ShieldCheck,
  Wrench,
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

export const SUGGESTED_PROMPTS: SuggestedPrompt[] = [
  {
    id: "sp-1",
    label: "Pump seal procedure",
    prompt: "What is the seal replacement procedure for pump P-4102?",
  },
  {
    id: "sp-2",
    label: "CDU furnace inspection",
    prompt: "What is the tube inspection interval for CDU furnace F-101?",
  },
  {
    id: "sp-3",
    label: "Flare maintenance history",
    prompt: "Summarize flare stack maintenance history for Unit 4.",
  },
  {
    id: "sp-4",
    label: "LOTO requirements",
    prompt: "What LOTO steps apply before opening heat exchanger E-2201?",
  },
  {
    id: "sp-5",
    label: "Compressor vibration",
    prompt: "Show recent vibration analysis findings for compressor K-301.",
  },
  {
    id: "sp-6",
    label: "OISD compliance",
    prompt: "Which OISD standards apply to crude storage tank T-401?",
  },
];

export const COPILOT_MESSAGES: CopilotMessage[] = [
  {
    id: "msg-1",
    role: "user",
    content: "What is the seal replacement procedure for pump P-4102?",
    timestamp: "2026-07-01T09:12:00Z",
  },
  {
    id: "msg-2",
    role: "assistant",
    content:
      "The seal replacement for cooling water circulation pump P-4102 follows SOP-MNT-0088. Key steps include: isolate and LOTO the pump per SOP-HSE-0031, drain the casing, remove the coupling guard, extract the mechanical seal assembly, inspect the seal chamber for scoring, install the OEM seal kit (part no. SK-4102-Rev-B), and perform alignment check before return to service. Torque values and tolerances are specified in the OEM manual section 4.2.",
    timestamp: "2026-07-01T09:12:08Z",
    citationIds: ["src-1", "src-2", "src-3"],
  },
  {
    id: "msg-3",
    role: "user",
    content: "Are there any open work orders for this pump?",
    timestamp: "2026-07-01T09:13:00Z",
  },
  {
    id: "msg-4",
    role: "assistant",
    content:
      "Yes. Work order WO-8842 — Cooling water pump overhaul — is assigned to Maria Chen with critical priority. The work order is currently overdue by 2 days. The maintenance log indicates the mechanical seal replacement is the primary scope item.",
    timestamp: "2026-07-01T09:13:06Z",
    citationIds: ["src-4"],
  },
];

export const REFERENCED_DOCUMENTS: ReferencedDocument[] = [
  {
    id: "ref-1",
    title: "SOP — Pump P-4102 Seal Replacement",
    type: "SOP",
    page: "pp. 3–7",
    relevance: 98,
  },
  {
    id: "ref-2",
    title: "LOTO Procedure — Utilities Pump House",
    type: "Safety Manual",
    page: "p. 12",
    relevance: 91,
  },
  {
    id: "ref-3",
    title: "OEM Manual — CW Pump Series 4100",
    type: "OEM Manual",
    page: "§ 4.2",
    relevance: 87,
  },
  {
    id: "ref-4",
    title: "WO-8842 — Cooling Water Pump Overhaul",
    type: "Maintenance Log",
    relevance: 94,
  },
];

export const SOURCE_EXCERPTS: SourceExcerpt[] = [
  {
    id: "src-1",
    documentId: "ref-1",
    documentTitle: "SOP-MNT-0088 — Pump P-4102 Seal Replacement",
    page: "p. 4",
    excerpt:
      "Before commencing seal replacement, verify LOTO isolation of motor breaker P-4102-M1 and close suction/discharge block valves. Allow minimum 30 minutes depressurization.",
    highlighted: "LOTO isolation",
  },
  {
    id: "src-2",
    documentId: "ref-1",
    documentTitle: "SOP-MNT-0088 — Pump P-4102 Seal Replacement",
    page: "p. 6",
    excerpt:
      "Install mechanical seal kit SK-4102-Rev-B per OEM drawing. Torque gland bolts to 45 N·m in star pattern. Maximum runout tolerance: 0.05 mm.",
    highlighted: "SK-4102-Rev-B",
  },
  {
    id: "src-3",
    documentId: "ref-3",
    documentTitle: "OEM Manual — CW Pump Series 4100",
    page: "§ 4.2",
    excerpt:
      "Seal chamber surface finish must not exceed 0.8 µm Ra. Replace O-rings and gasket set with every seal change. Do not reuse compression packing.",
  },
  {
    id: "src-4",
    documentId: "ref-4",
    documentTitle: "WO-8842 — Cooling Water Pump Overhaul",
    page: "—",
    excerpt:
      "Work order status: Overdue. Priority: Critical. Scope: Mechanical seal replacement, coupling inspection, alignment check. Assigned: Maria Chen.",
    highlighted: "Overdue",
  },
];

export const GRAPH_STATS: GraphStat[] = [
  { label: "Total Nodes", value: "18,420" },
  { label: "Relationships", value: "47,832" },
  { label: "Linked Assets", value: "2,847" },
  { label: "Document Links", value: "14,382" },
];

export const GRAPH_INFO_ITEMS: GraphInfoItem[] = [
  {
    id: "gi-1",
    label: "Asset ↔ Document",
    description: "Equipment tags linked to SOPs, manuals, inspection reports, and P&IDs.",
  },
  {
    id: "gi-2",
    label: "Procedure ↔ Incident",
    description: "Safety and operational procedures connected to historical incident records.",
  },
  {
    id: "gi-3",
    label: "Compliance ↔ Standard",
    description: "Regulatory standards mapped to applicable assets and audit evidence.",
  },
  {
    id: "gi-4",
    label: "Maintenance ↔ Work Order",
    description: "Preventive schedules and corrective actions tied to asset hierarchy.",
  },
];

export const AI_AGENTS: AiAgent[] = [
  {
    id: "agent-maintenance",
    name: "Maintenance Agent",
    description:
      "Plans and retrieves maintenance procedures, work order history, and asset service records.",
    capabilities: ["Work order lookup", "PM schedule analysis", "Parts & BOM retrieval"],
    status: "coming_soon",
    icon: Wrench,
  },
  {
    id: "agent-compliance",
    name: "Compliance Agent",
    description:
      "Surfaces applicable standards, audit findings, and regulatory obligations by asset or process.",
    capabilities: ["Standard mapping", "Audit gap analysis", "Finding tracking"],
    status: "coming_soon",
    icon: ShieldCheck,
  },
  {
    id: "agent-sop",
    name: "SOP Agent",
    description:
      "Navigates approved procedures, version history, and step-by-step operational guidance.",
    capabilities: ["SOP retrieval", "Version comparison", "Approval status check"],
    status: "coming_soon",
    icon: BookOpen,
  },
  {
    id: "agent-search",
    name: "Search Agent",
    description:
      "Orchestrates semantic search across documents, assets, and tags with ranked relevance.",
    capabilities: ["Multi-source retrieval", "Query expansion", "Citation ranking"],
    status: "coming_soon",
    icon: Search,
  },
  {
    id: "agent-root-cause",
    name: "Root Cause Agent",
    description:
      "Correlates incidents, failures, and maintenance events to identify recurring failure patterns.",
    capabilities: ["Failure correlation", "Timeline analysis", "Hypothesis generation"],
    status: "planned",
    icon: GitBranch,
  },
  {
    id: "agent-lessons",
    name: "Lessons Learned Agent",
    description:
      "Extracts and surfaces institutional knowledge from incident reports and turnaround debriefs.",
    capabilities: ["Lesson extraction", "Similar incident matching", "Knowledge capture"],
    status: "planned",
    icon: Lightbulb,
  },
];
