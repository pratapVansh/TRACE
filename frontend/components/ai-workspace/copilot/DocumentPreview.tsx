"use client";

import React, { useState } from "react";
import { FileText, File, ExternalLink, X, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Citation } from "@/types/chat";

interface DocumentData {
  document_name: string;
  chunk_content?: string;
  highlighted_excerpt?: string;
  page_number?: number;
  confidence?: number;
}

export function DocumentPreview({
  data,
  citations = [],
  onOpenDocument,
}: {
  data: string | DocumentData;
  /** This turn's citations, used to resolve the card's name to a document id. */
  citations?: Citation[];
  onOpenDocument?: (documentId: string) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  
  let doc: DocumentData;
  try {
    doc = typeof data === "string" ? JSON.parse(data) : data;
  } catch (e) {
    return <div className="p-4 bg-red-500/10 text-red-400 border border-red-500/20 rounded-xl my-4 text-sm">Error parsing document data</div>;
  }

  // The card names a document but never carries its id, so match it against
  // the turn's citations. Without this the ExternalLink below promised a source
  // it could not open, and the modal showed the retrieved chunk instead — the
  // same text the model was given.
  const documentId =
    citations.find((c) => c.document_name === doc.document_name)?.document_id ?? null;
  const canOpenSource = Boolean(documentId && onOpenDocument);

  const getDocIcon = (name: string) => {
    const ext = name.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'pdf': return <FileText className="size-4 text-red-400" />;
      case 'docx':
      case 'doc': return <FileText className="size-4 text-blue-400" />;
      case 'xlsx':
      case 'xls': return <FileText className="size-4 text-emerald-400" />;
      case 'pptx':
      case 'ppt': return <FileText className="size-4 text-orange-400" />;
      default: return <File className="size-4 text-sky-400" />;
    }
  };

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        className="my-5 flex w-full flex-col items-start rounded-xl border border-[var(--accent-steel)]/20 bg-[var(--surface-secondary)] p-4 shadow-sm transition-industrial hover:border-[var(--accent-steel)]/40 hover:bg-[var(--surface-tertiary)]"
      >
        <div className="flex w-full items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            {getDocIcon(doc.document_name)}
            <span className="font-semibold text-foreground/90 truncate max-w-[200px] sm:max-w-[300px]">
              {doc.document_name}
            </span>
            {doc.page_number && (
              <span className="text-xs text-muted-foreground bg-[var(--surface)]/5 px-1.5 py-0.5 rounded">p.{doc.page_number}</span>
            )}
          </div>
          {canOpenSource ? (
            <ExternalLink className="size-4 text-muted-foreground" />
          ) : null}
        </div>
        {doc.highlighted_excerpt && (
          <div 
            className="text-left text-sm text-foreground/80 line-clamp-2 w-full pl-6 [&>mark]:bg-sky-500/20 [&>mark]:text-sky-300 [&>mark]:rounded-sm [&>mark]:px-0.5"
            dangerouslySetInnerHTML={{ __html: doc.highlighted_excerpt }}
          />
        )}
      </button>

      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="relative w-full max-w-4xl max-h-[85vh] flex flex-col rounded-2xl border border-[var(--accent-steel)]/20 bg-[var(--surface-primary)] shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-[var(--accent-steel)]/10 px-6 py-4 bg-[var(--surface-secondary)]">
              <div className="flex items-center gap-3">
                {getDocIcon(doc.document_name)}
                <h3 className="font-semibold text-foreground">{doc.document_name}</h3>
                {doc.page_number && <span className="text-sm text-muted-foreground">Page {doc.page_number}</span>}
                {doc.confidence && <span className="text-sm text-sky-400">Match: {(doc.confidence * 100).toFixed(0)}%</span>}
              </div>
              <div className="flex items-center gap-2">
              {canOpenSource ? (
                <button
                  type="button"
                  onClick={() => {
                    setIsOpen(false);
                    onOpenDocument!(documentId!);
                  }}
                  className="inline-flex items-center gap-1.5 rounded-md border border-[var(--accent-steel)]/30 px-2 py-1 text-xs font-medium text-foreground/80 transition-colors hover:border-[var(--accent-steel)]/60 hover:text-foreground"
                >
                  <ExternalLink className="size-3.5" />
                  Open source document
                </button>
              ) : null}
              <button 
                onClick={() => setIsOpen(false)}
                className="p-1.5 rounded-md hover:bg-[var(--surface)]/10 text-muted-foreground hover:text-foreground transition-colors"
              >
                <X className="size-5" />
              </button>
              </div>
            </div>
            
            <div className="flex-1 overflow-y-auto p-6 bg-[var(--surface-primary)]">
              <div className="flex items-center gap-2 mb-4 text-sm font-medium text-sky-400">
                <Search className="size-4" />
                Retrieved Context
              </div>
              {doc.highlighted_excerpt ? (
                // Server-escaped, with <mark> added around query terms.
                <div
                  className="prose dark:prose-invert max-w-none text-foreground/90 leading-relaxed [&>mark]:bg-sky-500/20 [&>mark]:text-sky-300 [&>mark]:rounded-sm [&>mark]:px-1 [&>mark]:font-medium whitespace-pre-wrap font-mono text-sm"
                  dangerouslySetInnerHTML={{ __html: doc.highlighted_excerpt }}
                />
              ) : (
                // Raw document text: render as text, never as HTML.
                <div className="prose dark:prose-invert max-w-none text-foreground/90 leading-relaxed whitespace-pre-wrap font-mono text-sm">
                  {doc.chunk_content || "No content preview available."}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
