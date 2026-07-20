"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { 
  AlertTriangle, FileText, ChevronRight 
} from "lucide-react";
import { cn } from "@/lib/utils";
import { AssetCard } from "./AssetCard";
import { DocumentPreview } from "./DocumentPreview";
import { KnowledgeGraphVis } from "./KnowledgeGraphVis";

// Helper to parse GitHub-style alerts in blockquotes
// e.g., > [!WARNING] or > [!RISK]
function parseAlert(text: string) {
  const match = text.match(/^\[!(WARNING|RISK|MAINTENANCE|RCA|EVIDENCE|TIMELINE|DOCUMENT|SOURCE|ASSUMPTION|ASSET|GRAPH)\]\s*([\s\S]*)$/i);
  if (match) {
    return { type: match[1].toLowerCase(), content: match[2] };
  }
  return null;
}

export function EnterpriseReportRenderer({ content }: { content: string }) {
  return (
    <div className="enterprise-report">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={{
          h1: ({ children }) => <h1 className="text-xl font-bold mt-8 mb-4 text-white border-b border-white/10 pb-2">{children}</h1>,
          h2: ({ children }) => <h2 className="text-lg font-semibold mt-6 mb-3 text-white/90">{children}</h2>,
          h3: ({ children }) => <h3 className="text-[15px] font-medium mt-5 mb-2 text-white/80">{children}</h3>,
          p: ({ children }) => <p className="leading-relaxed mb-4 text-foreground/90">{children}</p>,
          ul: ({ children, className }) => {
            if (className === "contains-task-list") {
              return <ul className="mb-4 space-y-2">{children}</ul>;
            }
            return <ul className="list-disc pl-5 mb-4 space-y-1.5 text-foreground/90 marker:text-[var(--accent-steel)]">{children}</ul>;
          },
          ol: ({ children }) => <ol className="list-decimal pl-5 mb-4 space-y-1.5 text-foreground/90 marker:text-[var(--accent-steel)] marker:font-medium">{children}</ol>,
          li: ({ children, className }) => {
            return <li className={cn("pl-1 leading-relaxed", className)}>{children}</li>;
          },
          table: ({ children }) => (
            <div className="w-full overflow-x-auto mb-6 rounded-xl border border-[var(--accent-steel)]/20 shadow-sm bg-[var(--surface-secondary)]">
              <table className="w-full text-sm text-left text-foreground/90 border-collapse">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-[var(--surface-tertiary)] border-b border-[var(--accent-steel)]/20 text-white/90 uppercase text-[11px] tracking-wider">{children}</thead>,
          tbody: ({ children }) => <tbody className="divide-y divide-border/20">{children}</tbody>,
          th: ({ children }) => <th className="px-4 py-3 font-semibold">{children}</th>,
          td: ({ children }) => <td className="px-4 py-3 align-top leading-relaxed">{children}</td>,
          blockquote: ({ children }) => {
            let text = "";
            React.Children.forEach(children, (child: React.ReactNode) => {
              if (typeof child === "string") text += child;
              else if (React.isValidElement(child) && child.props && (child.props as Record<string, unknown>).children) {
                const childProps = child.props as { children?: React.ReactNode };
                if (typeof childProps.children === "string") {
                  text += childProps.children;
                } else if (Array.isArray(childProps.children)) {
                  text += childProps.children.join("");
                }
              }
            });

            const alert = parseAlert(text.trim());
            if (alert) {
              let Icon = AlertTriangle;
              let bgColor = "bg-[var(--surface-tertiary)]";
              let borderColor = "border-[var(--accent-steel)]/30";
              let textColor = "text-[var(--accent-steel)]";
              const title = alert.type.toUpperCase();

              switch (alert.type) {
                case "warning":
                case "risk":
                  Icon = AlertTriangle;
                  bgColor = "bg-amber-500/10";
                  borderColor = "border-amber-500/30";
                  textColor = "text-amber-400";
                  break;
                case "document":
                case "source":
                  Icon = FileText;
                  textColor = "text-sky-400";
                  borderColor = "border-sky-500/30";
                  bgColor = "bg-sky-500/10";
                  break;
                case "asset":
                  return <AssetCard data={alert.content} />;
                case "graph":
                  return <KnowledgeGraphVis data={alert.content} />;
                default:
                  // Strip internal blocks (evidence, timeline, rca, maintenance, assumption)
                  // by rendering content as plain markdown without the alert box
                  return (
                    <div className="my-5">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>{alert.content}</ReactMarkdown>
                    </div>
                  );
              }

              if (alert.type === "document" || alert.type === "source") {
                return <DocumentPreview data={alert.content} />;
              }

              return (
                <div className={cn("my-5 rounded-xl border p-4 shadow-sm", bgColor, borderColor)}>
                  <div className="flex items-center gap-2 mb-2">
                    <Icon className={cn("size-4", textColor)} />
                    <span className={cn("text-xs font-bold tracking-wider", textColor)}>{title}</span>
                  </div>
                  <div className="text-[14px] text-foreground/90 prose-p:last:mb-0">
                    <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>{alert.content}</ReactMarkdown>
                  </div>
                </div>
              );
            }

            return (
              <blockquote className="border-l-2 border-[var(--accent-steel)]/50 pl-4 py-1 my-4 text-muted-foreground italic">
                {children}
              </blockquote>
            );
          },
          details: ({ children }) => (
            <details className="group my-4 rounded-xl border border-[var(--accent-steel)]/20 bg-[var(--surface-secondary)] open:bg-[var(--surface-tertiary)] open:border-[var(--accent-steel)]/40 transition-colors shadow-sm">
              {children}
            </details>
          ),
          summary: ({ children }) => (
            <summary className="flex cursor-pointer list-none items-center gap-3 p-4 font-medium text-white/90 [&::-webkit-details-marker]:hidden">
              <ChevronRight className="size-4 text-[var(--accent-steel-muted)] transition-transform group-open:rotate-90 shrink-0" />
              <div className="flex-1">{children}</div>
            </summary>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
