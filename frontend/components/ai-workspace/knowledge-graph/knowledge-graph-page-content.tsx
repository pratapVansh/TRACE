import { FutureNotice } from "@/components/ai-workspace/future-notice";
import { GraphInfoPanel } from "@/components/ai-workspace/knowledge-graph/graph-info-panel";
import { GraphPlaceholderCard } from "@/components/ai-workspace/knowledge-graph/graph-placeholder-card";
import { PageHeader } from "@/components/common/page-header";
import { GRAPH_INFO_ITEMS, GRAPH_STATS } from "@/lib/ai-workspace/mock-data";

export function KnowledgeGraphPageContent() {
  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
      <PageHeader
        sectionLabel="AI Workspace"
        title="Knowledge Graph"
        description="Explore relationships between assets, procedures, incidents, and compliance standards across Northfield Refinery Complex."
      />

      <FutureNotice />

      <div className="grid gap-6 xl:grid-cols-12">
        <div className="xl:col-span-8">
          <GraphPlaceholderCard />
        </div>
        <div className="xl:col-span-4">
          <GraphInfoPanel stats={GRAPH_STATS} items={GRAPH_INFO_ITEMS} />
        </div>
      </div>
    </div>
  );
}
