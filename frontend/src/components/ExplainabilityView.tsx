import React from 'react';
import { HelpCircle, BarChart3, Info } from 'lucide-react';
import { MuleComponentAlert } from '../types';

interface ExplainabilityViewProps {
  alert?: MuleComponentAlert | null;
}

export const ExplainabilityView: React.FC<ExplainabilityViewProps> = () => {
  return (
    <div className="bg-slate-900/80 backdrop-blur border border-slate-800 rounded-xl overflow-hidden shadow-xl p-5">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-indigo-400" />
          <h3 className="font-semibold text-white text-sm tracking-tight">SHAP Explainability & Rationale</h3>
        </div>
        <HelpCircle className="w-4 h-4 text-slate-500 cursor-help" />
      </div>

      <div className="mt-4 p-4 bg-slate-950/60 border border-slate-800/80 rounded-lg">
        <div className="flex items-start gap-2.5 text-xs text-slate-400">
          <Info className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
          <p>
            Every mule flag is accompanied by a transparent mathematical attribution model showing exact pass-through ratios, cycle lengths, and temporal velocities.
          </p>
        </div>
      </div>
    </div>
  );
};
