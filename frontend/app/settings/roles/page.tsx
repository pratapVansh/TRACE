import { RolesPageContent } from "@/components/administration/roles/roles-page-content";
import { ProtectedPage } from "@/components/layout/protected-page";
import { PERMISSIONS } from "@/types/permissions";

export default function SettingsRolesPage() {
  return (
    <ProtectedPage permission={PERMISSIONS.SETTINGS}>
      <RolesPageContent />
    </ProtectedPage>
  );
}
