import React from 'react';
import { Compass } from 'lucide-react';

export const InvestigationWorkbench: React.FC = () => {
  return (
    <div className="bg-slate-900/80 backdrop-blur border border-slate-800 rounded-xl overflow-hidden shadow-xl p-5">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Compass className="w-5 h-5 text-cyan-400" />
          <h3 className="font-semibold text-white text-sm tracking-tight">Flow B: Bounded Investigation Workbench</h3>
        </div>
        <span className="px-2 py-0.5 bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 rounded-full text-xs font-mono">
          Ephemeral Salts
        </span>
      </div>

      <div className="mt-4 p-4 bg-slate-950/60 border border-slate-800/80 rounded-lg text-center">
        <p className="text-xs text-slate-400">
          On-demand scoped neighborhood traversal with bidirectional pattern-decay stopping criteria.
        </p>
      </div>
    </div>
  );
};
