import { SearchPageContent } from "@/components/knowledge/search/search-page-content";
import { ProtectedPage } from "@/components/layout/protected-page";
import { PERMISSIONS } from "@/types/permissions";

export default function SearchPage() {
  return (
    <ProtectedPage permission={PERMISSIONS.SEARCH}>
      <SearchPageContent />
    </ProtectedPage>
  );
}
