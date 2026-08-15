import React from 'react';
import { ShieldAlert, Layers } from 'lucide-react';
import { MuleComponentAlert } from '../types';

interface AlertTableProps {
  alerts?: MuleComponentAlert[];
  onSelectAlert?: (alert: MuleComponentAlert) => void;
  selectedAlertId?: string;
}

export const AlertTable: React.FC<AlertTableProps> = () => {
  return (
    <div className="bg-slate-900/80 backdrop-blur border border-slate-800 rounded-xl overflow-hidden shadow-xl">
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-amber-400" />
          <h3 className="font-semibold text-white text-sm tracking-tight">Active Mule Subgraph Alerts</h3>
        </div>
        <span className="px-2.5 py-0.5 bg-amber-500/10 text-amber-400 border border-amber-500/20 rounded-full text-xs font-medium">
          Live Stream
        </span>
      </div>

      <div className="p-6 text-center text-slate-400">
        <div className="inline-flex p-3 bg-slate-800/80 rounded-xl mb-3 border border-slate-700">
          <Layers className="w-6 h-6 text-slate-400" />
        </div>
        <p className="text-sm font-medium text-slate-300">No active alerts loaded yet</p>
        <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
          Start the multi-bank synthetic transaction engine to stream boundary-crossing edges and detect suspicious mule rings in real-time.
        </p>
      </div>
    </div>
  );
};
