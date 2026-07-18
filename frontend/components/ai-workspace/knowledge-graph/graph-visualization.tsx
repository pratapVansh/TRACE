"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";

import type { GraphSelection, SelectedEdge, SelectedNode } from "@/types/knowledge-graph";
import { getNodeColor } from "@/types/knowledge-graph";
import type { GraphEdgeData, GraphNodeData } from "@/types/knowledge-graph";

export interface GraphVisualizationHandle {
  zoomIn: () => void;
  zoomOut: () => void;
  fit: () => void;
  resetView: () => void;
}

type GraphVisualizationProps = {
  initialNodes: GraphNodeData[];
  initialEdges: GraphEdgeData[];
  onSelection: (sel: GraphSelection) => void;
  focusId?: string | null;
  onExpandNode?: (entityId: string, depth?: number) => void;
};

function toVisNode(n: GraphNodeData) {
  return {
    id: n.entityId,
    label: n.name,
    group: n.entityType,
    title: `${n.name} (${n.entityType})\nConfidence: ${(n.confidence * 100).toFixed(0)}%`,
    color: getNodeColor(n.entityType),
    borderWidth: 2,
    size: Math.max(12, Math.min(28, 14 + n.confidence * 10)),
  };
}

function toVisEdge(e: GraphEdgeData) {
  return {
    id: e.relationshipId || `${e.source}-${e.target}-${e.relationshipType}`,
    from: e.source,
    to: e.target,
    label: e.relationshipType,
    title: `${e.relationshipType}\nConfidence: ${(e.confidence * 100).toFixed(0) || "N/A"}`,
    width: 1.5,
    color: { color: "#475569", highlight: "#60a5fa", hover: "#60a5fa", opacity: 0.7 },
    font: { color: "#94a3b8", size: 10, face: "Geist Mono, monospace", strokeWidth: 0, align: "middle" },
    smooth: { type: "continuous" },
    arrows: { to: { enabled: true, scaleFactor: 0.6 } },
  };
}

export const GraphVisualization = forwardRef<GraphVisualizationHandle, GraphVisualizationProps>(
  function GraphVisualization(
    { initialNodes, initialEdges, onSelection, focusId, onExpandNode },
    ref,
  ) {
    const containerRef = useRef<HTMLDivElement>(null);
    const networkRef = useRef<unknown>(null);
    const nodesDataSetRef = useRef<unknown>(null);
    const edgesDataSetRef = useRef<unknown>(null);
    const dataRef = useRef({ nodes: initialNodes, edges: initialEdges });
    const onSelectionRef = useRef(onSelection);
    onSelectionRef.current = onSelection;
    const onExpandNodeRef = useRef(onExpandNode);
    onExpandNodeRef.current = onExpandNode;

    useImperativeHandle(ref, () => ({
      zoomIn() {
        (networkRef.current as any)?.zoomIn?.();
      },
      zoomOut() {
        (networkRef.current as any)?.zoomOut?.();
      },
      fit() {
        (networkRef.current as any)?.fit?.({ animation: true });
      },
      resetView() {
        const net = networkRef.current as any;
        if (net) {
          net.fit?.({ animation: true });
          net.moveTo?.({ scale: 1, position: { x: 0, y: 0 }, animation: true });
        }
      },
    }), []);

    useEffect(() => {
      let destroyed = false;

      async function init() {
        const visNetworkModule = await import("vis-network");
        const visDataModule = await import("vis-data");

        const { Network } = visNetworkModule;
        const { DataSet } = visDataModule;

        const container = containerRef.current;
        if (!container || destroyed) return;

        const nodes = new DataSet(initialNodes.map(toVisNode));
        const edges = new DataSet(initialEdges.map(toVisEdge));
        nodesDataSetRef.current = nodes;
        edgesDataSetRef.current = edges;

        const groups: Record<string, object> = {};
        for (const n of initialNodes) {
          if (!groups[n.entityType]) {
            groups[n.entityType] = { color: getNodeColor(n.entityType) };
          }
        }

        const network = new Network(
          container,
          { nodes, edges },
          {
            groups,
            nodes: {
              shape: "dot",
              size: 16,
              font: { color: "#e2e8f0", size: 12, face: "Geist, system-ui, sans-serif", strokeWidth: 0 },
              borderWidth: 2,
              shadow: { enabled: false },
            },
            edges: {
              width: 1.5,
              color: { color: "#475569", highlight: "#60a5fa", hover: "#60a5fa", opacity: 0.7 },
              font: { color: "#94a3b8", size: 10, face: "Geist Mono, monospace", strokeWidth: 0, align: "middle" },
              smooth: { type: "continuous" },
              arrows: { to: { enabled: true, scaleFactor: 0.6 } },
            },
            physics: {
              solver: "forceAtlas2Based",
              forceAtlas2Based: {
                gravitationalConstant: -40,
                centralGravity: 0.005,
                springLength: 180,
                springConstant: 0.02,
                damping: 0.4,
              },
              stabilization: { iterations: 200 },
              maxVelocity: 50,
            },
            interaction: {
              hover: true,
              tooltipDelay: 200,
              navigationButtons: false,
              keyboard: true,
              zoomView: true,
              dragView: true,
              multiselect: false,
            },
            layout: { improvedLayout: true },
          },
        );

        networkRef.current = network;

        network.on("click", ((params: unknown) => {
          const p = params as { nodes: string[]; edges: string[] };
          if (p.nodes.length > 0) {
            const nodeId = String(p.nodes[0]);
            const nodeData = dataRef.current.nodes.find((n) => n.entityId === nodeId);
            if (nodeData) {
              onSelectionRef.current({
                id: nodeId,
                label: nodeData.name,
                entityType: nodeData.entityType,
                confidence: nodeData.confidence,
                sourceDocument: nodeData.sourceDocument,
                neighbors: dataRef.current.edges.filter(
                  (e) => e.source === nodeId || e.target === nodeId,
                ).length,
              } as SelectedNode);
            }
          } else if (p.edges.length > 0) {
            const edgeId = String(p.edges[0]);
            const edgeData = dataRef.current.edges.find(
              (e) => e.relationshipId === edgeId || `${e.source}-${e.target}-${e.relationshipType}` === edgeId,
            );
            if (edgeData) {
              onSelectionRef.current({
                id: edgeId,
                from: edgeData.source,
                to: edgeData.target,
                relationshipType: edgeData.relationshipType,
                confidence: edgeData.confidence,
              } as SelectedEdge);
            }
          } else {
            onSelectionRef.current(null);
          }
        }) as (...args: unknown[]) => void);

        network.on("doubleClick", ((params: unknown) => {
          const p = params as { nodes: string[] };
          if (p.nodes.length > 0) {
            onExpandNodeRef.current?.(String(p.nodes[0]));
          }
        }) as (...args: unknown[]) => void);
      }

      init();

      return () => {
        destroyed = true;
        if (networkRef.current) {
          (networkRef.current as { destroy: () => void }).destroy();
          networkRef.current = null;
        }
      };
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
      const nds = nodesDataSetRef.current as any;
      const eds = edgesDataSetRef.current as any;
      if (!nds || !eds) return;

      const existingNodeIds = new Set(nds.getIds());
      const nodesToAdd = initialNodes
        .filter((n) => !existingNodeIds.has(n.entityId))
        .map(toVisNode);
      if (nodesToAdd.length > 0) nds.add(nodesToAdd);

      const existingEdgeIds = new Set(eds.getIds());
      const edgesToAdd = initialEdges
        .filter((e) => {
          const eid = e.relationshipId || `${e.source}-${e.target}-${e.relationshipType}`;
          return !existingEdgeIds.has(eid);
        })
        .map(toVisEdge);
      if (edgesToAdd.length > 0) eds.add(edgesToAdd);

      dataRef.current = { nodes: initialNodes, edges: initialEdges };
    }, [initialNodes, initialEdges]);

    useEffect(() => {
      if (focusId) {
        const net = networkRef.current as any;
        if (net) {
          net.focus?.(focusId, { scale: 1.8, animation: true });
          net.selectNodes?.([focusId]);
        }
      }
    }, [focusId]);

    return (
      <div
        ref={containerRef}
        className="h-full w-full"
        style={{ minHeight: "500px" }}
      />
    );
  },
);
