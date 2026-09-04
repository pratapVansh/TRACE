"use client";

import React, { useEffect, useRef, useState } from "react";
import { Maximize2, Network, Search, X } from "lucide-react";

interface Node {
  id: string;
  label: string;
  group: string;
}

interface Edge {
  source: string;
  target: string;
  label: string;
}

interface GraphData {
  nodes: Node[];
  edges: Edge[];
}

export function KnowledgeGraphVis({ data }: { data: string | GraphData }) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  
  let graphData: GraphData;
  try {
    graphData = typeof data === "string" ? JSON.parse(data) : data;
  } catch (e) {
    return <div className="p-4 bg-red-500/10 text-red-400 border border-red-500/20 rounded-xl my-4 text-sm">Error parsing graph data</div>;
  }

  // A very simplified static visualization of the graph since we can't easily embed a complex force-directed graph library like D3 here without external dependencies. 
  // In a real application, we'd use vis-network, react-force-graph, or cytoscape.
  
  const GraphContent = () => (
    <div className="flex-1 w-full h-full min-h-[300px] bg-[var(--surface-primary)] relative rounded-xl border border-[var(--accent-steel)]/10 p-4 overflow-hidden flex items-center justify-center">
      <div className="absolute inset-0 opacity-[0.03] pointer-events-none" style={{ backgroundImage: 'radial-gradient(circle at 2px 2px, white 1px, transparent 0)', backgroundSize: '24px 24px' }}></div>
      
      {/* Simplified CSS-based Layout for demonstration */}
      <div className="relative w-full max-w-2xl aspect-video flex items-center justify-center">
        {graphData.nodes.length > 0 && (
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10 flex flex-col items-center group cursor-pointer">
            <div className="size-12 rounded-full bg-indigo-500/20 border-2 border-indigo-500/50 shadow-[0_0_15px_rgba(99,102,241,0.2)] flex items-center justify-center transition-transform group-hover:scale-110 group-hover:bg-indigo-500/30">
               <Network className="size-5 text-indigo-300" />
            </div>
            <span className="mt-2 px-2 py-1 bg-[var(--surface-tertiary)] border border-border rounded-md text-xs font-medium text-foreground shadow-lg whitespace-nowrap">
              {graphData.nodes[0].label}
            </span>
          </div>
        )}
        
        {/* Render satellite nodes around the center */}
        {graphData.nodes.slice(1).map((node, i) => {
          const angle = (i / (graphData.nodes.length - 1)) * Math.PI * 2;
          const radius = 120 + Math.random() * 40;
          const x = Math.cos(angle) * radius;
          const y = Math.sin(angle) * radius;
          
          return (
            <div key={node.id} className="absolute top-1/2 left-1/2 z-10 flex flex-col items-center group cursor-pointer" style={{ transform: `translate(calc(-50% + ${x}px), calc(-50% + ${y}px))` }}>
              <div className="size-8 rounded-full bg-sky-500/20 border border-sky-500/50 shadow-[0_0_10px_rgba(14,165,233,0.1)] transition-transform group-hover:scale-110 group-hover:bg-sky-500/30"></div>
              <span className="mt-1 px-1.5 py-0.5 bg-[var(--surface-tertiary)] border border-border rounded text-[10px] font-medium text-foreground/90 shadow-lg whitespace-nowrap">
                {node.label}
              </span>
            </div>
          );
        })}
        
        {/* Draw SVG lines for edges */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none">
           {/* In a real implementation we would calculate exact coordinates based on node positions */}
           {/* Here we just show a representative connected visual */}
           {graphData.edges.slice(0, Math.min(graphData.edges.length, 10)).map((edge, i) => {
               const angle = (i / (graphData.edges.length)) * Math.PI * 2;
               const radius = 120;
               const x = Math.cos(angle) * radius;
               const y = Math.sin(angle) * radius;
               
               return (
                 <g key={i}>
                   <line x1="50%" y1="50%" x2={`calc(50% + ${x}px)`} y2={`calc(50% + ${y}px)`} stroke="rgba(99, 102, 241, 0.3)" strokeWidth="1" strokeDasharray="4 2" />
                   {edge.label && (
                      <text x={`calc(50% + ${x/2}px)`} y={`calc(50% + ${y/2}px - 5px)`} fill="rgba(255, 255, 255, 0.5)" fontSize="9" textAnchor="middle" transform={`rotate(${angle * 180 / Math.PI}, calc(50% + ${x/2}px), calc(50% + ${y/2}px))`}>
                        {edge.label}
                      </text>
                   )}
                 </g>
               )
           })}
        </svg>
      </div>
      
      <div className="absolute top-4 left-4 flex flex-col gap-1">
        <div className="text-xs font-semibold text-foreground/80 uppercase tracking-wider">Entity Graph</div>
        <div className="text-[10px] text-muted-foreground">{graphData.nodes.length} Nodes &middot; {graphData.edges.length} Relationships</div>
      </div>
    </div>
  );

  return (
    <>
      <div className="my-5 flex flex-col rounded-xl border border-[var(--accent-steel)]/20 bg-[var(--surface-secondary)] p-4 shadow-sm h-[400px]">
        <div className="flex w-full items-center justify-between mb-4">
          <div className="flex items-center gap-2 text-[var(--accent-steel)]">
            <Network className="size-4" />
            <span className="font-semibold text-foreground/90">Knowledge Graph View</span>
          </div>
          <button onClick={() => setIsFullscreen(true)} className="p-1.5 hover:bg-[var(--surface)]/10 rounded-md text-muted-foreground hover:text-foreground transition-colors">
            <Maximize2 className="size-4" />
          </button>
        </div>
        <GraphContent />
      </div>

      {isFullscreen && (
        <div className="fixed inset-0 z-50 flex flex-col bg-[var(--surface-primary)] animate-in fade-in duration-200">
          <div className="flex items-center justify-between border-b border-[var(--accent-steel)]/10 px-6 py-4 bg-[var(--surface-secondary)]">
            <div className="flex items-center gap-3">
              <Network className="size-5 text-[var(--accent-steel)]" />
              <h3 className="font-semibold text-foreground">Interactive Knowledge Graph</h3>
              <div className="ml-4 flex items-center px-3 py-1 bg-[var(--surface)]/5 border border-border rounded-full">
                <Search className="size-3.5 text-muted-foreground mr-2" />
                <input type="text" placeholder="Search entities..." className="bg-transparent border-none outline-none text-sm text-foreground w-48 placeholder:text-foreground/30" />
              </div>
            </div>
            <button 
              onClick={() => setIsFullscreen(false)}
              className="p-1.5 rounded-md hover:bg-[var(--surface)]/10 text-muted-foreground hover:text-foreground transition-colors"
            >
              <X className="size-5" />
            </button>
          </div>
          <div className="flex-1 p-6 relative">
             <GraphContent />
          </div>
        </div>
      )}
    </>
  );
}
