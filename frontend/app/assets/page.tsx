import { AssetsPageContent } from "@/components/operations/assets/assets-page-content";
import { ProtectedPage } from "@/components/layout/protected-page";
import { PERMISSIONS } from "@/types/permissions";

export default function AssetsPage() {
  return (
    <ProtectedPage permission={PERMISSIONS.ASSETS_READ}>
      <AssetsPageContent />
    </ProtectedPage>
  );
}
