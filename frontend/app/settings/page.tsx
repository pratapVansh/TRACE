import { SystemSettingsPageContent } from "@/components/administration/settings/system-settings-page-content";
import { ProtectedPage } from "@/components/layout/protected-page";
import { PERMISSIONS } from "@/types/permissions";

export default function SettingsPage() {
  return (
    <ProtectedPage permission={PERMISSIONS.SETTINGS}>
      <SystemSettingsPageContent />
    </ProtectedPage>
  );
}
