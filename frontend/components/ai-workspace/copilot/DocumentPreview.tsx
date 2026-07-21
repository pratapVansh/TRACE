"use client";

import React, { useState } from "react";
import { FileText, File, ExternalLink, X, Search } from "lucide-react";
import { cn } from "@/lib/utils";

interface DocumentData {
  document_name: string;
  chunk_content?: string;
  highlighted_excerpt?: string;
  page_number?: number;
  confidence?: number;
}

export function DocumentPreview({ data }: { data: string | DocumentData }) {
  const [isOpen, setIsOpen] = useState(false);
  
  let doc: DocumentData;
  try {
    doc = typeof data === "string" ? JSON.parse(data) : data;
  } catch (e) {
    return <div className="p-4 bg-red-500/10 text-red-400 border border-red-500/20 rounded-xl my-4 text-sm">Error parsing document data</div>;
  }

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
            <span className="font-semibold text-[var(--text-primary)]/90 truncate max-w-[200px] sm:max-w-[300px]">
              {doc.document_name}
            </span>
            {doc.page_number && (
              <span className="text-xs text-muted-foreground bg-[var(--bg-tertiary)] px-1.5 py-0.5 rounded">p.{doc.page_number}</span>
            )}
          </div>
          <ExternalLink className="size-4 text-muted-foreground" />
        </div>
        {doc.highlighted_excerpt && (
          <div 
            className="text-left text-sm text-foreground/80 line-clamp-2 w-full pl-6 [&>mark]:bg-[var(--accent)]/20 [&>mark]:text-[var(--accent)] [&>mark]:rounded-sm [&>mark]:px-0.5"
            dangerouslySetInnerHTML={{ __html: doc.highlighted_excerpt }}
          />
        )}
      </button>

      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--bg)]/80 backdrop-blur-sm p-4">
          <div className="relative w-full max-w-4xl max-h-[85vh] flex flex-col rounded-2xl border border-[var(--border)] bg-[var(--bg-secondary)] shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-[var(--accent-steel)]/10 px-6 py-4 bg-[var(--bg-secondary)]">
              <div className="flex items-center gap-3">
                {getDocIcon(doc.document_name)}
                <h3 className="font-semibold text-[var(--text-primary)]">{doc.document_name}</h3>
                {doc.page_number && <span className="text-sm text-muted-foreground">Page {doc.page_number}</span>}
                {doc.confidence && <span className="text-sm text-[var(--accent)]">Match: {(doc.confidence * 100).toFixed(0)}%</span>}
              </div>
              <button 
                onClick={() => setIsOpen(false)}
                className="p-1.5 rounded-md hover:bg-[var(--bg-tertiary)] text-muted-foreground hover:text-[var(--text-primary)] transition-colors"
              >
                <X className="size-5" />
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-6 bg-[var(--bg-secondary)]">
              <div className="flex items-center gap-2 mb-4 text-sm font-medium text-[var(--accent)]">
                <Search className="size-4" />
                Retrieved Context
              </div>
              <div 
                className="prose max-w-none text-foreground/90 leading-relaxed [&>mark]:bg-[var(--accent)]/20 [&>mark]:text-[var(--accent)] [&>mark]:rounded-sm [&>mark]:px-1 [&>mark]:font-medium whitespace-pre-wrap font-mono text-sm"
                dangerouslySetInnerHTML={{ __html: doc.highlighted_excerpt || doc.chunk_content || "No content preview available." }}
              />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
