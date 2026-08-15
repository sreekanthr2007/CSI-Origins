/**
 * TRACE: Interactive Force-Directed Mule Network Graph
 * Built with D3.js — matches reference visualization with:
 *  - Colored nodes by risk (green=low, yellow=medium, red=mule/high)
 *  - Directed edges with arrow markers, thickness by amount
 *  - Transaction labels on edges (amount + timestamp)
 *  - Hover tooltip on node (account details, risk, history)
 *  - Click tooltip on edge (transaction info)
 *  - Right-side alert + stats panel
 *  - Zoom, pan, drag behavior
 */

import React, { useEffect, useRef, useCallback, useState } from 'react';
import * as d3 from 'd3';
import { Node, Edge } from '../types';
import {
  AlertTriangle, ShieldAlert, Activity,
  Zap, X, Maximize2
} from 'lucide-react';


interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  bank: string;
  riskScore: number;
  label: string;
  inDegree: number;
  outDegree: number;
  totalVolume: number;
  isMule: boolean;
}

interface GraphLink extends d3.SimulationLinkDatum<GraphNode> {
  id: string;
  source: string | GraphNode;
  target: string | GraphNode;
  amount: number;
  timestamp: string;
  bankId: string;
}

interface MuleNetworkGraphProps {
  nodes: Node[];
  edges: Edge[];
  onNodeClick?: (node: Node) => void;
  stats?: {
    nodeCount: number;
    edgeCount: number;
  } | null;
  alerts?: Array<{ id: string; severity: string; componentId: string; riskScore: number }>;
}

const BANK_COLORS: Record<string, string> = {
  bank_sbi:   '#2563EB',
  bank_hdfc:  '#7C3AED',
  bank_icici: '#DC2626',
  bank_axis:  '#D97706',
  bank_pnb:   '#059669',
  bank_bob:   '#0891B2',
  UNKNOWN:    '#6B7280',
};

function getRiskColor(score: number): string {
  if (score >= 0.7) return '#EF4444';  // red — mule
  if (score >= 0.4) return '#F59E0B';  // yellow — medium
  return '#22C55E';                     // green — low
}

function getRiskStroke(score: number): string {
  if (score >= 0.7) return '#B91C1C';
  if (score >= 0.4) return '#B45309';
  return '#15803D';
}

function formatAmount(v: number): string {
  if (v >= 100000) return `$${(v / 100000).toFixed(0)}L`;
  if (v >= 1000) return `$${(v / 1000).toFixed(1)}k`;
  return `$${v}`;
}

function shortHash(id: string): string {
  const parts = id.split(':');
  const raw = parts[parts.length - 1] || id;
  // Map to short A-XXXX style IDs for display
  const num = parseInt(raw.slice(0, 4), 16) % 9000 + 1000;
  const prefix = ['A', 'M', 'P', 'R'][parseInt(raw[0], 16) % 4];
  return `${prefix}-${num}`;
}

const MuleNetworkGraph: React.FC<MuleNetworkGraphProps> = ({
  nodes,
  edges,
  onNodeClick,
  stats,
  alerts = [],
}) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const simulationRef = useRef<d3.Simulation<GraphNode, GraphLink> | null>(null);

  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<GraphLink | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [edgeTooltipPos, setEdgeTooltipPos] = useState({ x: 0, y: 0 });
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  const buildGraph = useCallback(() => {
    if (!svgRef.current || !containerRef.current) return;
    if (nodes.length === 0) return;

    const container = containerRef.current;
    const W = container.clientWidth;
    const H = container.clientHeight;

    // Clear existing
    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current)
      .attr('width', W)
      .attr('height', H)
      .style('background', '#F8FAFC');

    // Defs: arrow markers (one per risk level), glow filters
    const defs = svg.append('defs');

    // Arrow markers
    ['low', 'medium', 'high'].forEach((level) => {
      const color = level === 'high' ? '#EF4444' : level === 'medium' ? '#F59E0B' : '#22C55E';
      defs.append('marker')
        .attr('id', `arrow-${level}`)
        .attr('viewBox', '0 -4 8 8')
        .attr('refX', 22)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-4L8,0L0,4')
        .attr('fill', color)
        .attr('opacity', 0.85);
    });

    // Glow filter for high-risk nodes
    const glowFilter = defs.append('filter').attr('id', 'glow').attr('x', '-50%').attr('y', '-50%').attr('width', '200%').attr('height', '200%');
    glowFilter.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'blur');
    const glowMerge = glowFilter.append('feMerge');
    glowMerge.append('feMergeNode').attr('in', 'blur');
    glowMerge.append('feMergeNode').attr('in', 'SourceGraphic');

    // Background dot grid
    const pattern = defs.append('pattern')
      .attr('id', 'grid')
      .attr('width', 30)
      .attr('height', 30)
      .attr('patternUnits', 'userSpaceOnUse');
    pattern.append('circle')
      .attr('cx', 1).attr('cy', 1).attr('r', 1)
      .attr('fill', '#CBD5E1').attr('opacity', 0.4);
    svg.append('rect').attr('width', W).attr('height', H).attr('fill', 'url(#grid)');

    // Zoom & pan layer
    const g = svg.append('g').attr('class', 'zoom-layer');

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform.toString());
      });

    svg.call(zoom as any);

    // Build graph data
    const inDegMap = new Map<string, number>();
    const outDegMap = new Map<string, number>();
    const volumeMap = new Map<string, number>();

    edges.forEach(e => {
      outDegMap.set(e.source, (outDegMap.get(e.source) || 0) + 1);
      inDegMap.set(e.target, (inDegMap.get(e.target) || 0) + 1);
      volumeMap.set(e.source, (volumeMap.get(e.source) || 0) + e.amount);
      volumeMap.set(e.target, (volumeMap.get(e.target) || 0) + e.amount);
    });

    const graphNodes: GraphNode[] = nodes.slice(0, 60).map(n => ({
      id: n.id,
      bank: n.bank || 'UNKNOWN',
      riskScore: n.riskScore ?? 0,
      label: shortHash(n.id),
      inDegree: inDegMap.get(n.id) || 0,
      outDegree: outDegMap.get(n.id) || 0,
      totalVolume: volumeMap.get(n.id) || 0,
      isMule: (n.riskScore ?? 0) >= 0.7,
    }));

    const nodeIdSet = new Set(graphNodes.map(n => n.id));

    const graphLinks: GraphLink[] = edges
      .filter(e => nodeIdSet.has(e.source) && nodeIdSet.has(e.target) && e.source !== e.target)
      .slice(0, 120)
      .map(e => ({
        id: e.id,
        source: e.source,
        target: e.target,
        amount: e.amount,
        timestamp: e.timestamp,
        bankId: e.bankId,
      }));

    // Node radius by degree + volume
    const nodeRadius = (n: GraphNode) => {
      const base = n.isMule ? 14 : 10;
      const deg = Math.min(n.inDegree + n.outDegree, 15);
      return base + deg * 0.8;
    };

    // Edge thickness by amount
    const edgeWidth = (link: GraphLink) => {
      const amt = link.amount || 0;
      if (amt >= 200000) return 5;
      if (amt >= 50000) return 3;
      if (amt >= 10000) return 2;
      return 1.5;
    };

    const edgeRiskLevel = (link: GraphLink): 'low' | 'medium' | 'high' => {
      const amt = link.amount || 0;
      if (amt >= 200000) return 'high';
      if (amt >= 50000) return 'medium';
      return 'low';
    };

    const edgeColor = (link: GraphLink): string => {
      const level = edgeRiskLevel(link);
      if (level === 'high') return '#EF4444';
      if (level === 'medium') return '#F59E0B';
      return '#94A3B8';
    };

    // Force simulation
    const simulation = d3.forceSimulation<GraphNode, GraphLink>(graphNodes)
      .force('link', d3.forceLink<GraphNode, GraphLink>(graphLinks)
        .id(d => d.id)
        .distance(d => {
          const link = d as GraphLink;
          return 100 + (link.amount || 0) / 10000;
        })
        .strength(0.4)
      )
      .force('charge', d3.forceManyBody().strength(-350))
      .force('center', d3.forceCenter(W / 2, H / 2).strength(0.08))
      .force('collision', d3.forceCollide<GraphNode>().radius(d => nodeRadius(d) + 12))
      .force('x', d3.forceX(W / 2).strength(0.03))
      .force('y', d3.forceY(H / 2).strength(0.03));

    simulationRef.current = simulation;

    // Draw edge lines
    const linkGroup = g.append('g').attr('class', 'links');
    const link = linkGroup.selectAll<SVGPathElement, GraphLink>('path')
      .data(graphLinks)
      .join('path')
      .attr('fill', 'none')
      .attr('stroke', d => edgeColor(d))
      .attr('stroke-width', d => edgeWidth(d))
      .attr('stroke-opacity', 0.7)
      .attr('marker-end', d => `url(#arrow-${edgeRiskLevel(d)})`)
      .style('cursor', 'pointer')
      .on('mouseenter', (event, d) => {
        d3.select(event.currentTarget)
          .attr('stroke-opacity', 1)
          .attr('stroke-width', edgeWidth(d) + 1.5);
        setHoveredEdge(d);
        setEdgeTooltipPos({ x: event.offsetX, y: event.offsetY });
      })
      .on('mousemove', (event) => {
        setEdgeTooltipPos({ x: event.offsetX, y: event.offsetY });
      })
      .on('mouseleave', (event, d) => {
        d3.select(event.currentTarget)
          .attr('stroke-opacity', 0.7)
          .attr('stroke-width', edgeWidth(d));
        setHoveredEdge(null);
      });

    // Draw edge amount labels (only for large amounts)
    const edgeLabelGroup = g.append('g').attr('class', 'edge-labels');

    // Draw nodes
    const nodeGroup = g.append('g').attr('class', 'nodes');
    const node = nodeGroup.selectAll<SVGGElement, GraphNode>('g.node-g')
      .data(graphNodes)
      .join('g')
      .attr('class', 'node-g')
      .style('cursor', 'pointer')
      .call(
        d3.drag<SVGGElement, GraphNode>()
          .on('start', (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on('drag', (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on('end', (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          }) as any
      )
      .on('mouseenter', (event, d) => {
        d3.select(event.currentTarget).select('circle.node-main')
          .attr('r', nodeRadius(d) + 4)
          .attr('filter', 'url(#glow)');
        setHoveredNode(d);
        setTooltipPos({ x: event.offsetX, y: event.offsetY });
      })
      .on('mousemove', (event) => {
        setTooltipPos({ x: event.offsetX, y: event.offsetY });
      })
      .on('mouseleave', (event, d) => {
        d3.select(event.currentTarget).select('circle.node-main')
          .attr('r', nodeRadius(d))
          .attr('filter', d.isMule ? 'url(#glow)' : 'none');
        setHoveredNode(null);
      })
      .on('click', (event, d) => {
        event.stopPropagation();
        setSelectedNode(prev => prev?.id === d.id ? null : d);
        if (onNodeClick) {
          onNodeClick({
            id: d.id,
            bank: d.bank,
            riskScore: d.riskScore,
            isMule: d.isMule,
            inDegree: d.inDegree,
            outDegree: d.outDegree,
            totalVolume: d.totalVolume,
          });
        }
      });

    // Outer glow ring for mule nodes
    node.filter(d => d.isMule)
      .append('circle')
      .attr('class', 'node-ring')
      .attr('r', d => nodeRadius(d) + 6)
      .attr('fill', 'none')
      .attr('stroke', d => getRiskColor(d.riskScore))
      .attr('stroke-width', 2)
      .attr('opacity', 0.4)
      .attr('filter', 'url(#glow)');

    // Main node circle
    node.append('circle')
      .attr('class', 'node-main')
      .attr('r', nodeRadius)
      .attr('fill', d => getRiskColor(d.riskScore))
      .attr('stroke', d => getRiskStroke(d.riskScore))
      .attr('stroke-width', d => d.isMule ? 2.5 : 1.5)
      .attr('filter', d => d.isMule ? 'url(#glow)' : 'none');

    // Node label
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('fill', 'white')
      .attr('font-size', d => d.isMule ? '9px' : '8px')
      .attr('font-weight', '700')
      .attr('font-family', 'JetBrains Mono, monospace')
      .attr('pointer-events', 'none')
      .text(d => d.label);

    // Bank indicator dot below node
    node.append('circle')
      .attr('cy', d => nodeRadius(d) + 5)
      .attr('r', 3)
      .attr('fill', d => BANK_COLORS[d.bank] || BANK_COLORS.UNKNOWN)
      .attr('stroke', 'white')
      .attr('stroke-width', 1);

    // SVG click to deselect
    svg.on('click', () => setSelectedNode(null));

    // Simulation tick
    simulation.on('tick', () => {
      link.attr('d', (d) => {
        const source = d.source as GraphNode;
        const target = d.target as GraphNode;
        if (!source.x || !source.y || !target.x || !target.y) return '';

        // Curved path for multi-edges
        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const dr = Math.sqrt(dx * dx + dy * dy) * 0.8;

        return `M${source.x},${source.y} A${dr},${dr} 0 0,1 ${target.x},${target.y}`;
      });

      node.attr('transform', (d) => `translate(${d.x ?? 0},${d.y ?? 0})`);

      // Edge labels on large transfers only
      edgeLabelGroup.selectAll('text').remove();
      graphLinks
        .filter(l => l.amount >= 50000)
        .forEach(l => {
          const s = l.source as GraphNode;
          const t = l.target as GraphNode;
          if (!s.x || !s.y || !t.x || !t.y) return;
          const mx = (s.x + t.x) / 2;
          const my = (s.y + t.y) / 2 - 8;
          edgeLabelGroup.append('text')
            .attr('x', mx)
            .attr('y', my)
            .attr('text-anchor', 'middle')
            .attr('fill', l.amount >= 200000 ? '#DC2626' : '#92400E')
            .attr('font-size', '9px')
            .attr('font-weight', '600')
            .attr('font-family', 'monospace')
            .attr('pointer-events', 'none')
            .text(`${formatAmount(l.amount)} | ${l.timestamp ? new Date(l.timestamp).toLocaleDateString() : ''}`);
        });
    });

    // Fit to view after settling
    setTimeout(() => {
      const bounds = (g.node() as SVGGElement)?.getBBox();
      if (bounds && bounds.width > 0) {
        const scale = Math.min(0.85, Math.min(W / (bounds.width + 80), H / (bounds.height + 80)));
        const tx = W / 2 - scale * (bounds.x + bounds.width / 2);
        const ty = H / 2 - scale * (bounds.y + bounds.height / 2);
        svg.transition().duration(800).call(
          zoom.transform as any,
          d3.zoomIdentity.translate(tx, ty).scale(scale)
        );
      }
    }, 2000);

    return () => {
      simulation.stop();
    };
  }, [nodes, edges, onNodeClick]);

  useEffect(() => {
    const cleanup = buildGraph();
    return cleanup;
  }, [buildGraph]);

  // Refit on container resize
  useEffect(() => {
    const observer = new ResizeObserver(() => buildGraph());
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [buildGraph]);

  const muleCount = nodes.filter(n => (n.riskScore ?? 0) >= 0.7).length;
  const totalVolume = edges.reduce((acc, e) => acc + (e.amount || 0), 0);

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* Graph Canvas Area */}
      <div className="flex-1 relative overflow-hidden" ref={containerRef}>
        <svg
          ref={svgRef}
          className="w-full h-full"
          style={{ background: '#F8FAFC' }}
        />

        {/* Empty state */}
        {nodes.length === 0 && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400">
            <Activity className="w-12 h-12 mb-3 opacity-30" />
            <p className="font-semibold text-sm">No graph data yet</p>
            <p className="text-xs mt-1">Click "⚡ Synthesize Data" to generate transactions</p>
          </div>
        )}

        {/* Top-left Legend */}
        <div className="absolute top-3 left-3 bg-white/95 backdrop-blur border border-slate-200 rounded-xl px-3 py-2.5 shadow-md text-xs space-y-1.5">
          <div className="font-bold text-slate-700 uppercase tracking-wider text-[10px] mb-2">Node Risk Level</div>
          <div className="flex items-center space-x-2">
            <span className="w-3 h-3 rounded-full bg-green-500 inline-block shadow-sm"></span>
            <span className="text-slate-600">Low Risk (&lt; 40%)</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="w-3 h-3 rounded-full bg-yellow-400 inline-block shadow-sm"></span>
            <span className="text-slate-600">Medium Risk (40–69%)</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="w-3 h-3 rounded-full bg-red-500 inline-block shadow-sm"></span>
            <span className="text-slate-600">High Risk / Mule (&ge; 70%)</span>
          </div>
          <div className="border-t border-slate-100 my-1 pt-1">
            <div className="font-bold text-slate-700 uppercase tracking-wider text-[10px] mb-1.5">Edge Direction</div>
            <div className="flex items-center space-x-2">
              <svg width="28" height="10"><line x1="0" y1="5" x2="20" y2="5" stroke="#94A3B8" strokeWidth="1.5" markerEnd="url(#lg-arrow)" /><defs><marker id="lg-arrow" markerWidth="4" markerHeight="4" refX="3" refY="2" orient="auto"><path d="M0,0L4,2L0,4" fill="#94A3B8" /></marker></defs></svg>
              <span className="text-slate-600">Transaction Flow</span>
            </div>
          </div>
          <div className="border-t border-slate-100 my-1 pt-1">
            <div className="font-bold text-slate-700 uppercase tracking-wider text-[10px] mb-1.5">Edge Thickness</div>
            <div className="flex items-center space-x-2">
              <svg width="28" height="10"><line x1="0" y1="5" x2="28" y2="5" stroke="#94A3B8" strokeWidth="1.5" /></svg>
              <span className="text-slate-600">Small Amount</span>
            </div>
            <div className="flex items-center space-x-2">
              <svg width="28" height="10"><line x1="0" y1="5" x2="28" y2="5" stroke="#EF4444" strokeWidth="4" /></svg>
              <span className="text-slate-600">Large Amount</span>
            </div>
          </div>
        </div>

        {/* Hover tooltip — Node */}
        {hoveredNode && !selectedNode && (
          <div
            className="absolute z-30 pointer-events-none"
            style={{ left: tooltipPos.x + 14, top: tooltipPos.y - 10 }}
          >
            <div className="bg-white border border-slate-200 rounded-xl shadow-xl p-3.5 text-xs w-56">
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-slate-900">{hoveredNode.label}</span>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                  hoveredNode.isMule
                    ? 'bg-red-100 text-red-700 border border-red-200'
                    : hoveredNode.riskScore >= 0.4
                    ? 'bg-amber-100 text-amber-700 border border-amber-200'
                    : 'bg-emerald-100 text-emerald-700 border border-emerald-200'
                }`}>
                  {hoveredNode.isMule ? 'MULE' : hoveredNode.riskScore >= 0.4 ? 'SUSPICIOUS' : 'CLEAN'}
                </span>
              </div>
              <div className="space-y-1 text-slate-600">
                <div className="flex justify-between">
                  <span>Risk Score:</span>
                  <span className={`font-bold ${hoveredNode.isMule ? 'text-red-600' : hoveredNode.riskScore >= 0.4 ? 'text-amber-600' : 'text-emerald-600'}`}>
                    {(hoveredNode.riskScore * 100).toFixed(0)}% {hoveredNode.isMule ? '(Critical)' : ''}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Bank:</span>
                  <span className="font-semibold uppercase text-slate-800">{hoveredNode.bank.replace('bank_', '')}</span>
                </div>
                <div className="flex justify-between">
                  <span>In-Flow Edges:</span>
                  <span className="font-semibold text-slate-800">{hoveredNode.inDegree}</span>
                </div>
                <div className="flex justify-between">
                  <span>Out-Flow Edges:</span>
                  <span className="font-semibold text-slate-800">{hoveredNode.outDegree}</span>
                </div>
                <div className="flex justify-between">
                  <span>Avg Trans Vol:</span>
                  <span className="font-semibold text-slate-800">{hoveredNode.inDegree + hoveredNode.outDegree > 0 ? formatAmount(hoveredNode.totalVolume / Math.max(1, hoveredNode.inDegree + hoveredNode.outDegree)) : 'N/A'}</span>
                </div>
                <div className="flex justify-between">
                  <span>Complete History:</span>
                  <span className="font-semibold text-blue-600 cursor-pointer">View →</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Hover tooltip — Edge (Transaction Info) */}
        {hoveredEdge && (
          <div
            className="absolute z-30 pointer-events-none"
            style={{ left: edgeTooltipPos.x + 10, top: edgeTooltipPos.y + 10 }}
          >
            <div className="bg-white border border-slate-200 rounded-xl shadow-xl p-3.5 text-xs w-52">
              <div className="font-bold text-slate-900 mb-2 flex items-center gap-1.5">
                <Zap className="w-3 h-3 text-amber-500" />
                TRANSACTION INFO
              </div>
              <div className="space-y-1 text-slate-600">
                <div className="flex justify-between">
                  <span>ID:</span>
                  <span className="font-mono font-semibold text-slate-800 text-[10px]">{(hoveredEdge.id || 'TR-XXXX').slice(0, 12)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Amount:</span>
                  <span className={`font-bold ${(hoveredEdge.amount || 0) >= 200000 ? 'text-red-600' : 'text-slate-800'}`}>
                    ₹{(hoveredEdge.amount || 0).toLocaleString('en-IN')}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Date:</span>
                  <span className="font-semibold text-slate-800">
                    {hoveredEdge.timestamp ? new Date(hoveredEdge.timestamp).toLocaleDateString() : 'N/A'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Type:</span>
                  <span className="font-semibold text-slate-800">
                    {(hoveredEdge.amount || 0) >= 200000 ? 'Transfer (Large/Rapid)' : 'Transfer'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Bank:</span>
                  <span className="font-semibold text-slate-800 uppercase">
                    {(hoveredEdge.bankId || '').replace('bank_', '')}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Selected Node Detail Popup (pin-style) */}
        {selectedNode && (
          <div className="absolute top-3 right-3 z-30">
            <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl p-4 text-xs w-64">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className={`w-3 h-3 rounded-full ${selectedNode.isMule ? 'bg-red-500' : selectedNode.riskScore >= 0.4 ? 'bg-amber-400' : 'bg-emerald-500'}`}></span>
                  <span className="font-bold text-slate-900 text-sm">ACCOUNT DETAILS: {selectedNode.label}</span>
                </div>
                <button
                  onClick={() => setSelectedNode(null)}
                  className="p-1 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-700"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="space-y-1.5 text-slate-700">
                <div className="flex justify-between">
                  <span className="text-slate-500">Risk Score:</span>
                  <span className={`font-bold ${selectedNode.isMule ? 'text-red-600' : selectedNode.riskScore >= 0.4 ? 'text-amber-600' : 'text-emerald-600'}`}>
                    {(selectedNode.riskScore * 100).toFixed(0)}% {selectedNode.isMule ? '(Critical)' : ''}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Bank:</span>
                  <span className="font-semibold uppercase">{selectedNode.bank.replace('bank_', '')}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Avg Trans Vol:</span>
                  <span className="font-semibold">
                    {formatAmount(selectedNode.totalVolume / Math.max(1, selectedNode.inDegree + selectedNode.outDegree))}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Connections:</span>
                  <span className="font-semibold">{selectedNode.inDegree} in / {selectedNode.outDegree} out</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Zoom controls */}
        <div className="absolute bottom-4 left-3 flex flex-col space-y-1.5">
          <button
            onClick={() => {
              const svg = d3.select(svgRef.current);
              svg.transition().call((d3.zoom() as any).scaleBy, 1.3);
            }}
            className="w-8 h-8 bg-white border border-slate-200 rounded-lg shadow-sm text-slate-600 hover:text-slate-900 hover:bg-slate-50 flex items-center justify-center text-base font-bold transition-colors"
          >+</button>
          <button
            onClick={() => {
              const svg = d3.select(svgRef.current);
              svg.transition().call((d3.zoom() as any).scaleBy, 0.77);
            }}
            className="w-8 h-8 bg-white border border-slate-200 rounded-lg shadow-sm text-slate-600 hover:text-slate-900 hover:bg-slate-50 flex items-center justify-center text-base font-bold transition-colors"
          >−</button>
          <button
            onClick={() => buildGraph()}
            title="Refit graph"
            className="w-8 h-8 bg-white border border-slate-200 rounded-lg shadow-sm text-slate-600 hover:text-slate-900 hover:bg-slate-50 flex items-center justify-center transition-colors"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Right Sidebar — Alert Summary & Stats */}
      <div className="w-64 bg-white border-l border-slate-200 flex flex-col overflow-y-auto shrink-0">
        {/* Alert Summary Header */}
        <div className="p-3 border-b border-slate-200 bg-slate-50">
          <h3 className="text-[10px] font-extrabold uppercase tracking-widest text-slate-600">Alert Summary & Details</h3>
        </div>

        {/* System Alerts */}
        <div className="p-3 border-b border-slate-100">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-2">System Alerts</div>
          <div className="space-y-2">
            {muleCount > 0 && (
              <div className="flex items-start gap-2 text-xs">
                <AlertTriangle className="w-3.5 h-3.5 text-red-500 mt-0.5 shrink-0" />
                <span className="text-slate-700 leading-tight">
                  Mule Network Detected in {muleCount} Cluster{muleCount > 1 ? 's' : ''}
                </span>
              </div>
            )}
            {totalVolume >= 500000 && (
              <div className="flex items-start gap-2 text-xs">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-500 mt-0.5 shrink-0" />
                <span className="text-slate-700 leading-tight">High-Volume Transfer Spike Identified</span>
              </div>
            )}
            {alerts.filter(a => a.severity === 'critical').map(a => (
              <div key={a.id} className="flex items-start gap-2 text-xs">
                <ShieldAlert className="w-3.5 h-3.5 text-red-500 mt-0.5 shrink-0" />
                <span className="text-slate-700 leading-tight font-mono text-[10px]">{a.componentId.slice(0, 20)}…</span>
              </div>
            ))}
            {muleCount === 0 && totalVolume < 500000 && alerts.length === 0 && (
              <div className="text-xs text-slate-400 italic">No active system alerts</div>
            )}
          </div>
        </div>

        {/* Network Statistics */}
        <div className="p-3 border-b border-slate-100">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-2.5">Network Statistics</div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-500">Total Accounts</span>
              <span className="font-bold text-slate-900">{stats?.nodeCount ?? nodes.length}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Total Transactions</span>
              <span className="font-bold text-slate-900">{stats?.edgeCount ?? edges.length}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Total Volume</span>
              <span className="font-bold text-slate-900">₹{(totalVolume / 100000).toFixed(1)}L</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Mule Prob. Score</span>
              <span className={`font-bold ${muleCount > 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                {nodes.length > 0 ? Math.round((muleCount / nodes.length) * 100) : 0}%
              </span>
            </div>
          </div>
        </div>

        {/* Selected Node Details */}
        {selectedNode ? (
          <div className="p-3 border-b border-slate-100">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-2.5">Selected Node ({selectedNode.label})</div>
            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-500">Account ID</span>
                <span className="font-bold text-slate-900">{selectedNode.label}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Total Volume</span>
                <span className="font-bold text-slate-900">₹{selectedNode.totalVolume.toLocaleString('en-IN')}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Transactions</span>
                <span className="font-bold text-slate-900">{selectedNode.inDegree + selectedNode.outDegree}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Mule Prob. Score</span>
                <span className={`font-bold ${selectedNode.isMule ? 'text-red-600' : 'text-emerald-600'}`}>
                  {(selectedNode.riskScore * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          </div>
        ) : (
          <div className="p-3 border-b border-slate-100">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1.5">Selected Node</div>
            <p className="text-xs text-slate-400 italic">Click any node in the graph to view details</p>
          </div>
        )}

        {/* Bank Distribution */}
        <div className="p-3 border-b border-slate-100">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-2.5">Bank Distribution</div>
          <div className="space-y-2">
            {Object.entries(
              nodes.reduce((acc, n) => {
                const b = n.bank || 'UNKNOWN';
                acc[b] = (acc[b] || 0) + 1;
                return acc;
              }, {} as Record<string, number>)
            ).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([bank, count]) => (
              <div key={bank} className="flex items-center gap-2">
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ background: BANK_COLORS[bank] || '#6B7280' }}
                />
                <span className="text-xs text-slate-700 uppercase">{bank.replace('bank_', '')}</span>
                <div className="flex-1 bg-slate-100 rounded-full h-1.5 overflow-hidden">
                  <div
                    className="h-1.5 rounded-full"
                    style={{
                      width: `${Math.round((count / nodes.length) * 100)}%`,
                      background: BANK_COLORS[bank] || '#6B7280'
                    }}
                  />
                </div>
                <span className="text-[10px] text-slate-500 font-mono">{count}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Mule Ring Summary */}
        <div className="p-3">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-2.5">
            High-Risk Nodes ({muleCount})
          </div>
          <div className="space-y-1.5 max-h-40 overflow-y-auto">
            {nodes
              .filter(n => (n.riskScore ?? 0) >= 0.7)
              .slice(0, 10)
              .map(n => (
                <div
                  key={n.id}
                  className="flex items-center justify-between text-xs bg-red-50/60 border border-red-100 rounded-lg px-2 py-1.5 cursor-pointer hover:bg-red-50"
                  onClick={() => {
                    setSelectedNode({
                      id: n.id,
                      bank: n.bank || 'UNKNOWN',
                      riskScore: n.riskScore ?? 0.85,
                      label: shortHash(n.id),
                      inDegree: 0,
                      outDegree: 0,
                      totalVolume: 0,
                      isMule: true,
                    });
                  }}
                >
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-red-500 shrink-0"></span>
                    <span className="font-mono font-bold text-slate-900 text-[10px]">{shortHash(n.id)}</span>
                  </div>
                  <span className="font-bold text-red-600 text-[10px]">{((n.riskScore ?? 0) * 100).toFixed(0)}%</span>
                </div>
              ))}
            {muleCount === 0 && (
              <p className="text-xs text-slate-400 italic">No high-risk mule nodes detected</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default MuleNetworkGraph;
