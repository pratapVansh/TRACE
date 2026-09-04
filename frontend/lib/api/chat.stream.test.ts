import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * The Copilot's failure states are driven entirely by what `streamChatMessage`
 * reports, so these exercise the three ways a turn can go wrong against real
 * SSE frames: the server says `error`, retrieval finds nothing, and the
 * connection dies mid-answer.
 *
 * The last one matters most: tokens already delivered are real output, and a
 * truncated stream must still surface as a failure rather than passing a
 * half-answer off as complete.
 */

function encodeStream(frames: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const frame of frames) controller.enqueue(encoder.encode(frame));
      controller.close();
    },
  });
}

function sse(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

function stubBrowserGlobals() {
  const jar = new Map<string, string>();
  vi.stubGlobal("document", {
    get cookie(): string {
      return [...jar.entries()].map(([k, v]) => `${k}=${v}`).join("; ");
    },
    set cookie(raw: string) {
      const [pair] = raw.split(";");
      const eq = pair.indexOf("=");
      jar.set(pair.slice(0, eq).trim(), pair.slice(eq + 1));
    },
  });
  vi.stubGlobal("localStorage", {
    getItem: () => null,
    setItem: () => undefined,
    removeItem: () => undefined,
  });
  vi.stubGlobal("window", { location: { origin: "http://localhost:3000" } });
}

function stubFetch(frames: string[]) {
  const fetchMock = vi.fn(async () => ({
    ok: true,
    status: 200,
    body: encodeStream(frames),
  }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

type Recorded = {
  citations: { citations: unknown[]; sources: string[] }[];
  tokens: string[];
  done: unknown[];
  errors: string[];
  evidence: unknown[];
};

function recorder(): { calls: Recorded; callbacks: Record<string, unknown> } {
  const calls: Recorded = {
    citations: [], tokens: [], done: [], errors: [], evidence: [],
  };
  return {
    calls,
    callbacks: {
      onMeta: () => undefined,
      onCitations: (d: { citations: unknown[]; sources: string[] }) =>
        calls.citations.push(d),
      onToken: (t: string) => calls.tokens.push(t),
      onEvidence: (d: unknown) => calls.evidence.push(d),
      onDone: (d: unknown) => calls.done.push(d),
      onError: (m: string) => calls.errors.push(m),
    },
  };
}

beforeEach(() => {
  vi.resetModules();
  stubBrowserGlobals();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("streamChatMessage evidence event", () => {
  const payload = {
    classified_statements: [
      { text: "P-101 is a centrifugal pump.", classification: "FACT",
        evidence_refs: ["MAN-001.docx"] },
      { text: "It may run hotter in summer.", classification: "HYPOTHESIS",
        evidence_refs: [] },
    ],
    evidence: { fact_count: 1, hypothesis_count: 1, unknown_count: 0 },
  };

  it("delivers evidence before done", async () => {
    stubFetch([
      sse("citations", { citations: [], sources: [] }),
      sse("token", { token: "P-101 is a centrifugal pump." }),
      sse("evidence", payload),
      sse("done", { confidence: 0.71 }),
    ]);
    const { streamChatMessage } = await import("./chat");
    const { calls, callbacks } = recorder();

    await streamChatMessage({ question: "what is P-101?" }, callbacks);

    expect(calls.evidence).toEqual([payload]);
    expect(calls.done).toHaveLength(1);
  });

  it("still completes when the backend sends no evidence event", async () => {
    // An older backend, or a turn that produced nothing classifiable.
    stubFetch([
      sse("citations", { citations: [], sources: [] }),
      sse("token", { token: "..." }),
      sse("done", { confidence: 0.0 }),
    ]);
    const { streamChatMessage } = await import("./chat");
    const { calls, callbacks } = recorder();

    await expect(
      streamChatMessage({ question: "anything" }, callbacks),
    ).resolves.toBeUndefined();
    expect(calls.evidence).toHaveLength(0);
    expect(calls.done).toHaveLength(1);
  });
});

describe("streamChatMessage failure paths", () => {
  it("reports a server-sent error event without throwing", async () => {
    stubFetch([
      sse("meta", { conversation_id: "c1" }),
      sse("citations", { citations: [], sources: [] }),
      sse("error", { message: "LLM generation failed: upstream timeout" }),
    ]);
    const { streamChatMessage } = await import("./chat");
    const { calls, callbacks } = recorder();

    await expect(
      streamChatMessage({ question: "why did P-101 trip?" }, callbacks),
    ).resolves.toBeUndefined();

    expect(calls.errors).toEqual(["LLM generation failed: upstream timeout"]);
    expect(calls.done).toHaveLength(0);
  });

  it("delivers the no-results turn as empty citations plus the backend's message", async () => {
    // What rag_service.py emits when retrieval returns nothing.
    const message = "I could not find this information in the uploaded documents.";
    stubFetch([
      sse("citations", { citations: [], sources: [] }),
      sse("token", { token: message }),
      sse("done", { confidence: 0.0 }),
    ]);
    const { streamChatMessage } = await import("./chat");
    const { calls, callbacks } = recorder();

    await streamChatMessage({ question: "unrelated question" }, callbacks);

    expect(calls.citations[0]).toEqual({ citations: [], sources: [] });
    expect(calls.tokens.join("")).toBe(message);
    expect(calls.done).toEqual([{ confidence: 0 }]);
    expect(calls.errors).toHaveLength(0);
  });

  it("throws StreamIncompleteError when the stream ends before `done`", async () => {
    stubFetch([
      sse("citations", {
        citations: [{ document_name: "Pump-Manual-v3.pdf" }],
        sources: ["Pump-Manual-v3.pdf"],
      }),
      sse("token", { token: "The seal was " }),
      sse("token", { token: "replaced in" }),
      // connection drops here — no `done`, no `error`
    ]);
    const { streamChatMessage, StreamIncompleteError } = await import("./chat");
    const { calls, callbacks } = recorder();

    await expect(
      streamChatMessage({ question: "seal history?" }, callbacks),
    ).rejects.toBeInstanceOf(StreamIncompleteError);

    // The partial answer already delivered must survive the failure.
    expect(calls.tokens.join("")).toBe("The seal was replaced in");
    expect(calls.citations[0].sources).toEqual(["Pump-Manual-v3.pdf"]);
  });

  it("surfaces citations before any answer token", async () => {
    stubFetch([
      sse("citations", {
        citations: [{ document_name: "Inspection-2024.pdf" }],
        sources: ["Inspection-2024.pdf"],
      }),
      sse("token", { token: "Vessel V-2 " }),
      sse("done", { confidence: 0.87 }),
    ]);
    const { streamChatMessage } = await import("./chat");

    const order: string[] = [];
    await streamChatMessage(
      { question: "vessel status?" },
      {
        onCitations: () => order.push("citations"),
        onToken: () => order.push("token"),
        onDone: () => order.push("done"),
      },
    );

    expect(order).toEqual(["citations", "token", "done"]);
  });
});
