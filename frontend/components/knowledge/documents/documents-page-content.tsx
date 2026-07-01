"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { DocumentTable } from "@/components/knowledge/documents/document-table";
import {
  DEFAULT_FILTERS,
  KnowledgeFilters,
} from "@/components/knowledge/knowledge-filters";
import { KnowledgePageHeader } from "@/components/knowledge/knowledge-page-header";
import { KnowledgeSearchBar } from "@/components/knowledge/knowledge-search-bar";
import {
  DEPARTMENTS,
  DOCUMENT_STATUSES,
  DOCUMENT_STATUS_LABELS,
  DOCUMENT_TYPES,
} from "@/lib/knowledge/constants";
import { KNOWLEDGE_DOCUMENTS } from "@/lib/knowledge/mock-data";
import { filterDocuments } from "@/lib/knowledge/utils";
import { APP_ROUTES } from "@/lib/auth/routes";

export function DocumentsPageContent() {
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState(DEFAULT_FILTERS);

  const filteredDocuments = useMemo(
    () => filterDocuments(KNOWLEDGE_DOCUMENTS, query, filters),
    [query, filters],
  );

  const typeOptions = [
    { value: "all", label: "All types" },
    ...DOCUMENT_TYPES.map((type) => ({ value: type, label: type })),
  ];

  const statusOptions = [
    { value: "all", label: "All statuses" },
    ...DOCUMENT_STATUSES.map((status) => ({
      value: status,
      label: DOCUMENT_STATUS_LABELS[status],
    })),
  ];

  const departmentOptions = [
    { value: "all", label: "All departments" },
    ...DEPARTMENTS.map((department) => ({
      value: department,
      label: department,
    })),
  ];

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
      <KnowledgePageHeader
        sectionLabel="Knowledge Management"
        title="Documents"
        description="Browse, filter, and manage technical records, SOPs, inspection reports, and engineering documentation across Northfield Refinery Complex."
        action={
          <Link
            href={APP_ROUTES.documentsUpload}
            className="inline-flex h-10 items-center rounded-xl bg-[var(--accent-steel)] px-4 text-sm font-medium text-white transition-industrial hover:bg-[#6a8eb5]"
          >
            Upload Documents
          </Link>
        }
      />

      <KnowledgeSearchBar value={query} onChange={setQuery} />

      <KnowledgeFilters
        filters={filters}
        onChange={setFilters}
        typeOptions={typeOptions}
        statusOptions={statusOptions}
        departmentOptions={departmentOptions}
      />

      <DocumentTable documents={filteredDocuments} />
    </div>
  );
}
