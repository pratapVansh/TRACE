import { CompliancePageContent } from "@/components/operations/compliance/compliance-page-content";
import { ProtectedPage } from "@/components/layout/protected-page";
import { PERMISSIONS } from "@/types/permissions";

export default function CompliancePage() {
  return (
    <ProtectedPage permission={PERMISSIONS.COMPLIANCE}>
      <CompliancePageContent />
    </ProtectedPage>
  );
}
