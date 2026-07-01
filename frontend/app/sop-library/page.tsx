import { SopLibraryPageContent } from "@/components/operations/sop/sop-library-page-content";
import { ProtectedPage } from "@/components/layout/protected-page";
import { PERMISSIONS } from "@/types/permissions";

export default function SopLibraryPage() {
  return (
    <ProtectedPage permission={PERMISSIONS.SOP_LIBRARY}>
      <SopLibraryPageContent />
    </ProtectedPage>
  );
}
