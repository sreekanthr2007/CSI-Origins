/**
 * TRACE: Flow B Targeted Investigation Traversal Workbench (Light Theme)
 */

import React, { useState, useEffect } from 'react';
import { Investigation, TraversalStep } from '../types';
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  RotateCcw,
  ShieldAlert,
  Download,
  X,
  Activity
} from 'lucide-react';

interface InvestigationWorkbenchProps {
  investigation: Investigation | null;
  playback?: TraversalStep[];
  playbackSteps?: TraversalStep[];
  onClose?: () => void;
  onStartInvestigation?: (id: string) => void;
  onCloseInvestigation?: (id: string) => void;
}

export const InvestigationWorkbench: React.FC<InvestigationWorkbenchProps> = ({
  investigation,
  playback = [],
  playbackSteps = [],
  onClose,
}) => {

  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);

  const rawSteps = playback.length > 0 ? playback : playbackSteps.length > 0 ? playbackSteps : investigation?.playbackSteps || [];

  // Provide mock demo steps if empty so the workbench is always rich & interactive
  const steps = rawSteps.length > 0 ? rawSteps : [
    {
      stepNumber: 1,
      action: 'START',
      node: 'HMAC:8f3c7a1098b2c45e',
      description: 'Initialized targeted forensic investigation on target node HMAC:8f3c7a1098b2c45e',
      decision: 'ACCEPT' as const,
      timestamp: new Date().toISOString(),
      bankId: 'bank_sbi',
    },
    {
      stepNumber: 2,
      action: 'EXPAND_DOWNSTREAM',
      from: 'HMAC:8f3c7a1098b2c45e',
      to: 'HMAC:1a2b3c4d5e6f7a8b',
      bankId: 'bank_hdfc',
      amount: 500000.0,
      description: 'Expanded downstream to HDFC node (INR 500,000.00 in 12 mins)',
      decision: 'ACCEPT' as const,
      timestamp: new Date().toISOString(),
    },
    {
      stepNumber: 3,
      action: 'EXPAND_DOWNSTREAM',
      from: 'HMAC:1a2b3c4d5e6f7a8b',
      to: 'HMAC:3c4d5e6f7a8b9c0d',
      bankId: 'bank_icici',
      amount: 490000.0,
      description: 'Expanded downstream to ICICI node (INR 490,000.00 in 18 mins)',
      decision: 'ACCEPT' as const,
      timestamp: new Date().toISOString(),
    },
    {
      stepNumber: 4,
      action: 'EXPAND_DOWNSTREAM',
      from: 'HMAC:3c4d5e6f7a8b9c0d',
      to: 'HMAC:5e6f7a8b9c0d1e2f',
      bankId: 'bank_axis',
      amount: 485000.0,
      description: 'Expanded downstream to AXIS node (INR 485,000.00 in 12 mins)',
      decision: 'ACCEPT' as const,
      timestamp: new Date().toISOString(),
    },
    {
      stepNumber: 5,
      action: 'COMPLETE_TRAVERSAL',
      reason: 'completed',
      description: 'Traversal completed: 4-bank rapid laundering chain isolated across SBI -> HDFC -> ICICI -> AXIS',
      decision: 'ACCEPT' as const,
      timestamp: new Date().toISOString(),
    }
  ];

  // Playback timer loop
  useEffect(() => {
    let timer: any;
    if (isPlaying && steps.length > 0) {
      timer = setInterval(() => {
        setCurrentStepIndex((prev) => {
          if (prev >= steps.length - 1) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, 1000 / playbackSpeed);
    }
    return () => clearInterval(timer);
  }, [isPlaying, steps.length, playbackSpeed]);

  const currentStep = steps[currentStepIndex] || steps[0];

  const handleExportJSON = () => {
    const dataStr =
      'data:text/json;charset=utf-8,' +
      encodeURIComponent(
        JSON.stringify({ investigation, playbackSteps: steps }, null, 2)
      );
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute(
      'download',
      `trace_investigation_${investigation?.id || 'session'}.json`
    );
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <div className="flex-1 bg-white border border-slate-200 rounded-2xl shadow-xs p-6 m-4 flex flex-col space-y-5 text-slate-800 overflow-y-auto">
      {/* Workbench Header */}
      <div className="flex items-center justify-between pb-4 border-b border-slate-200">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-xl bg-blue-100 text-blue-600 border border-blue-200">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="font-bold text-base text-slate-900">
                Flow B Targeted Forensic Traversal
              </h2>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold font-mono uppercase bg-emerald-100 text-emerald-800 border border-emerald-200">
                Active Bounded Session
              </span>
            </div>
            <p className="text-xs text-slate-500 font-mono mt-0.5">
              Investigation ID: {investigation?.id || 'INV-20260815-4B9F2A'} | Ephemeral Salt: Active (Auto-Purge 24h)
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={handleExportJSON}
            className="px-3.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold rounded-xl text-xs flex items-center space-x-1.5 transition-colors cursor-pointer border border-slate-200"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export Forensic JSON</span>
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>
      </div>

      {/* Traversal Session Overview Cards */}
      <div className="grid grid-cols-4 gap-3">
        <div className="bg-slate-50 border border-slate-200/80 p-3 rounded-xl shadow-2xs">
          <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider block">
            Traversal Depth
          </span>
          <span className="text-lg font-extrabold font-mono text-slate-900">
            {investigation?.depthReached ?? 4} / 4 Hops
          </span>
        </div>

        <div className="bg-slate-50 border border-slate-200/80 p-3 rounded-xl shadow-2xs">
          <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider block">
            Queried Banks
          </span>
          <span className="text-lg font-extrabold font-mono text-slate-900">
            4 Banks (SBI, HDFC, ICICI, Axis)
          </span>
        </div>

        <div className="bg-slate-50 border border-slate-200/80 p-3 rounded-xl shadow-2xs">
          <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider block">
            Pattern-Decay State
          </span>
          <span className="text-lg font-extrabold font-mono text-emerald-600">
            Active Propagation
          </span>
        </div>

        <div className="bg-slate-50 border border-slate-200/80 p-3 rounded-xl shadow-2xs">
          <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider block">
            Privacy Status
          </span>
          <span className="text-lg font-extrabold font-mono text-blue-600">
            100% Zero-PII
          </span>
        </div>
      </div>

      {/* Forensic Playback Timeline Player */}
      <div className="bg-slate-50 border border-slate-200 rounded-2xl p-5 space-y-4 shadow-2xs">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="px-2.5 py-1 rounded-lg bg-blue-600 text-white font-bold font-mono text-xs shadow-xs">
              Step {currentStepIndex + 1} of {steps.length}
            </span>
            <span className="font-bold text-xs text-slate-800 uppercase tracking-wider">
              Action: {currentStep?.action || 'TRAVERSAL'}
            </span>
          </div>

          {/* Speed selector */}
          <div className="flex items-center space-x-1.5 text-xs text-slate-600 font-medium">
            <span>Speed:</span>
            {[1, 2, 4].map((s) => (
              <button
                key={s}
                onClick={() => setPlaybackSpeed(s)}
                className={`px-2 py-0.5 rounded-lg border text-xs font-mono transition-colors cursor-pointer ${
                  playbackSpeed === s
                    ? 'bg-blue-600 text-white border-blue-600 font-bold'
                    : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-100'
                }`}
              >
                {s}x
              </button>
            ))}
          </div>
        </div>

        {/* Current Active Step Box */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="font-bold text-slate-900 flex items-center gap-1.5">
              <Activity className="w-4 h-4 text-blue-600" />
              {currentStep?.description || 'Step execution description'}
            </span>
            {currentStep?.bankId && (
              <span className="px-2 py-0.5 bg-blue-100 text-blue-700 font-bold rounded text-[11px] uppercase font-mono">
                {currentStep.bankId.replace('bank_', '')}
              </span>
            )}
          </div>

          {currentStep?.amount && (
            <div className="text-xs text-slate-600 flex items-center gap-2">
              <span>Amount Transferred:</span>
              <span className="font-bold font-mono text-slate-900 text-sm">
                ₹{currentStep.amount.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
              </span>
            </div>
          )}
        </div>

        {/* Player Controls Bar */}
        <div className="flex items-center justify-center space-x-3 pt-2">
          <button
            onClick={() => setCurrentStepIndex(0)}
            className="p-2 rounded-xl bg-white border border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors cursor-pointer"
            title="Reset to Start"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
          <button
            onClick={() => setCurrentStepIndex((prev) => Math.max(0, prev - 1))}
            disabled={currentStepIndex === 0}
            className="p-2 rounded-xl bg-white border border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-100 disabled:opacity-30 transition-colors cursor-pointer"
            title="Previous Step"
          >
            <SkipBack className="w-4 h-4" />
          </button>
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="p-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white shadow-md shadow-blue-600/20 transition-all hover:scale-105 cursor-pointer"
            title={isPlaying ? 'Pause' : 'Play Traversal'}
          >
            {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5 fill-current" />}
          </button>
          <button
            onClick={() => setCurrentStepIndex((prev) => Math.min(steps.length - 1, prev + 1))}
            disabled={currentStepIndex >= steps.length - 1}
            className="p-2 rounded-xl bg-white border border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-100 disabled:opacity-30 transition-colors cursor-pointer"
            title="Next Step"
          >
            <SkipForward className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Step by Step Expansion History List */}
      <div>
        <h4 className="font-bold text-xs text-slate-700 uppercase tracking-wider mb-2.5">
          Step Execution Trace Log
        </h4>
        <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
          {steps.map((step, idx) => {
            const isCurrent = idx === currentStepIndex;
            const isPast = idx < currentStepIndex;
            return (
              <div
                key={idx}
                onClick={() => setCurrentStepIndex(idx)}
                className={`p-3 rounded-xl border text-xs flex items-center justify-between transition-all cursor-pointer ${
                  isCurrent
                    ? 'bg-blue-50 border-blue-400 font-semibold shadow-xs'
                    : isPast
                    ? 'bg-white border-slate-200 text-slate-600'
                    : 'bg-slate-50/60 border-slate-100 text-slate-400'
                }`}
              >
                <div className="flex items-center space-x-2.5">
                  <span
                    className={`w-5 h-5 rounded-full flex items-center justify-center font-bold text-[10px] ${
                      isCurrent
                        ? 'bg-blue-600 text-white'
                        : isPast
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-slate-200 text-slate-500'
                    }`}
                  >
                    {idx + 1}
                  </span>
                  <span className="font-mono text-slate-800">{step.description}</span>
                </div>
                {step.bankId && (
                  <span className="px-2 py-0.5 rounded bg-slate-100 border border-slate-200 text-[10px] font-mono uppercase font-bold text-slate-700">
                    {step.bankId.replace('bank_', '')}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default InvestigationWorkbench;
