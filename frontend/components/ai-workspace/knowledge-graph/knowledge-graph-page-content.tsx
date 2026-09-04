"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, Loader2, Network } from "lucide-react";
import { isAxiosError } from "axios";

import { GraphVisualization, type GraphVisualizationHandle } from "@/components/ai-workspace/knowledge-graph/graph-visualization";
import { GraphToolbar } from "@/components/ai-workspace/knowledge-graph/graph-toolbar";
import { GraphInfoPanel } from "@/components/ai-workspace/knowledge-graph/graph-info-panel";
import { NodeDetailsPanel } from "@/components/ai-workspace/knowledge-graph/node-details-panel";
import { PageHeader } from "@/components/common/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchBatchNeighbors, fetchEntities, fetchGraphSchema, fetchGraphStatistics, fetchNeighbors } from "@/lib/api/graph";
import type { GraphSchema } from "@/lib/api/graph";
import { getApiErrorMessage } from "@/lib/api/errors";
import type { EntityResponse } from "@/lib/api/graph";
import type {
  GraphEdgeData,
  GraphNodeData,
  GraphSelection,
  SelectedNode,
} from "@/types/knowledge-graph";
import { StatCard } from "@/components/operations/stat-card";

async function getGraphErrorMessage(err: unknown): Promise<string> {
  const msg = await getApiErrorMessage(err, "");
  if (msg) return msg;
  if (isAxiosError(err)) {
    const status = err.response?.status;
    if (status === 401) return "Your session has expired. Please log in again.";
    if (status === 403) return "Access denied. You don't have permission to view the knowledge graph.";
    if (status === 404) return "The requested data could not be found.";
    if (status === 500) return "The server encountered an internal error. Please try again later.";
    if (status) return `Request failed (status ${status}). Please try again.`;
  }
  return "An unexpected error occurred. Please try again.";
}

const PAGE_SIZE = 50;

export function KnowledgeGraphPageContent() {
  const [nodes, setNodes] = useState<GraphNodeData[]>([]);
  const [edges, setEdges] = useState<GraphEdgeData[]>([]);
  const [selection, setSelection] = useState<GraphSelection>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState({ entities: 0, relationships: 0, documents: 0 });
  const [focusId, setFocusId] = useState<string | null>(null);
  const [loadKey, setLoadKey] = useState(0);
  const [schema, setSchema] = useState<GraphSchema | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const graphRef = useRef<GraphVisualizationHandle>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const entityData = await fetchEntities(0, PAGE_SIZE);
        if (cancelled) return;

        const allNodes: GraphNodeData[] = [];
        const allEdges: GraphEdgeData[] = [];
        const seenNodes = new Set<string>();
        const seenEdges = new Set<string>();

        for (const entity of entityData.items) {
          if (!seenNodes.has(entity.id)) {
            seenNodes.add(entity.id);
            allNodes.push({
              entityId: entity.id,
              name: entity.name,
              entityType: entity.type,
              confidence: entity.confidence,
              sourceDocument: entity.source_document,
            });
          }
        }

        const entityIds = entityData.items.map((e) => e.id);
        if (entityIds.length > 0) {
          try {
            const batchResults = await fetchBatchNeighbors(entityIds, 1);
            if (cancelled) return;

            for (const [, neighbors] of Object.entries(batchResults)) {
              for (const nbr of neighbors) {
                if (!seenNodes.has(nbr.entity.id)) {
                  seenNodes.add(nbr.entity.id);
                  allNodes.push({
                    entityId: nbr.entity.id,
                    name: nbr.entity.name,
                    entityType: nbr.entity.type,
                    confidence: nbr.entity.confidence,
                    sourceDocument: nbr.entity.source_document,
                  });
                }

                const eid =
                  nbr.relationship.id ||
                  `${nbr.relationship.source}-${nbr.relationship.target}-${nbr.relationship.type}`;
                if (!seenEdges.has(eid)) {
                  seenEdges.add(eid);
                  allEdges.push({
                    relationshipId: eid,
                    relationshipType: nbr.relationship.type,
                    source: nbr.relationship.source,
                    target: nbr.relationship.target,
                    confidence: nbr.relationship.confidence,
                  });
                }
              }
            }
          } catch (err) {
            if (!cancelled) {
              const msg = await getApiErrorMessage(err, "Failed to load neighbor relationships.");
              setError(msg);
            }
          }
        }

        if (!cancelled) {
          setNodes(allNodes);
          setEdges(allEdges);
          setHasMore(entityData.has_next);
        }

        // Fetch authoritative statistics and schema from the backend
        if (!cancelled) {
          try {
            const [graphStats, graphSchema] = await Promise.all([
              fetchGraphStatistics(),
              fetchGraphSchema(),
            ]);
            if (!cancelled) {
              setSchema(graphSchema);
              setStats({
                entities: graphStats.total_entities,
                relationships: graphStats.total_relationships,
                documents: graphStats.total_documents,
              });
            }
          } catch {
            if (!cancelled) {
              setSchema(null);
            }
            // Fall back to client-side computation from loaded data
            if (!cancelled) {
              setStats({
                entities: allNodes.length,
                relationships: allEdges.length,
                documents: new Set(allNodes.map((n) => n.sourceDocument).filter(Boolean)).size,
              });
            }
          }
        }
      } catch (err) {
        if (!cancelled) {
          const msg = await getGraphErrorMessage(err);
          setError(msg);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [loadKey]);

  const handleSelection = useCallback((sel: GraphSelection) => {
    setSelection(sel);
  }, []);

  const handleSearchResult = useCallback((entityId: string) => {
    setFocusId(entityId);
  }, []);

  const handleAddEntity = useCallback(
    (entity: EntityResponse) => {
      setError(null);
      const exists = nodes.some((n) => n.entityId === entity.id);
      if (exists) return;

      setFocusId(entity.id);
      setNodes((prev) => [
        ...prev,
        {
          entityId: entity.id,
          name: entity.name,
          entityType: entity.type,
          confidence: entity.confidence,
          sourceDocument: entity.source_document,
        },
      ]);
    },
    [nodes],
  );

  const handleExpand = useCallback(
    async (entityId: string, depth: number = 1) => {
      try {
        setError(null);
        const result = await fetchNeighbors(entityId, depth);
        setNodes((prev) => {
          const existing = new Set(prev.map((n) => n.entityId));
          const added: GraphNodeData[] = [];
          if (!existing.has(result.entity.id)) {
            added.push({
              entityId: result.entity.id,
              name: result.entity.name,
              entityType: result.entity.type,
              confidence: result.entity.confidence,
              sourceDocument: result.entity.source_document,
            });
          }
          for (const nbr of result.neighbors) {
            if (!existing.has(nbr.entity.id)) {
              added.push({
                entityId: nbr.entity.id,
                name: nbr.entity.name,
                entityType: nbr.entity.type,
                confidence: nbr.entity.confidence,
                sourceDocument: nbr.entity.source_document,
              });
            }
          }
          return [...prev, ...added];
        });

        setEdges((prev) => {
          const existing = new Set(prev.map((e) => e.relationshipId));
          const added: GraphEdgeData[] = [];
          for (const nbr of result.neighbors) {
            const eid =
              nbr.relationship.id ||
              `${nbr.relationship.source}-${nbr.relationship.target}-${nbr.relationship.type}`;
            if (!existing.has(eid)) {
              added.push({
                relationshipId: eid,
                relationshipType: nbr.relationship.type,
                source: nbr.relationship.source,
                target: nbr.relationship.target,
                confidence: nbr.relationship.confidence,
              });
            }
          }
          return [...prev, ...added];
        });
      } catch (err) {
        const msg = await getApiErrorMessage(err, "Failed to expand node. Please try again.");
        setError(msg);
      }
    },
    [],
  );

  const handleLoadMore = useCallback(async () => {
    setLoadingMore(true);
    setError(null);
    try {
      const entityData = await fetchEntities(nodes.length, PAGE_SIZE);

      const newNodes: GraphNodeData[] = [];
      const newEdges: GraphEdgeData[] = [];
      const existingNodeIds = new Set(nodes.map((n) => n.entityId));
      const existingEdgeIds = new Set(edges.map((e) => e.relationshipId));

      for (const entity of entityData.items) {
        if (!existingNodeIds.has(entity.id)) {
          existingNodeIds.add(entity.id);
          newNodes.push({
            entityId: entity.id,
            name: entity.name,
            entityType: entity.type,
            confidence: entity.confidence,
            sourceDocument: entity.source_document,
          });
        }
      }

      const newEntityIds = entityData.items.map((e) => e.id);
      if (newEntityIds.length > 0) {
        const batchResults = await fetchBatchNeighbors(newEntityIds, 1);
        for (const [, neighbors] of Object.entries(batchResults)) {
          for (const nbr of neighbors) {
            if (!existingNodeIds.has(nbr.entity.id)) {
              existingNodeIds.add(nbr.entity.id);
              newNodes.push({
                entityId: nbr.entity.id,
                name: nbr.entity.name,
                entityType: nbr.entity.type,
                confidence: nbr.entity.confidence,
                sourceDocument: nbr.entity.source_document,
              });
            }

            const eid =
              nbr.relationship.id ||
              `${nbr.relationship.source}-${nbr.relationship.target}-${nbr.relationship.type}`;
            if (!existingEdgeIds.has(eid)) {
              existingEdgeIds.add(eid);
              newEdges.push({
                relationshipId: eid,
                relationshipType: nbr.relationship.type,
                source: nbr.relationship.source,
                target: nbr.relationship.target,
                confidence: nbr.relationship.confidence,
              });
            }
          }
        }
      }

      setNodes((prev) => [...prev, ...newNodes]);
      setEdges((prev) => [...prev, ...newEdges]);
      setHasMore(entityData.has_next);
    } catch (err) {
      const msg = await getApiErrorMessage(err, "Failed to load more entities.");
      setError(msg);
    } finally {
      setLoadingMore(false);
    }
  }, [nodes, edges]);

  const handleZoomIn = useCallback(() => graphRef.current?.zoomIn(), []);
  const handleZoomOut = useCallback(() => graphRef.current?.zoomOut(), []);
  const handleReset = useCallback(() => graphRef.current?.resetView(), []);

  const handleCloseDetails = useCallback(() => {
    setSelection(null);
  }, []);

  const handleDismissError = useCallback(() => {
    setError(null);
  }, []);

  const statItems = useMemo(
    () => [
      { label: "Entities", value: String(stats.entities) },
      { label: "Relationships", value: String(stats.relationships) },
      { label: "Documents", value: String(stats.documents) },
    ],
    [stats],
  );

  if (loading) {
    return (
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
        <PageHeader
          sectionLabel="AI Workspace"
          title="Knowledge Graph"
          description="Explore relationships between assets, procedures, incidents, and compliance standards across the facility."
        />
        <Skeleton className="h-[600px] w-full rounded-xl" />
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
      <PageHeader
        sectionLabel="AI Workspace"
        title="Knowledge Graph"
        description="Explore relationships between assets, procedures, incidents, and compliance standards across the facility."
      />

      {error && nodes.length === 0 && (
        <div className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400">
          <AlertCircle size={18} className="shrink-0" />
          <p className="flex-1">{error}</p>
          <button
            onClick={() => setLoadKey((k) => k + 1)}
            className="shrink-0 rounded-md bg-red-500/20 px-3 py-1.5 font-medium text-red-400 transition-colors hover:bg-red-500/30"
          >
            Retry
          </button>
        </div>
      )}

      {error && nodes.length > 0 && (
        <div className="flex items-center gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-400">
          <AlertCircle size={18} className="shrink-0" />
          <p className="flex-1">{error}</p>
          <button
            onClick={handleDismissError}
            className="shrink-0 rounded-md bg-amber-500/20 px-3 py-1.5 font-medium text-amber-400 transition-colors hover:bg-amber-500/30"
          >
            Dismiss
          </button>
        </div>
      )}

      <GraphToolbar
        onSearchResult={handleSearchResult}
        onAddEntity={handleAddEntity}
        onZoomIn={handleZoomIn}
        onZoomOut={handleZoomOut}
        onReset={handleReset}
      />

      <div className="grid gap-6 xl:grid-cols-12">
        <div className="xl:col-span-8">
          <div className="industrial-card overflow-hidden p-0">
            <div className="aspect-[16/10] w-full min-h-[500px]">
              {nodes.length > 0 ? (
                <GraphVisualization
                  ref={graphRef}
                  initialNodes={nodes}
                  initialEdges={edges}
                  onSelection={handleSelection}
                  focusId={focusId}
                  onExpandNode={handleExpand}
                />
              ) : (
                <div className="flex h-full min-h-[500px] items-center justify-center p-8">
                  <div className="max-w-sm text-center">
                    <Network
                      size={48}
                      className="mx-auto text-muted-foreground/40"
                    />
                    <p className="mt-4 text-sm text-muted-foreground">
                      No entities found. Upload documents and process assets to
                      generate the knowledge graph.
                    </p>
                  </div>
                </div>
              )}
            </div>
            {hasMore && nodes.length > 0 && (
              <div className="flex items-center justify-center border-t border-border px-4 py-3">
                <button
                  onClick={handleLoadMore}
                  disabled={loadingMore}
                  className="inline-flex items-center gap-2 rounded-lg border border-border bg-[var(--surface-secondary)] px-4 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-border/50 hover:text-foreground disabled:opacity-50"
                >
                  {loadingMore && <Loader2 size={14} className="animate-spin" />}
                  {loadingMore ? "Loading..." : "Load More Entities"}
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="xl:col-span-4 space-y-6">
          <div className="grid gap-4 sm:grid-cols-3 xl:grid-cols-1">
            {statItems.map((s) => (
              <StatCard key={s.label} label={s.label} value={s.value} icon={Network} />
            ))}
          </div>

          {selection ? (
            <NodeDetailsPanel
              selection={selection}
              onClose={handleCloseDetails}
              onExpand={
                selection && "neighbors" in selection
                  ? (id, depth) => handleExpand(id, depth)
                  : undefined
              }
            />
          ) : schema ? (
            <GraphInfoPanel
              stats={schema.labels.map((l) => ({
                label: l.label,
                value: String(l.count),
              }))}
              items={schema.relationship_types.map((rt) => ({
                id: rt.type,
                label: rt.type,
                description: `${rt.count} occurrence${rt.count === 1 ? "" : "s"}`,
              }))}
            />
          ) : (
            <div className="industrial-card p-5 sm:p-6">
              <div className="flex items-center justify-center py-8">
                <div className="size-5 animate-spin rounded-full border-2 border-[var(--accent-steel)] border-t-transparent" />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
