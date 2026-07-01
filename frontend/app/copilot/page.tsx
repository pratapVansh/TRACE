import { CopilotPageContent } from "@/components/ai-workspace/copilot/copilot-page-content";
import { ProtectedPage } from "@/components/layout/protected-page";
import { PERMISSIONS } from "@/types/permissions";

export default function CopilotPage() {
  return (
    <ProtectedPage permission={PERMISSIONS.COPILOT}>
      <CopilotPageContent />
    </ProtectedPage>
  );
}
