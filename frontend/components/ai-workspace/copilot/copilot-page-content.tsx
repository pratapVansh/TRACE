"use client";

import { useState } from "react";

import { FutureNotice } from "@/components/ai-workspace/future-notice";
import { ConversationArea } from "@/components/ai-workspace/copilot/conversation-area";
import { ReferencedDocuments } from "@/components/ai-workspace/copilot/referenced-documents";
import { SourcePanel } from "@/components/ai-workspace/copilot/source-panel";
import { SuggestedPrompts } from "@/components/ai-workspace/copilot/suggested-prompts";
import { PageHeader } from "@/components/common/page-header";
import {
  COPILOT_MESSAGES,
  REFERENCED_DOCUMENTS,
  SOURCE_EXCERPTS,
  SUGGESTED_PROMPTS,
} from "@/lib/ai-workspace/mock-data";

export function CopilotPageContent() {
  const [draft, setDraft] = useState("");
  const [activeDocId, setActiveDocId] = useState(REFERENCED_DOCUMENTS[0]?.id);

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
      <PageHeader
        sectionLabel="AI Workspace"
        title="Copilot"
        description="Conversational interface for grounded industrial knowledge — preview UI with sample conversation and citations."
      />

      <FutureNotice
        title="UI preview only"
        description="Copilot responses are simulated. Live LLM inference, RAG retrieval, and streaming will be connected in a future milestone."
      />

      <SuggestedPrompts prompts={SUGGESTED_PROMPTS} onSelect={setDraft} />

      <div className="grid gap-6 xl:grid-cols-12">
        <div className="xl:col-span-5">
          <ReferencedDocuments
            documents={REFERENCED_DOCUMENTS}
            activeId={activeDocId}
            onSelect={setActiveDocId}
          />
        </div>

        <div className="xl:col-span-4">
          <ConversationArea draft={draft} onDraftChange={setDraft} messages={COPILOT_MESSAGES} />
        </div>

        <div className="xl:col-span-3">
          <SourcePanel sources={SOURCE_EXCERPTS} activeDocumentId={activeDocId} />
        </div>
      </div>
    </div>
  );
}
