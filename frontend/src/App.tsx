import { useState, useEffect } from 'react';
import { Network, Building2, Cpu, EyeOff } from 'lucide-react';
import { NetworkGraph } from './components/NetworkGraph';
import { AlertTable } from './components/AlertTable';
import { ExplainabilityView } from './components/ExplainabilityView';
import { InvestigationWorkbench } from './components/InvestigationWorkbench';
import { BankCompliancePortal } from './components/BankCompliancePortal';
import { fetchHealth } from './services/api';

export function App() {
  const [activeTab, setActiveTab] = useState<'central' | 'bank'>('central');
  const [backendStatus, setBackendStatus] = useState<'online' | 'offline' | 'checking'>('checking');

  useEffect(() => {
    fetchHealth()
      .then(() => setBackendStatus('online'))
      .catch(() => setBackendStatus('offline'));
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-indigo-500 selection:text-white">
      {/* Top Navbar */}
      <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Logo & Title */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 p-0.5 shadow-lg shadow-indigo-500/20">
              <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
                <Network className="w-5 h-5 text-indigo-400" />
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-base tracking-tight text-white">Cross-Bank Mule Detection</span>
                <span className="px-2 py-0.5 bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 rounded text-[10px] font-semibold tracking-wide uppercase">
                  IDPIC Intelligence
                </span>
              </div>
              <p className="text-xs text-slate-400">Privacy-Preserving Federated Graph Network</p>
            </div>
          </div>

          {/* Navigation Toggle */}
          <div className="flex items-center gap-1 bg-slate-900 p-1 rounded-xl border border-slate-800">
            <button
              onClick={() => setActiveTab('central')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === 'central'
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Cpu className="w-3.5 h-3.5" />
              Central Intelligence
            </button>
            <button
              onClick={() => setActiveTab('bank')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === 'bank'
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-600/30 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Building2 className="w-3.5 h-3.5" />
              Bank Compliance Portal
            </button>
          </div>

          {/* Status Indicator */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-xs font-mono px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800">
              <span className={`w-2 h-2 rounded-full ${backendStatus === 'online' ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'}`} />
              <span className="text-slate-300">API: {backendStatus.toUpperCase()}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Body */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex-1 w-full">
        {activeTab === 'central' ? (
          <div className="space-y-6">
            {/* Privacy Guarantee Banner */}
            <div className="bg-gradient-to-r from-indigo-950/60 via-slate-900/60 to-slate-950/60 border border-indigo-500/20 rounded-xl p-4 flex items-center justify-between shadow-lg">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-indigo-500/10 border border-indigo-500/30 rounded-lg text-indigo-400">
                  <EyeOff className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-white">Central Operations (Zero PII Guarantee)</h4>
                  <p className="text-xs text-slate-400">
                    All nodes are HMAC-SHA256 hashed. Central systems never ingest or display real customer names, account numbers, or PANs.
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-1 bg-slate-800/80 border border-slate-700 rounded text-xs font-mono text-indigo-300">
                  HMAC Standing Key Active
                </span>
              </div>
            </div>

            {/* Top Grid: Graph & Alerts */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2">
                <NetworkGraph />
              </div>
              <div>
                <AlertTable />
              </div>
            </div>

            {/* Bottom Grid: Explainability & Investigation */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <ExplainabilityView />
              <InvestigationWorkbench />
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            <BankCompliancePortal />
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950/80 py-4 text-center text-xs text-slate-500">
        Cross-Bank Mule Detection Platform • IDPIC Privacy-Preserving Architecture
      </footer>
    </div>
  );
}

export default App;
