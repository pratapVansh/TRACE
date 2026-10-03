import { Suspense } from "react";

import { SearchPageContent } from "@/components/knowledge/search/search-page-content";
import { ProtectedPage } from "@/components/layout/protected-page";
import { Skeleton } from "@/components/ui/skeleton";
import { PERMISSIONS } from "@/types/permissions";

export default function SearchPage() {
  return (
    <ProtectedPage permission={PERMISSIONS.SEARCH}>
      <Suspense fallback={<Skeleton className="h-32 w-full rounded-md" />}>
        <SearchPageContent />
      </Suspense>
    </ProtectedPage>
  );
}
