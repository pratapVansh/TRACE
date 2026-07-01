import { AuditLogsPageContent } from "@/components/operations/audit/audit-logs-page-content";
import { ProtectedPage } from "@/components/layout/protected-page";
import { PERMISSIONS } from "@/types/permissions";

export default function AuditLogsPage() {
  return (
    <ProtectedPage permission={PERMISSIONS.COMPLIANCE}>
      <AuditLogsPageContent />
    </ProtectedPage>
  );
}
