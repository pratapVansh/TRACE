import { UsersPageContent } from "@/components/administration/users/users-page-content";
import { ProtectedPage } from "@/components/layout/protected-page";
import { PERMISSIONS } from "@/types/permissions";

export default function SettingsUsersPage() {
  return (
    <ProtectedPage permission={PERMISSIONS.SETTINGS}>
      <UsersPageContent />
    </ProtectedPage>
  );
}
