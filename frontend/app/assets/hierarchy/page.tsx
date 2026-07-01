import { AssetHierarchyPageContent } from "@/components/operations/assets/asset-hierarchy-page-content";
import { ProtectedPage } from "@/components/layout/protected-page";
import { PERMISSIONS } from "@/types/permissions";

export default function AssetHierarchyPage() {
  return (
    <ProtectedPage permission={PERMISSIONS.ASSETS}>
      <AssetHierarchyPageContent />
    </ProtectedPage>
  );
}
