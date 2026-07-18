export interface GraphNodeData {
  entityId: string;
  name: string;
  entityType: string;
  confidence: number;
  sourceDocument: string;
}

export interface GraphEdgeData {
  relationshipId: string;
  relationshipType: string;
  source: string;
  target: string;
  confidence: number;
}

export interface SelectedNode {
  id: string;
  label: string;
  entityType: string;
  confidence: number;
  sourceDocument: string;
  neighbors: number;
}

export interface SelectedEdge {
  id: string;
  from: string;
  to: string;
  relationshipType: string;
  confidence: number;
}

export type GraphSelection = SelectedNode | SelectedEdge | null;

export function isNodeSelection(
  sel: GraphSelection,
): sel is SelectedNode {
  return sel !== null && "entityType" in sel && "neighbors" in sel;
}

export function isEdgeSelection(
  sel: GraphSelection,
): sel is SelectedEdge {
  return sel !== null && "relationshipType" in sel && !("neighbors" in sel);
}

export const ENTITY_TYPE_COLORS: Record<string, string> = {
  Pump: "#3b82f6",
  Valve: "#ef4444",
  Compressor: "#06b6d4",
  Pipeline: "#f59e0b",
  Tank: "#22c55e",
  Instrument: "#8b5cf6",
  Motor: "#e11d48",
  "Heat Exchanger": "#f97316",
  Unit: "#14b8a6",
  Equipment: "#a855f7",
  Procedure: "#6366f1",
  Document: "#d946ef",
  Standard: "#84cc16",
  Chemical: "#ec4899",
  Location: "#0ea5e9",
  Failure: "#dc2626",
  Cause: "#facc15",
  Operator: "#10b981",
  Default: "#64748b",
};

export function getNodeColor(entityType: string): string {
  return ENTITY_TYPE_COLORS[entityType] ?? ENTITY_TYPE_COLORS.Default;
}
