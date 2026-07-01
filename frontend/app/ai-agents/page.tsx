import { AiAgentsPageContent } from "@/components/ai-workspace/agents/ai-agents-page-content";
import { ProtectedPage } from "@/components/layout/protected-page";
import { PERMISSIONS } from "@/types/permissions";

export default function AiAgentsPage() {
  return (
    <ProtectedPage permission={PERMISSIONS.AI_AGENTS}>
      <AiAgentsPageContent />
    </ProtectedPage>
  );
}
