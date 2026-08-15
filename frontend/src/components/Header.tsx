/**
 * TRACE: Application Top Navigation Header
 */

import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { PortalToggle } from './PortalToggle';
import {
  RefreshCw,
  Zap,
} from 'lucide-react';
import * as api from '../services/api';

interface HeaderProps {
  onRefreshGraph?: () => void;
  onGenerateData?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onRefreshGraph, onGenerateData }) => {
  const location = useLocation();
  const isBankPortal = location.pathname.startsWith('/bank');
  const [backendHealthy, setBackendHealthy] = useState<boolean>(true);
  const [generating, setGenerating] = useState<boolean>(false);


  // Backend Health Ping
  useEffect(() => {
    const checkHealth = async () => {
      try {
        await api.fetchGraphStats();
        setBackendHealthy(true);
      } catch {
        setBackendHealthy(false);
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      if (onGenerateData) {
        await onGenerateData();
      } else {
        await api.triggerSyntheticGeneration();
      }
      if (onRefreshGraph) onRefreshGraph();
    } catch (err) {
      console.error('Data generation failed:', err);
    } finally {
      setGenerating(false);
    }
  };


  return (
    <header className="border-b px-6 py-3.5 flex items-center justify-between transition-colors bg-white border-slate-200 text-slate-900 shadow-xs">
      {/* Brand & Logo */}
      <div className="flex items-center space-x-3">
        <div className="flex items-center justify-center w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 text-white font-black text-sm tracking-wider shadow-md shadow-blue-600/20">
          TR
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <span className="font-extrabold text-base tracking-tight text-slate-900">
              TRACE
            </span>
            <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 border border-blue-200 font-bold">
              v1.0-RC
            </span>
          </div>
          <p className="text-[11px] text-slate-500 hidden sm:block">
            Cross-Bank Mule Account Detection Network
          </p>
        </div>
      </div>

      {/* Center Actions / Status */}
      <div className="flex items-center space-x-4">
        {/* Backend Connectivity Indicator */}
        <div
          className={`flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${
            backendHealthy
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : 'bg-red-50 text-red-700 border-red-200'
          }`}
        >
          <span
            className={`w-2 h-2 rounded-full ${
              backendHealthy ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'
            }`}
          />
          <span className="text-[11px] font-medium">
            {backendHealthy ? 'System Active' : 'Disconnected'}
          </span>
        </div>

        {/* Quick Data Synthesis Trigger */}
        {!isBankPortal && (
          <div className="flex items-center space-x-2">
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="flex items-center space-x-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-3.5 py-1.5 rounded-xl shadow-xs transition-all hover:scale-102 cursor-pointer disabled:opacity-50"
            >
              <Zap className={`w-3.5 h-3.5 ${generating ? 'animate-spin' : ''}`} />
              <span>{generating ? 'Synthesizing...' : '⚡ Synthesize Data'}</span>
            </button>

            {onRefreshGraph && (
              <button
                onClick={onRefreshGraph}
                className="p-1.5 rounded-xl bg-slate-100 border border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-200 transition-colors cursor-pointer"
                title="Refresh Graph"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        )}
      </div>

      {/* Right: Dual-Portal Toggle */}
      <div className="flex items-center space-x-3">
        <PortalToggle />
      </div>
    </header>
  );
};


export default Header;
