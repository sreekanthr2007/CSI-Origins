/**
 * TRACE: Multi-Bank Swimlane Pipeline Graph Visualizer (Light Theme)
 */

import React, { useMemo } from 'react';
import {
  Activity,
  Layers,
  Maximize2
} from 'lucide-react';

import { Node, Edge } from '../types';


interface NetworkGraphProps {
  nodes: Node[];
  edges: Edge[];
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string | null) => void;
  onSelectEdge?: (edgeId: string | null) => void;
  onInspectNode: (node: Node) => void;
  onGenerateScenario?: (scenarioNum: number) => void;
}

export const NetworkGraph: React.FC<NetworkGraphProps> = ({
  nodes,
  edges,
  selectedNodeId,
  onSelectNode,
  onInspectNode,
  onGenerateScenario,
}) => {
  // Classify nodes into 4 horizontal swimlane stages based on topology and in/out degrees

  const swimlanes = useMemo(() => {
    const nodeInDegree = new Map<string, number>();
    const nodeOutDegree = new Map<string, number>();

    edges.forEach((e) => {
      nodeInDegree.set(e.target, (nodeInDegree.get(e.target) || 0) + 1);
      nodeOutDegree.set(e.source, (nodeOutDegree.get(e.source) || 0) + 1);
    });

    const ingress: Node[] = [];
    const intermediate: Node[] = [];
    const hubs: Node[] = [];
    const egress: Node[] = [];

    nodes.forEach((n) => {
      const inDeg = nodeInDegree.get(n.id) || 0;
      const outDeg = nodeOutDegree.get(n.id) || 0;

      if (inDeg === 0 && outDeg > 0) {
        ingress.push(n);
      } else if (inDeg > 0 && outDeg === 0) {
        egress.push(n);
      } else if (inDeg >= 3 || outDeg >= 3) {
        hubs.push(n);
      } else {
        intermediate.push(n);
      }
    });

    // Fallback if some buckets are empty to ensure a balanced pipeline
    if (ingress.length === 0 && nodes.length > 0) {
      ingress.push(...nodes.slice(0, Math.ceil(nodes.length / 4)));
    }

    return {
      ingress: ingress.slice(0, 15),
      intermediate: intermediate.slice(0, 15),
      hubs: hubs.slice(0, 15),
      egress: egress.slice(0, 15),
    };
  }, [nodes, edges]);

  // Helper for bank badge styling
  const getBankBadgeStyle = (bankId?: string) => {
    const b = (bankId || '').toLowerCase();
    if (b.includes('sbi')) return 'bg-blue-50 text-blue-700 border-blue-200';
    if (b.includes('hdfc')) return 'bg-indigo-50 text-indigo-700 border-indigo-200';
    if (b.includes('icici')) return 'bg-rose-50 text-rose-700 border-rose-200';
    if (b.includes('axis')) return 'bg-purple-50 text-purple-700 border-purple-200';
    if (b.includes('pnb')) return 'bg-amber-50 text-amber-800 border-amber-200';
    if (b.includes('bob')) return 'bg-orange-50 text-orange-700 border-orange-200';
    return 'bg-slate-100 text-slate-700 border-slate-200';
  };

  // Render Empty State if no nodes loaded yet
  if (nodes.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 bg-slate-50 border border-slate-200/80 rounded-2xl m-4 text-center">
        <div className="w-16 h-16 rounded-2xl bg-blue-100/70 border border-blue-200 flex items-center justify-center text-blue-600 mb-4 shadow-sm">
          <Layers className="w-8 h-8" />
        </div>
        <h3 className="text-xl font-bold text-slate-900 mb-1">No Active Topology in Memory</h3>
        <p className="text-sm text-slate-500 max-w-md mb-6">
          Load a pre-configured multi-bank money laundering scenario or synthesize live graph transactions.
        </p>

        <div className="flex flex-wrap gap-2.5 justify-center max-w-xl">
          <button
            onClick={() => onGenerateScenario?.(1)}
            className="px-4 py-2 bg-white hover:bg-blue-50 border border-slate-200 hover:border-blue-300 rounded-xl text-xs font-semibold text-slate-800 shadow-xs transition-all flex items-center gap-2"
          >
            <span className="w-2 h-2 rounded-full bg-red-500"></span> Scenario 1: 4-Bank Chain (₹5L)
          </button>
          <button
            onClick={() => onGenerateScenario?.(2)}
            className="px-4 py-2 bg-white hover:bg-blue-50 border border-slate-200 hover:border-blue-300 rounded-xl text-xs font-semibold text-slate-800 shadow-xs transition-all flex items-center gap-2"
          >
            <span className="w-2 h-2 rounded-full bg-amber-500"></span> Scenario 2: Collector Star (8 Senders)
          </button>
          <button
            onClick={() => onGenerateScenario?.(3)}
            className="px-4 py-2 bg-white hover:bg-blue-50 border border-slate-200 hover:border-blue-300 rounded-xl text-xs font-semibold text-slate-800 shadow-xs transition-all flex items-center gap-2"
          >
            <span className="w-2 h-2 rounded-full bg-purple-500"></span> Scenario 3: Smurfing Ring (10 Slices)
          </button>
          <button
            onClick={() => onGenerateScenario?.(4)}
            className="px-4 py-2 bg-white hover:bg-emerald-50 border border-slate-200 hover:border-emerald-300 rounded-xl text-xs font-semibold text-slate-800 shadow-xs transition-all flex items-center gap-2"
          >
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span> Scenario 4: Legitimate Decay
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col bg-slate-100/60 p-4 overflow-hidden relative select-none">
      {/* Swimlane Pipeline Header Indicator */}
      <div className="grid grid-cols-4 gap-4 mb-3 px-2">
        <div className="bg-white/90 border border-slate-200/80 px-3.5 py-2 rounded-xl shadow-xs flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-500"></span>
            <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              1. Ingress / Source Nodes
            </span>
          </div>
          <span className="text-xs font-bold font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
            {swimlanes.ingress.length}
          </span>
        </div>

        <div className="bg-white/90 border border-slate-200/80 px-3.5 py-2 rounded-xl shadow-xs flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="w-2.5 h-2.5 rounded-full bg-indigo-500"></span>
            <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              2. Rapid Layering Mules
            </span>
          </div>
          <span className="text-xs font-bold font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
            {swimlanes.intermediate.length}
          </span>
        </div>

        <div className="bg-white/90 border border-slate-200/80 px-3.5 py-2 rounded-xl shadow-xs flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
            <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              3. Aggregator & Smurf Hubs
            </span>
          </div>
          <span className="text-xs font-bold font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
            {swimlanes.hubs.length}
          </span>
        </div>

        <div className="bg-white/90 border border-slate-200/80 px-3.5 py-2 rounded-xl shadow-xs flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
            <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              4. Egress / Cash-Out Target
            </span>
          </div>
          <span className="text-xs font-bold font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
            {swimlanes.egress.length}
          </span>
        </div>
      </div>

      {/* Main Swimlane Columns Canvas */}
      <div className="flex-1 grid grid-cols-4 gap-4 overflow-y-auto pr-1 pb-4">
        {/* Swimlane Column 1 */}
        <div className="bg-white border border-slate-200 rounded-2xl p-3 shadow-xs space-y-3 overflow-y-auto">
          {swimlanes.ingress.map((node) => (
            <NodeCard
              key={node.id}
              node={node}
              isSelected={selectedNodeId === node.id}
              onSelect={onSelectNode}
              onInspect={onInspectNode}
              badgeStyle={getBankBadgeStyle(node.bank)}
            />
          ))}
        </div>

        {/* Swimlane Column 2 */}
        <div className="bg-white border border-slate-200 rounded-2xl p-3 shadow-xs space-y-3 overflow-y-auto">
          {swimlanes.intermediate.map((node) => (
            <NodeCard
              key={node.id}
              node={node}
              isSelected={selectedNodeId === node.id}
              onSelect={onSelectNode}
              onInspect={onInspectNode}
              badgeStyle={getBankBadgeStyle(node.bank)}
            />
          ))}
        </div>

        {/* Swimlane Column 3 */}
        <div className="bg-white border border-slate-200 rounded-2xl p-3 shadow-xs space-y-3 overflow-y-auto">
          {swimlanes.hubs.map((node) => (
            <NodeCard
              key={node.id}
              node={node}
              isSelected={selectedNodeId === node.id}
              onSelect={onSelectNode}
              onInspect={onInspectNode}
              badgeStyle={getBankBadgeStyle(node.bank)}
            />
          ))}
        </div>

        {/* Swimlane Column 4 */}
        <div className="bg-white border border-slate-200 rounded-2xl p-3 shadow-xs space-y-3 overflow-y-auto">
          {swimlanes.egress.map((node) => (
            <NodeCard
              key={node.id}
              node={node}
              isSelected={selectedNodeId === node.id}
              onSelect={onSelectNode}
              onInspect={onInspectNode}
              badgeStyle={getBankBadgeStyle(node.bank)}
            />
          ))}
        </div>
      </div>


      {/* Floating Canvas Footer Helper */}
      <div className="absolute bottom-6 right-8 bg-white/95 backdrop-blur-md border border-slate-200 px-4 py-2 rounded-xl shadow-lg flex items-center space-x-4 text-xs text-slate-600">
        <div className="flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-red-600 mule-pulse"></span>
          <span className="font-semibold text-slate-800">Critical Mule Ring (&ge; 70%)</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
          <span className="font-semibold text-slate-800">Suspicious (40-69%)</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
          <span className="font-semibold text-slate-800">Clean (&lt; 40%)</span>
        </div>
        <span className="text-slate-300">|</span>
        <span className="text-slate-500 italic">Click any card to open full Modal Profile</span>
      </div>
    </div>
  );
};

interface NodeCardProps {
  node: Node;
  isSelected: boolean;
  onSelect: (id: string) => void;
  onInspect: (node: Node) => void;
  badgeStyle: string;
}

const NodeCard: React.FC<NodeCardProps> = ({
  node,
  isSelected,
  onSelect,
  onInspect,
  badgeStyle,
}) => {
  const risk = node.riskScore ?? 0;
  const isHighRisk = risk >= 0.7;
  const isMediumRisk = risk >= 0.4 && risk < 0.7;

  return (
    <div
      onClick={() => onSelect(node.id)}
      className={`p-3.5 rounded-xl border transition-all cursor-pointer relative group ${

        isSelected
          ? 'bg-blue-50/90 border-blue-500 ring-2 ring-blue-500/20 shadow-md'
          : isHighRisk
          ? 'bg-red-50/40 border-red-200 hover:border-red-400 hover:bg-red-50/70 shadow-xs'
          : 'bg-white border-slate-200/90 hover:border-blue-300 hover:bg-slate-50/80 shadow-xs'
      }`}
    >
      {/* Top Row: Bank Badge & Risk Gauge */}
      <div className="flex items-center justify-between mb-2">
        <span className={`px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider border ${badgeStyle}`}>
          {node.bank || 'INTER-BANK'}
        </span>

        <span
          className={`px-2 py-0.5 rounded-full text-[10px] font-extrabold font-mono uppercase tracking-wider ${
            isHighRisk
              ? 'bg-red-600 text-white mule-pulse'
              : isMediumRisk
              ? 'bg-amber-500 text-white'
              : 'bg-emerald-600 text-white'
          }`}
        >
          {(risk * 100).toFixed(0)}% RISK
        </span>
      </div>

      {/* Standing Hash Snippet */}
      <div className="font-mono text-xs text-slate-700 font-semibold truncate mb-2.5">
        {node.id}
      </div>

      {/* Bottom Row: Metric & Inspect CTA */}
      <div className="flex items-center justify-between text-xs pt-2 border-t border-slate-100">
        <span className="text-slate-500 text-[11px] flex items-center gap-1">
          <Activity className="w-3 h-3 text-blue-600" /> Active Flow
        </span>

        <button
          onClick={(e) => {
            e.stopPropagation();
            onInspect(node);
          }}
          className="text-blue-600 group-hover:text-blue-700 font-bold flex items-center gap-1 hover:underline text-[11px]"
        >
          <span>Inspect</span>
          <Maximize2 className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
};
