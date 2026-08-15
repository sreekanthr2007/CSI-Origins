/**
 * TRACE: Detailed Node & Cluster Inspection Modal (Light Theme)
 */

import React from 'react';
import {
  X,
  ShieldAlert,
  Activity,
  ArrowRight,
  Fingerprint,
  CheckCircle,
} from 'lucide-react';
import { Node, Edge, Component } from '../types';


interface InspectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedNode: Node | null;
  selectedComponent?: Component | null;
  connectedEdges: Edge[];
  onLaunchInvestigation: (nodeId: string) => void;
}

export const InspectionModal: React.FC<InspectionModalProps> = ({
  isOpen,
  onClose,
  selectedNode,
  selectedComponent,
  connectedEdges,
  onLaunchInvestigation,
}) => {
  if (!isOpen || !selectedNode) return null;

  const isHighRisk = (selectedNode.riskScore ?? 0) >= 0.7;
  const isMediumRisk = (selectedNode.riskScore ?? 0) >= 0.4 && (selectedNode.riskScore ?? 0) < 0.7;

  // Compute total in/out transaction volumes
  const inEdges = connectedEdges.filter(e => e.target === selectedNode.id);
  const outEdges = connectedEdges.filter(e => e.source === selectedNode.id);
  const inVolume = inEdges.reduce((acc, e) => acc + (e.amount || 0), 0);
  const outVolume = outEdges.reduce((acc, e) => acc + (e.amount || 0), 0);
  const passThrough = inVolume > 0 ? Math.min(100, Math.round((outVolume / inVolume) * 100)) : 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-fadeIn">
      <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl max-w-2xl w-full overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className={`px-6 py-4 border-b flex items-center justify-between ${
          isHighRisk ? 'bg-red-50/70 border-red-200' : 'bg-slate-50 border-slate-200'
        }`}>
          <div className="flex items-center space-x-3">
            <div className={`p-2.5 rounded-xl ${
              isHighRisk ? 'bg-red-100 text-red-600' : isMediumRisk ? 'bg-amber-100 text-amber-600' : 'bg-blue-100 text-blue-600'
            }`}>
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-slate-900 text-base">Node Intelligence Profile</span>
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold font-mono uppercase ${
                  isHighRisk ? 'bg-red-600 text-white' : isMediumRisk ? 'bg-amber-500 text-white' : 'bg-emerald-600 text-white'
                }`}>
                  {isHighRisk ? 'CRITICAL MULE' : isMediumRisk ? 'SUSPICIOUS' : 'LEGITIMATE'}
                </span>
              </div>
              <span className="text-xs text-slate-500 font-mono">Zero-PII Cryptographic Entity</span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 text-sm text-slate-700">
          {/* Key Identifiers Card */}
          <div className="bg-slate-50 border border-slate-200/80 rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                <Fingerprint className="w-3.5 h-3.5 text-blue-600" /> Standing HMAC Hash
              </span>
              <span className="px-2 py-0.5 bg-blue-100/70 text-blue-700 rounded font-semibold text-xs uppercase">
                {selectedNode.bank || 'INTER-BANK'}
              </span>
            </div>
            <div className="font-mono text-xs text-slate-800 bg-white border border-slate-200 rounded-lg p-2.5 break-all select-all shadow-inner">
              {selectedNode.id}
            </div>
          </div>

          {/* Core Quantitative Metrics */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-white border border-slate-200 p-3.5 rounded-xl shadow-xs">
              <span className="text-xs font-medium text-slate-500 block mb-1">Mule Risk Score</span>
              <div className="flex items-baseline space-x-1">
                <span className={`text-2xl font-extrabold font-mono ${
                  isHighRisk ? 'text-red-600' : isMediumRisk ? 'text-amber-600' : 'text-emerald-600'
                }`}>
                  {((selectedNode.riskScore ?? 0) * 100).toFixed(0)}%
                </span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-1.5 mt-2 overflow-hidden">
                <div
                  className={`h-1.5 rounded-full ${isHighRisk ? 'bg-red-600' : isMediumRisk ? 'bg-amber-500' : 'bg-emerald-500'}`}
                  style={{ width: `${(selectedNode.riskScore ?? 0) * 100}%` }}
                />
              </div>
            </div>

            <div className="bg-white border border-slate-200 p-3.5 rounded-xl shadow-xs">
              <span className="text-xs font-medium text-slate-500 block mb-1">Pass-Through Ratio</span>
              <span className="text-2xl font-extrabold font-mono text-slate-800">
                {passThrough}%
              </span>
              <span className="text-[11px] text-slate-400 block mt-1">
                {outVolume > 0 ? 'Rapid diversion' : 'Static holding'}
              </span>
            </div>

            <div className="bg-white border border-slate-200 p-3.5 rounded-xl shadow-xs">
              <span className="text-xs font-medium text-slate-500 block mb-1">Total Flow Volume</span>
              <span className="text-xl font-extrabold font-mono text-slate-800">
                ₹{((inVolume + outVolume) / 1000).toFixed(1)}k
              </span>
              <span className="text-[11px] text-slate-400 block mt-1">
                {connectedEdges.length} inter-bank txs
              </span>
            </div>
          </div>

          {/* Topological Transaction Flow Breakdown */}
          <div>
            <h4 className="font-bold text-slate-900 mb-2.5 flex items-center gap-1.5 text-xs uppercase tracking-wider">
              <Activity className="w-4 h-4 text-indigo-600" /> Connected Multi-Bank Transactions
            </h4>
            <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
              {connectedEdges.length === 0 ? (
                <div className="p-4 text-center text-slate-400 bg-slate-50 rounded-xl border border-dashed border-slate-200">
                  No active transaction edges attached to this node
                </div>
              ) : (
                connectedEdges.map((edge, idx) => {
                  const isOutflow = edge.source === selectedNode.id;
                  return (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-2.5 bg-slate-50 hover:bg-slate-100/80 border border-slate-200/80 rounded-lg transition-colors text-xs"
                    >
                      <div className="flex items-center space-x-2">
                        <span className={`px-2 py-0.5 rounded font-bold uppercase text-[10px] ${
                          isOutflow ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'
                        }`}>
                          {isOutflow ? 'OUTFLOW' : 'INFLOW'}
                        </span>
                        <span className="font-mono text-slate-600 truncate max-w-[140px]">
                          {isOutflow ? edge.target.slice(0, 14) + '...' : edge.source.slice(0, 14) + '...'}
                        </span>
                      </div>
                      <div className="flex items-center space-x-3">
                        <span className="font-bold font-mono text-slate-900">
                          ₹{(edge.amount || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                        </span>
                        <span className="text-[11px] text-slate-400 font-mono">
                          {edge.timestamp ? new Date(edge.timestamp).toLocaleTimeString() : 'N/A'}
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Explainability Summary */}
          {selectedComponent?.shapExplanation && (
            <div className="p-4 bg-indigo-50/60 border border-indigo-100 rounded-xl text-xs text-indigo-950 space-y-1">
              <span className="font-bold uppercase tracking-wider text-indigo-700 flex items-center gap-1">
                <CheckCircle className="w-3.5 h-3.5" /> SHAP Feature Attribution Synthesis
              </span>
              <p className="leading-relaxed">
                {typeof selectedComponent.shapExplanation === 'string'
                  ? selectedComponent.shapExplanation
                  : (selectedComponent.shapExplanation as any).summary || 'High velocity cyclic transaction patterns observed across multi-bank hops.'}
              </p>
            </div>
          )}
        </div>

        {/* Modal Footer Actions */}
        <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 flex items-center justify-between">
          <button
            onClick={onClose}
            className="px-4 py-2 text-slate-600 hover:text-slate-800 font-semibold text-xs rounded-lg hover:bg-slate-200/60 transition-colors"
          >
            Close
          </button>

          <button
            onClick={() => {
              onClose();
              onLaunchInvestigation(selectedNode.id);
            }}
            className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs rounded-xl shadow-md shadow-blue-600/20 flex items-center space-x-2 transition-all hover:scale-102"
          >
            <span>Launch Flow B Deep Traversal</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
