import { DocumentsPageContent } from "@/components/knowledge/documents/documents-page-content";
import { ProtectedPage } from "@/components/layout/protected-page";
import { PERMISSIONS } from "@/types/permissions";

export default function DocumentsPage() {
  return (
    <ProtectedPage permission={PERMISSIONS.DOCUMENTS}>
      <DocumentsPageContent />
    </ProtectedPage>
  );
}
