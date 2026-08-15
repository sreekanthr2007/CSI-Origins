import React from 'react';
import { Network, Activity, Shield } from 'lucide-react';

interface NetworkGraphProps {
  onSelectNode?: (nodeId: string) => void;
}

export const NetworkGraph: React.FC<NetworkGraphProps> = () => {
  return (
    <div className="relative w-full h-[520px] bg-slate-900/70 backdrop-blur border border-slate-800 rounded-xl overflow-hidden shadow-2xl flex flex-col items-center justify-center p-6 text-center">
      <div className="p-4 bg-indigo-500/10 border border-indigo-500/30 rounded-2xl mb-4 text-indigo-400">
        <Network className="w-12 h-12 stroke-[1.5] animate-pulse" />
      </div>
      <h3 className="text-lg font-semibold text-white tracking-tight">Cross-Bank Network Graph Canvas</h3>
      <p className="text-sm text-slate-400 max-w-md mt-2">
        React Flow topology visualizer for real-time inter-bank edge streams, boundary-crossing transfers, and multi-hop mule rings.
      </p>
      <div className="flex items-center gap-4 mt-6 text-xs text-slate-400 font-mono">
        <span className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-800/80 rounded-md border border-slate-700">
          <Activity className="w-3.5 h-3.5 text-emerald-400" /> Flow A Active
        </span>
        <span className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-800/80 rounded-md border border-slate-700">
          <Shield className="w-3.5 h-3.5 text-indigo-400" /> Zero Raw PII
        </span>
      </div>
    </div>
  );
};
