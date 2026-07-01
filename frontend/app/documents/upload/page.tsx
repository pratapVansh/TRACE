import { UploadDocumentsPageContent } from "@/components/knowledge/upload/upload-documents-page-content";
import { ProtectedPage } from "@/components/layout/protected-page";
import { PERMISSIONS } from "@/types/permissions";

export default function UploadDocumentsPage() {
  return (
    <ProtectedPage permission={PERMISSIONS.DOCUMENTS_UPLOAD}>
      <UploadDocumentsPageContent />
    </ProtectedPage>
  );
}
