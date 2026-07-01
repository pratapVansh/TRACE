export function GraphPlaceholderCard() {
  const nodes = [
    { id: "n1", x: 50, y: 30, label: "P-4102", size: 12 },
    { id: "n2", x: 25, y: 55, label: "SOP-MNT-0088", size: 10 },
    { id: "n3", x: 75, y: 50, label: "WO-8842", size: 10 },
    { id: "n4", x: 40, y: 75, label: "Utilities", size: 8 },
    { id: "n5", x: 65, y: 22, label: "OISD-118", size: 9 },
    { id: "n6", x: 18, y: 28, label: "K-301", size: 11 },
    { id: "n7", x: 82, y: 78, label: "F-101", size: 10 },
  ];

  const edges = [
    ["n1", "n2"],
    ["n1", "n3"],
    ["n1", "n4"],
    ["n3", "n5"],
    ["n6", "n7"],
    ["n2", "n4"],
  ] as const;

  const nodeMap = Object.fromEntries(nodes.map((n) => [n.id, n]));

  return (
    <div className="industrial-card relative aspect-[16/10] min-h-[360px] overflow-hidden p-6">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(91,127,168,0.08),transparent_70%)]" />

      <div className="relative mb-4">
        <p className="section-label">Visualization</p>
        <h3 className="text-lg font-semibold text-white">Knowledge graph</h3>
      </div>

      <svg
        viewBox="0 0 100 100"
        className="relative h-full w-full"
        aria-hidden="true"
      >
        {edges.map(([from, to]) => {
          const a = nodeMap[from];
          const b = nodeMap[to];
          if (!a || !b) return null;
          return (
            <line
              key={`${from}-${to}`}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke="rgba(139,163,196,0.25)"
              strokeWidth="0.3"
            />
          );
        })}

        {nodes.map((node) => (
          <g key={node.id}>
            <circle
              cx={node.x}
              cy={node.y}
              r={node.size / 2}
              fill="rgba(17,24,39,0.9)"
              stroke="rgba(91,127,168,0.5)"
              strokeWidth="0.4"
            />
            <text
              x={node.x}
              y={node.y + node.size / 2 + 4}
              textAnchor="middle"
              fill="rgba(148,163,184,0.9)"
              fontSize="3"
            >
              {node.label}
            </text>
          </g>
        ))}
      </svg>

      <div className="absolute inset-0 flex items-center justify-center bg-[var(--surface)]/60 backdrop-blur-[1px]">
        <div className="rounded-xl border border-border bg-[var(--surface)]/95 px-6 py-4 text-center shadow-lg">
          <p className="text-sm font-medium text-white">Interactive graph preview</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Neo4j visualization coming in a future milestone
          </p>
        </div>
      </div>
    </div>
  );
}
