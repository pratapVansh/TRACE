import { MaintenancePageContent } from "@/components/operations/maintenance/maintenance-page-content";
import { ProtectedPage } from "@/components/layout/protected-page";
import { PERMISSIONS } from "@/types/permissions";

export default function MaintenancePage() {
  return (
    <ProtectedPage permission={PERMISSIONS.MAINTENANCE}>
      <MaintenancePageContent />
    </ProtectedPage>
  );
}
