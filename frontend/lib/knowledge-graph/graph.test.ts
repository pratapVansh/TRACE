import { describe, expect, it, vi, beforeEach } from "vitest";

import { getNodeColor, isEdgeSelection, isNodeSelection } from "@/types/knowledge-graph";
import type { SelectedEdge, SelectedNode } from "@/types/knowledge-graph";

// ── getNodeColor ───────────────────────────────────────────

describe("getNodeColor", () => {
  it("returns blue for Pump", () => {
    expect(getNodeColor("Pump")).toBe("#3b82f6");
  });

  it("returns green for Tank", () => {
    expect(getNodeColor("Tank")).toBe("#22c55e");
  });

  it("returns red for Valve", () => {
    expect(getNodeColor("Valve")).toBe("#ef4444");
  });

  it("returns amber for Pipeline", () => {
    expect(getNodeColor("Pipeline")).toBe("#f59e0b");
  });

  it("returns purple for Instrument", () => {
    expect(getNodeColor("Instrument")).toBe("#8b5cf6");
  });

  it("returns slate for unknown types", () => {
    expect(getNodeColor("UnknownType")).toBe("#64748b");
    expect(getNodeColor("")).toBe("#64748b");
  });
});

// ── Selection type guards ──────────────────────────────────

describe("isNodeSelection", () => {
  it("returns true for a valid node selection", () => {
    const sel: SelectedNode = {
      id: "n1",
      label: "P-101",
      entityType: "Pump",
      confidence: 0.95,
      sourceDocument: "proc.pdf",
      neighbors: 3,
    };
    expect(isNodeSelection(sel)).toBe(true);
  });

  it("returns false for null", () => {
    expect(isNodeSelection(null)).toBe(false);
  });

  it("returns false for an edge selection", () => {
    const sel: SelectedEdge = {
      id: "e1",
      from: "n1",
      to: "n2",
      relationshipType: "CONNECTED_TO",
      confidence: 0.9,
    };
    expect(isNodeSelection(sel)).toBe(false);
  });
});

describe("isEdgeSelection", () => {
  it("returns true for a valid edge selection", () => {
    const sel: SelectedEdge = {
      id: "e1",
      from: "n1",
      to: "n2",
      relationshipType: "CONNECTED_TO",
      confidence: 0.9,
    };
    expect(isEdgeSelection(sel)).toBe(true);
  });

  it("returns false for null", () => {
    expect(isEdgeSelection(null)).toBe(false);
  });

  it("returns false for a node selection", () => {
    const sel: SelectedNode = {
      id: "n1",
      label: "P-101",
      entityType: "Pump",
      confidence: 0.95,
      sourceDocument: "proc.pdf",
      neighbors: 3,
    };
    expect(isEdgeSelection(sel)).toBe(false);
  });
});

// ── Graph API client ───────────────────────────────────────

describe("graph API client", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("fetchEntities builds correct URL", async () => {
    const mockGet = vi.fn().mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, total_items: 0, total_pages: 0, has_next: false, has_previous: false },
    });
    vi.doMock("@/lib/api/client", () => ({
      apiClient: { get: mockGet },
    }));

    const { fetchEntities } = await import("@/lib/api/graph");
    await fetchEntities(10, 50, "Pump");

    expect(mockGet).toHaveBeenCalledWith("/api/graph/entities", {
      params: { skip: 10, limit: 50, entity_type: "Pump" },
    });
  });

  it("fetchEntities without type omits entity_type", async () => {
    const mockGet = vi.fn().mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 100, total_items: 0, total_pages: 0, has_next: false, has_previous: false },
    });
    vi.doMock("@/lib/api/client", () => ({
      apiClient: { get: mockGet },
    }));

    const { fetchEntities } = await import("@/lib/api/graph");
    await fetchEntities(0, 100);

    expect(mockGet).toHaveBeenCalledWith("/api/graph/entities", {
      params: { skip: 0, limit: 100 },
    });
  });

  it("fetchEntity calls correct URL", async () => {
    const mockGet = vi.fn().mockResolvedValue({
      data: {
        id: "abc123", name: "P-101", type: "Pump",
        aliases: [], confidence: 0.95,
        document_id: "", chunk_id: "", source_document: "",
        updated_at: null,
      },
    });
    vi.doMock("@/lib/api/client", () => ({
      apiClient: { get: mockGet },
    }));

    const { fetchEntity } = await import("@/lib/api/graph");
    const result = await fetchEntity("abc123");

    expect(mockGet).toHaveBeenCalledWith("/api/graph/entity/abc123");
    expect(result.name).toBe("P-101");
    expect(result.type).toBe("Pump");
  });

  it("searchEntities builds correct URL", async () => {
    const mockGet = vi.fn().mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 20, total_items: 0, total_pages: 0, has_next: false, has_previous: false },
    });
    vi.doMock("@/lib/api/client", () => ({
      apiClient: { get: mockGet },
    }));

    const { searchEntities } = await import("@/lib/api/graph");
    await searchEntities("P-101", 0, 20);

    expect(mockGet).toHaveBeenCalledWith("/api/graph/search", {
      params: { q: "P-101", skip: 0, limit: 20 },
    });
  });

  it("fetchNeighbors with relTypes", async () => {
    const mockGet = vi.fn().mockResolvedValue({
      data: {
        entity: {
          id: "n1", name: "P-101", type: "Pump",
          aliases: [], confidence: 0.95,
          document_id: "", chunk_id: "", source_document: "",
          updated_at: null,
        },
        neighbors: [],
        total: 0,
      },
    });
    vi.doMock("@/lib/api/client", () => ({
      apiClient: { get: mockGet },
    }));

    const { fetchNeighbors } = await import("@/lib/api/graph");
    await fetchNeighbors("n1", 1, ["CONNECTED_TO", "INPUT_TO"]);

    expect(mockGet).toHaveBeenCalledWith("/api/graph/neighbors/n1", {
      params: { depth: 1, rel_types: "CONNECTED_TO,INPUT_TO" },
    });
  });

  it("findPath builds correct URL", async () => {
    const mockGet = vi.fn().mockResolvedValue({
      data: { segments: [], total_length: 0 },
    });
    vi.doMock("@/lib/api/client", () => ({
      apiClient: { get: mockGet },
    }));

    const { findPath } = await import("@/lib/api/graph");
    await findPath("src1", "tgt1", 4);

    expect(mockGet).toHaveBeenCalledWith("/api/graph/path", {
      params: { source: "src1", target: "tgt1", max_depth: 4 },
    });
  });

  it("fetchBatchNeighbors POSTs to batch endpoint", async () => {
    const mockPost = vi.fn().mockResolvedValue({
      data: {
        results: {
          n1: [
            {
              entity: { id: "n2", name: "T-101", type: "Tank", aliases: [], confidence: 0.9, document_id: "", chunk_id: "", source_document: "", updated_at: null },
              relationship: { id: "r1", type: "CONNECTED_TO", source: "n1", target: "n2", confidence: 0.95, document_id: "", chunk_id: "", source_document: "" },
              depth: 1,
            },
          ],
        },
      },
    });
    vi.doMock("@/lib/api/client", () => ({
      apiClient: { post: mockPost },
    }));

    const { fetchBatchNeighbors } = await import("@/lib/api/graph");
    const result = await fetchBatchNeighbors(["n1", "n2"], 1);

    expect(mockPost).toHaveBeenCalledWith("/api/graph/neighbors/batch", {
      entity_ids: ["n1", "n2"],
      depth: 1,
    });
    expect(result.n1).toHaveLength(1);
    expect(result.n1[0].entity.name).toBe("T-101");
  });

  it("fetchBatchNeighbors returns empty for no entities", async () => {
    const mockPost = vi.fn().mockResolvedValue({ data: { results: {} } });
    vi.doMock("@/lib/api/client", () => ({
      apiClient: { post: mockPost },
    }));

    const { fetchBatchNeighbors } = await import("@/lib/api/graph");
    const result = await fetchBatchNeighbors([], 1);

    expect(Object.keys(result)).toHaveLength(0);
  });
});
