"use client";

import { useState } from "react";
import { X } from "lucide-react";
import type { GraphSelection, SelectedEdge, SelectedNode } from "@/types/knowledge-graph";
import { isEdgeSelection, isNodeSelection } from "@/types/knowledge-graph";
import { Badge } from "@/components/ui/badge";

type NodeDetailsPanelProps = {
  selection: GraphSelection;
  onClose: () => void;
  onExpand?: (entityId: string, depth: number) => void;
};

function NodeDetails({ node, onExpand }: { node: SelectedNode; onExpand?: (entityId: string, depth: number) => void }) {
  const [depth, setDepth] = useState(1);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-lg font-semibold text-foreground truncate">
          {node.label}
        </h3>
        <Badge variant="secondary" className="shrink-0">
          {node.entityType}
        </Badge>
      </div>

      <dl className="space-y-3 text-sm">
        <div>
          <dt className="text-muted-foreground text-xs uppercase tracking-wider">
            Entity ID
          </dt>
          <dd className="mt-0.5 font-mono text-xs text-foreground/70 break-all">
            {node.id}
          </dd>
        </div>

        <div>
          <dt className="text-muted-foreground text-xs uppercase tracking-wider">
            Source Document
          </dt>
          <dd className="mt-0.5 text-foreground/70 break-words">
            {node.sourceDocument || "N/A"}
          </dd>
        </div>

        <div>
          <dt className="text-muted-foreground text-xs uppercase tracking-wider">
            Connected Neighbors
          </dt>
          <dd className="mt-0.5 text-foreground">{node.neighbors}</dd>
        </div>
      </dl>

      {onExpand && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-xs text-muted-foreground uppercase tracking-wider">
              Traversal depth
            </label>
            <span className="text-xs font-medium text-foreground">{depth}</span>
          </div>
          <input
            type="range"
            min={1}
            max={3}
            value={depth}
            onChange={(e) => setDepth(Number(e.target.value))}
            className="w-full h-1.5 rounded-full appearance-none cursor-pointer bg-border accent-[var(--accent-steel)]"
          />
          <button
            onClick={() => onExpand(node.id, depth)}
            className="w-full rounded-lg border border-border bg-[var(--surface-secondary)] px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-border/50"
          >
            Expand neighbors (depth {depth})
          </button>
        </div>
      )}
    </div>
  );
}

function EdgeDetails({ edge }: { edge: SelectedEdge }) {
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-foreground truncate">
        {edge.relationshipType}
      </h3>

      <dl className="space-y-3 text-sm">
        <div>
          <dt className="text-muted-foreground text-xs uppercase tracking-wider">
            Type
          </dt>
          <dd className="mt-0.5">
            <Badge variant="secondary">{edge.relationshipType}</Badge>
          </dd>
        </div>

        <div>
          <dt className="text-muted-foreground text-xs uppercase tracking-wider">
            Source Entity
          </dt>
          <dd className="mt-0.5 font-mono text-xs text-foreground/70 break-all">
            {edge.from}
          </dd>
        </div>

        <div>
          <dt className="text-muted-foreground text-xs uppercase tracking-wider">
            Target Entity
          </dt>
          <dd className="mt-0.5 font-mono text-xs text-foreground/70 break-all">
            {edge.to}
          </dd>
        </div>

        <div>
          <dt className="text-muted-foreground text-xs uppercase tracking-wider">
            Relationship ID
          </dt>
          <dd className="mt-0.5 font-mono text-xs text-foreground/70 break-all">
            {edge.id}
          </dd>
        </div>
      </dl>
    </div>
  );
}

export function NodeDetailsPanel({
  selection,
  onClose,
  onExpand,
}: NodeDetailsPanelProps) {
  if (!selection) return null;

  return (
    <div className="industrial-card p-5 sm:p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="section-label">
          {isNodeSelection(selection) ? "Entity Details" : "Relationship Details"}
        </h2>
        <button
          onClick={onClose}
          className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-border/50 hover:text-foreground"
          aria-label="Close details"
        >
          <X size={16} />
        </button>
      </div>

      {isNodeSelection(selection) && (
        <NodeDetails node={selection} onExpand={onExpand} />
      )}
      {isEdgeSelection(selection) && <EdgeDetails edge={selection} />}
    </div>
  );
}
