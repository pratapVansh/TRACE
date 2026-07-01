import { KnowledgeGraphPageContent } from "@/components/ai-workspace/knowledge-graph/knowledge-graph-page-content";
import { ProtectedPage } from "@/components/layout/protected-page";
import { PERMISSIONS } from "@/types/permissions";

export default function KnowledgeGraphPage() {
  return (
    <ProtectedPage permission={PERMISSIONS.KNOWLEDGE_GRAPH}>
      <KnowledgeGraphPageContent />
    </ProtectedPage>
  );
}
