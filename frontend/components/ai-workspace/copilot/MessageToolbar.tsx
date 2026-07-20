"use client";

import React, { useState } from "react";
import { Check, Copy, Download, RefreshCcw } from "lucide-react";

interface MessageToolbarProps {
  content: string;
  onRegenerate?: () => void;
  isStreaming?: boolean;
}

export function MessageToolbar({ content, onRegenerate, isStreaming }: MessageToolbarProps) {
  const [copied, setCopied] = useState(false);
  const [exported, setExported] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleExport = () => {
    const blob = new Blob([content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Report_${new Date().toISOString().slice(0, 10)}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setExported(true);
    setTimeout(() => setExported(false), 2000);
  };

  if (isStreaming) return null;

  return (
    <div className="mt-4 flex items-center gap-2 border-t border-[var(--accent-steel)]/10 pt-3">
      <button
        onClick={handleCopy}
        className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-[var(--surface-tertiary)] hover:text-white transition-colors"
        title="Copy answer to clipboard"
      >
        {copied ? <Check className="size-3.5 text-emerald-400" /> : <Copy className="size-3.5" />}
        <span>{copied ? "Copied" : "Copy"}</span>
      </button>

      <button
        onClick={handleExport}
        className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-[var(--surface-tertiary)] hover:text-white transition-colors"
        title="Export as Markdown"
      >
        {exported ? <Check className="size-3.5 text-emerald-400" /> : <Download className="size-3.5" />}
        <span>Export</span>
      </button>

      {onRegenerate && (
        <button
          onClick={onRegenerate}
          className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-[var(--surface-tertiary)] hover:text-white transition-colors ml-auto"
          title="Regenerate response"
        >
          <RefreshCcw className="size-3.5" />
          <span>Regenerate</span>
        </button>
      )}
    </div>
  );
}
