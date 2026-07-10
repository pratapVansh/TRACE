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

export const SUGGESTED_PROMPTS: SuggestedPrompt[] = [];

export const COPILOT_MESSAGES: CopilotMessage[] = [];

export const REFERENCED_DOCUMENTS: ReferencedDocument[] = [];

export const SOURCE_EXCERPTS: SourceExcerpt[] = [];

export const GRAPH_STATS: GraphStat[] = [];

export const GRAPH_INFO_ITEMS: GraphInfoItem[] = [];

export const AI_AGENTS: AiAgent[] = [];
