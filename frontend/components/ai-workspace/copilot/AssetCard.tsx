"use client";

import React, { useState } from "react";
import { Activity, MapPin, AlertCircle, Wrench, ShieldAlert, FileText, ChevronDown, ChevronUp, Share2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface AssetData {
  name: string;
  status: "Operational" | "Maintenance" | "Offline" | "Warning" | string;
  criticality: "High" | "Medium" | "Low" | string;
  location?: string;
  connected_assets?: string[];
  connected_incidents?: string[];
  maintenance_history?: { date: string; description: string }[];
  graph_relationships?: { type: string; target: string }[];
}

export function AssetCard({ data }: { data: string | AssetData }) {
  const [expanded, setExpanded] = useState(false);
  
  let asset: AssetData;
  try {
    asset = typeof data === "string" ? JSON.parse(data) : data;
  } catch (e) {
    return <div className="p-4 bg-red-500/10 text-red-400 border border-red-500/20 rounded-xl my-4 text-sm">Error parsing asset data: {data as string}</div>;
  }

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case "operational": return "text-emerald-400 bg-emerald-400/10 border-emerald-400/20";
      case "maintenance": return "text-blue-400 bg-blue-400/10 border-blue-400/20";
      case "warning": return "text-amber-400 bg-amber-400/10 border-amber-400/20";
      case "offline": return "text-red-400 bg-red-400/10 border-red-400/20";
      default: return "text-[var(--accent-steel)] bg-[var(--accent-steel)]/10 border-[var(--accent-steel)]/20";
    }
  };

  const getCriticalityColor = (crit: string) => {
    switch (crit?.toLowerCase()) {
      case "high": return "text-red-400";
      case "medium": return "text-amber-400";
      case "low": return "text-emerald-400";
      default: return "text-muted-foreground";
    }
  };

  return (
    <div className="my-5 rounded-xl border border-[var(--accent-steel)]/20 bg-[var(--surface-secondary)] shadow-sm overflow-hidden transition-industrial hover:border-[var(--accent-steel)]/40">
      <div className="p-5">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Activity className="size-5 text-[var(--accent-steel)]" />
              {asset.name || "Unknown Asset"}
            </h3>
            {asset.location && (
              <p className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
                <MapPin className="size-3.5" />
                {asset.location}
              </p>
            )}
          </div>
          <div className="flex flex-col items-end gap-2">
            {asset.status && (
              <span className={cn("px-2.5 py-1 text-xs font-medium rounded-md border", getStatusColor(asset.status))}>
                {asset.status.toUpperCase()}
              </span>
            )}
            {asset.criticality && (
              <span className="flex items-center gap-1.5 text-xs font-medium">
                <AlertCircle className={cn("size-3.5", getCriticalityColor(asset.criticality))} />
                <span className="text-muted-foreground">Criticality:</span>
                <span className={getCriticalityColor(asset.criticality)}>{asset.criticality}</span>
              </span>
            )}
          </div>
        </div>

        {(asset.connected_assets?.length || asset.connected_incidents?.length || asset.maintenance_history?.length || asset.graph_relationships?.length) ? (
          <>
            <button
              onClick={() => setExpanded(!expanded)}
              className="mt-4 flex w-full items-center justify-between rounded-lg bg-[var(--surface-tertiary)] px-4 py-2.5 text-sm font-medium text-white/80 transition-colors hover:bg-[var(--surface-tertiary)]/80"
            >
              <span>View Asset Details & Relationships</span>
              {expanded ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
            </button>

            {expanded && (
              <div className="mt-4 grid gap-6 sm:grid-cols-2 pt-2 border-t border-[var(--accent-steel)]/10">
                {/* Relationships */}
                {asset.graph_relationships && asset.graph_relationships.length > 0 && (
                  <div className="space-y-3">
                    <h4 className="flex items-center gap-2 text-sm font-medium text-white/90">
                      <Share2 className="size-4 text-indigo-400" />
                      Graph Relationships
                    </h4>
                    <ul className="space-y-2">
                      {asset.graph_relationships.map((rel, i) => (
                        <li key={i} className="flex items-center gap-2 text-xs">
                          <span className="px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">{rel.type}</span>
                          <span className="text-muted-foreground">→</span>
                          <span className="font-medium text-white/80">{rel.target}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Maintenance */}
                {asset.maintenance_history && asset.maintenance_history.length > 0 && (
                  <div className="space-y-3">
                    <h4 className="flex items-center gap-2 text-sm font-medium text-white/90">
                      <Wrench className="size-4 text-blue-400" />
                      Maintenance History
                    </h4>
                    <ul className="space-y-3 relative before:absolute before:inset-y-1 before:left-1.5 before:w-px before:bg-blue-500/20">
                      {asset.maintenance_history.map((record, i) => (
                        <li key={i} className="relative pl-5 text-xs">
                          <span className="absolute left-0.5 top-1 size-2 rounded-full bg-blue-500 ring-2 ring-[var(--surface-secondary)]" />
                          <div className="font-medium text-white/70 mb-0.5">{record.date}</div>
                          <div className="text-muted-foreground leading-relaxed">{record.description}</div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Connected Incidents */}
                {asset.connected_incidents && asset.connected_incidents.length > 0 && (
                  <div className="space-y-3">
                    <h4 className="flex items-center gap-2 text-sm font-medium text-white/90">
                      <ShieldAlert className="size-4 text-red-400" />
                      Related Incidents
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {asset.connected_incidents.map((inc, i) => (
                        <span key={i} className="inline-flex items-center gap-1.5 rounded-md bg-red-500/10 px-2 py-1 text-xs text-red-300 border border-red-500/20">
                          <ShieldAlert className="size-3" />
                          {inc}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Connected Assets */}
                {asset.connected_assets && asset.connected_assets.length > 0 && (
                  <div className="space-y-3">
                    <h4 className="flex items-center gap-2 text-sm font-medium text-white/90">
                      <Activity className="size-4 text-[var(--accent-steel)]" />
                      Connected Assets
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {asset.connected_assets.map((ca, i) => (
                        <span key={i} className="inline-flex items-center rounded-md bg-[var(--accent-steel)]/10 px-2 py-1 text-xs text-[var(--accent-steel-muted)] border border-[var(--accent-steel)]/20">
                          {ca}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        ) : null}
      </div>
    </div>
  );
}
