import React, { useState } from 'react';
import { Building2, FileText, KeyRound } from 'lucide-react';

export const BankCompliancePortal: React.FC = () => {
  const [selectedBank, setSelectedBank] = useState('SBI');

  return (
    <div className="bg-slate-50 border border-slate-200 rounded-xl overflow-hidden shadow-2xl text-slate-900">
      {/* Enterprise Bank Header */}
      <div className="bg-gradient-to-r from-blue-900 to-indigo-950 text-white p-5 flex items-center justify-between shadow-md">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-blue-500/20 border border-blue-400/30 rounded-lg">
            <Building2 className="w-6 h-6 text-blue-300" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-base tracking-tight">Internal Core Banking Compliance Terminal</span>
              <span className="px-2 py-0.5 bg-emerald-500/20 text-emerald-300 border border-emerald-400/30 rounded text-[10px] font-mono uppercase tracking-wider">
                Airgapped Local Vault
              </span>
            </div>
            <p className="text-xs text-blue-200">
              Only the originating bank can decrypt its private hash and match real customer identities behind this firewall.
            </p>
          </div>
        </div>

        {/* Bank Selector */}
        <div className="flex items-center gap-2">
          <label className="text-xs text-blue-200 font-medium">Bank Node:</label>
          <select 
            value={selectedBank}
            onChange={(e) => setSelectedBank(e.target.value)}
            className="bg-blue-950/80 border border-blue-700/60 rounded-lg px-3 py-1.5 text-xs text-white font-medium focus:outline-none focus:ring-2 focus:ring-blue-400"
          >
            <option value="SBI">State Bank of India (SBIN)</option>
            <option value="HDFC">HDFC Bank (HDFC)</option>
            <option value="ICICI">ICICI Bank (ICIC)</option>
            <option value="AXIS">Axis Bank (UTIB)</option>
            <option value="PNB">Punjab National Bank (PUNB)</option>
          </select>
        </div>
      </div>

      {/* Internal Portal Content */}
      <div className="p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="border border-slate-200 bg-white rounded-xl p-5 shadow-sm">
            <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
              <KeyRound className="w-4 h-4 text-blue-600" />
              <h4 className="font-semibold text-slate-800 text-sm">Local Hash De-Anonymizer</h4>
            </div>
            <p className="text-xs text-slate-500 mt-2">
              Central Intelligence flags cryptographic hashes (`HMAC:...`). Input or select a flagged hash to resolve the customer record stored in the local core banking vault.
            </p>
            <div className="mt-4 p-3 bg-slate-50 rounded-lg border border-dashed border-slate-300 text-center">
              <span className="text-xs text-slate-400 font-mono">No alert hash queued for de-anonymization</span>
            </div>
          </div>

          <div className="border border-slate-200 bg-white rounded-xl p-5 shadow-sm">
            <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
              <FileText className="w-4 h-4 text-indigo-600" />
              <h4 className="font-semibold text-slate-800 text-sm">FIU-IND Regulatory Actions</h4>
            </div>
            <p className="text-xs text-slate-500 mt-2">
              Generate official Suspicious Transaction Reports (STRs) and apply compliance holds directly from this workstation.
            </p>
            <div className="mt-4 flex gap-2">
              <button disabled className="px-3 py-1.5 bg-slate-100 text-slate-400 text-xs font-medium rounded-lg border border-slate-200 cursor-not-allowed">
                Generate FIU-IND STR Payload
              </button>
              <button disabled className="px-3 py-1.5 bg-slate-100 text-slate-400 text-xs font-medium rounded-lg border border-slate-200 cursor-not-allowed">
                Apply Debit Freeze
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
