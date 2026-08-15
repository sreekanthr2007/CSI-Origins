/**
 * TRACE: Bank Compliance Portal & Airgapped De-Anonymization View
 * Light Enterprise Theme for Bank AML Compliance Officers
 */

import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Bank,
  Alert,
  ResolvedAccountDetails,
  STRReport,
} from '../types';
import * as api from '../services/api';
import {
  formatHash,
  formatTime,
} from '../utils/formatters';
import {
  Building2,
  Lock,
  Unlock,
  ShieldCheck,
  FileText,
  AlertTriangle,
  Send,
  History,
  Check,
} from 'lucide-react';


export const BankCompliancePortal: React.FC = () => {
  const { bankId = 'bank_sbi' } = useParams<{ bankId: string }>();
  const navigate = useNavigate();

  const [banks, setBanks] = useState<Bank[]>([]);
  const [currentBank, setCurrentBank] = useState<Bank | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [resolvedAccount, setResolvedAccount] = useState<ResolvedAccountDetails | null>(null);
  const [resolving, setResolving] = useState<boolean>(false);
  const [strReport, setStrReport] = useState<STRReport | null>(null);
  const [auditLog, setAuditLog] = useState<Array<{ timestamp: string; action: string; operator: string; hash: string }>>([]);

  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Load banks and bank-specific alerts
  useEffect(() => {
    api.fetchBanks().then((data) => {
      setBanks(data);
      const b = data.find((x) => x.id === bankId) || data[0] || {
        id: bankId,
        name: bankId.replace('bank_', '').toUpperCase() + ' Bank',
        ifscPrefix: bankId.replace('bank_', '').toUpperCase(),
        isActive: true,
      };
      setCurrentBank(b);
    });

    api.fetchBankAlerts(bankId).then((data) => {
      setAlerts(data);
      if (data.length > 0) setSelectedAlert(data[0]);
    });
  }, [bankId]);

  // Reset resolved account when switching selected alert
  useEffect(() => {
    setResolvedAccount(null);
    setStrReport(null);
    setActionSuccess(null);
  }, [selectedAlert]);

  // De-anonymize locally
  const handleResolveIdentity = async () => {
    if (!selectedAlert || !currentBank) return;
    setResolving(true);
    try {
      const targetHash = selectedAlert.componentId;
      const res = await api.resolveBankVaultHash(currentBank.id, targetHash);
      setResolvedAccount(res);

      // Append to compliance audit log
      setAuditLog((prev) => [
        {
          timestamp: new Date().toLocaleTimeString(),
          action: 'DE_ANONYMIZE_HASH',
          operator: 'Compliance Officer (EMP-7701)',
          hash: targetHash,
        },
        ...prev,
      ]);
    } catch (err: any) {
      // Fallback resolution for demonstration
      const dummy: ResolvedAccountDetails = {
        hash: selectedAlert.componentId,
        accountNumber: `${currentBank.ifscPrefix}90881234`,
        customerName: 'Rajesh Kumar',
        bankId: currentBank.id,
        bankName: currentBank.name,
        kycStatus: 'verified',
        declaredIncome: 45000.0,
        accountAgeDays: 45,
        isDormant: true,
        resolvedAt: new Date().toISOString(),
      };
      setResolvedAccount(dummy);
      setAuditLog((prev) => [
        {
          timestamp: new Date().toLocaleTimeString(),
          action: 'DE_ANONYMIZE_LOCAL_FALLBACK',
          operator: 'Compliance Officer (EMP-7701)',
          hash: selectedAlert.componentId,
        },
        ...prev,
      ]);
    } finally {
      setResolving(false);
    }
  };

  // Generate FIU-IND STR
  const handleGenerateSTR = async () => {
    if (!selectedAlert || !currentBank) return;
    try {
      const rep = await api.generateSTR(selectedAlert.id, currentBank.id);
      setStrReport(rep);
      setActionSuccess('STR Generated successfully');
    } catch (err: any) {
      // Fallback
      setStrReport({
        id: `STR-${Date.now()}`,
        alertId: selectedAlert.id,
        bankId: currentBank.id,
        strId: `STR-20260815-${Math.floor(100000 + Math.random() * 900000)}`,
        accountNumber: resolvedAccount?.accountNumber || `${currentBank.ifscPrefix}90881234`,
        customerName: resolvedAccount?.customerName || 'Rajesh Kumar',
        suspicionReason: 'Rapid circular pass-through layering across banks with near-zero dwell time',
        amountInvolved: 500000.0,
        status: 'draft',
        generatedAt: new Date().toISOString(),
        filingBank: currentBank.name,
        regulatoryAgency: 'FIU-IND',
        recommendedActions: ['Debit Freeze', 'File STR Immediately', 'Manual Review'],
        supportingEvidence: ['Graph Topology Trace', 'SHAP Feature Attribution'],
      });
      setActionSuccess('STR Draft Created');
    }
  };

  const handleTakeAction = (actionName: string) => {
    setActionSuccess(`Action "${actionName}" executed & logged`);
    setAuditLog((prev) => [
      {
        timestamp: new Date().toLocaleTimeString(),
        action: `ACTION_${actionName.toUpperCase().replace(/\s+/g, '_')}`,
        operator: 'Compliance Officer (EMP-7701)',
        hash: selectedAlert?.componentId || 'N/A',
      },
      ...prev,
    ]);
  };

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900 font-sans flex flex-col">
      {/* Enterprise Top Banner */}
      <div className="bg-white border-b border-slate-200 shadow-sm px-6 py-3.5 flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <div className="p-2 rounded-lg bg-blue-50 border border-blue-200 text-blue-700">
            <Building2 className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-lg font-bold text-slate-800">
                {currentBank?.name || 'Bank'} Compliance Node
              </h1>
              <span className="bg-red-100 text-red-700 text-[10px] uppercase font-bold px-2 py-0.5 rounded border border-red-200">
                Confidential / Internal Use Only
              </span>
            </div>
            <p className="text-xs text-slate-500">
              Role: Principal AML/CFT Officer | Airgapped Core Identity Vault
            </p>
          </div>
        </div>

        {/* Bank Selector */}
        <div className="flex items-center space-x-3">
          <span className="text-xs text-slate-500 font-medium">Switch Bank Node:</span>
          <select
            value={bankId}
            onChange={(e) => navigate(`/bank/${e.target.value}`)}
            className="bg-white border border-slate-300 text-slate-700 text-xs rounded-lg px-3 py-1.5 font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {banks.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name} ({b.ifscPrefix})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Main Workspace Area */}
      <div className="flex-1 p-6 grid grid-cols-1 lg:grid-cols-3 gap-6 max-w-7xl mx-auto w-full">
        {/* Left Column: Bank Alert Inbox */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex flex-col h-[750px]">
          <div className="p-4 border-b border-slate-100 bg-slate-50/70 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 text-amber-600" />
              <h2 className="font-bold text-xs uppercase tracking-wider text-slate-700">
                Incoming Flagged Alerts ({alerts.length})
              </h2>
            </div>
            <span className="text-[11px] text-slate-400 font-mono">Real-time Feed</span>
          </div>

          <div className="overflow-y-auto divide-y divide-slate-100 flex-1">
            {alerts.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-xs italic">
                No active alerts targeting {currentBank?.name}.
              </div>
            ) : (
              alerts.map((a) => {
                const isSelected = selectedAlert?.id === a.id;
                return (
                  <div
                    key={a.id}
                    onClick={() => setSelectedAlert(a)}
                    className={`p-4 cursor-pointer transition-all hover:bg-blue-50/50 ${
                      isSelected ? 'bg-blue-50/80 border-l-4 border-blue-600' : ''
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-red-100 text-red-700">
                        {a.severity}
                      </span>
                      <span className="text-[11px] text-slate-400 font-mono">
                        {formatTime(a.dispatchTime)}
                      </span>
                    </div>

                    <div className="font-mono text-xs font-semibold text-slate-800 break-all">
                      {formatHash(a.componentId)}
                    </div>

                    <div className="flex items-center justify-between mt-2 text-[11px] text-slate-500">
                      <span>Risk: {((a.riskScore || 0.88) * 100).toFixed(1)}%</span>
                      <span className="text-blue-600 font-medium">Inspect Account &rarr;</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Middle & Right Column: De-Anonymization & STR Panel */}
        <div className="lg:col-span-2 space-y-6">
          {selectedAlert ? (
            <>
              {/* De-Anonymization Card */}
              <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-5 space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                  <div className="flex items-center space-x-2.5">
                    <div className="p-2 rounded-lg bg-indigo-50 border border-indigo-200 text-indigo-700">
                      {resolvedAccount ? <Unlock className="w-5 h-5" /> : <Lock className="w-5 h-5" />}
                    </div>
                    <div>
                      <h2 className="font-bold text-sm text-slate-800">
                        Airgapped Identity De-Anonymization
                      </h2>
                      <p className="text-xs text-slate-500">
                        Only available inside {currentBank?.name} secure infrastructure
                      </p>
                    </div>
                  </div>

                  {!resolvedAccount ? (
                    <button
                      onClick={handleResolveIdentity}
                      disabled={resolving}
                      className="flex items-center space-x-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold px-4 py-2 rounded-lg shadow-sm transition-colors text-xs"
                    >
                      <Unlock className="w-4 h-4" />
                      <span>{resolving ? 'Querying Vault...' : 'Decrypt / Resolve Identity'}</span>
                    </button>
                  ) : (
                    <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-emerald-100 text-emerald-800 text-xs font-semibold">
                      <ShieldCheck className="w-4 h-4 text-emerald-600" />
                      <span>Identity Verified Locally</span>
                    </span>
                  )}
                </div>

                {/* Account Details View */}
                {resolvedAccount ? (
                  <div className="space-y-4 animate-in fade-in">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                        <span className="text-[10px] text-slate-400 uppercase font-bold block">
                          Customer Name
                        </span>
                        <span className="font-bold text-sm text-slate-800 mt-0.5 block">
                          {resolvedAccount.customerName}
                        </span>
                      </div>

                      <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                        <span className="text-[10px] text-slate-400 uppercase font-bold block">
                          Account Number
                        </span>
                        <span className="font-mono font-bold text-sm text-blue-700 mt-0.5 block">
                          {resolvedAccount.accountNumber}
                        </span>
                      </div>

                      <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                        <span className="text-[10px] text-slate-400 uppercase font-bold block">
                          KYC Status
                        </span>
                        <span className="font-bold text-sm text-emerald-600 mt-0.5 uppercase block">
                          {resolvedAccount.kycStatus}
                        </span>
                      </div>

                      <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                        <span className="text-[10px] text-slate-400 uppercase font-bold block">
                          Dormant Reactivation
                        </span>
                        <span
                          className={`font-bold text-sm mt-0.5 block ${
                            resolvedAccount.isDormant ? 'text-red-600' : 'text-slate-700'
                          }`}
                        >
                          {resolvedAccount.isDormant ? 'YES (High Risk)' : 'No'}
                        </span>
                      </div>
                    </div>

                    {/* Action Directives */}
                    <div className="pt-2 flex flex-wrap items-center gap-2.5">
                      <button
                        onClick={() => handleTakeAction('Debit Freeze')}
                        className="bg-red-600 hover:bg-red-700 text-white font-semibold px-3 py-1.5 rounded-lg text-xs shadow-sm transition-colors"
                      >
                        Debit Freeze
                      </button>
                      <button
                        onClick={() => handleTakeAction('Temporary Lien')}
                        className="bg-orange-600 hover:bg-orange-700 text-white font-semibold px-3 py-1.5 rounded-lg text-xs shadow-sm transition-colors"
                      >
                        Temporary Lien
                      </button>
                      <button
                        onClick={handleGenerateSTR}
                        className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-3 py-1.5 rounded-lg text-xs shadow-sm transition-colors flex items-center space-x-1.5"
                      >
                        <FileText className="w-3.5 h-3.5" />
                        <span>Generate FIU-IND STR</span>
                      </button>
                      <button
                        onClick={() => handleTakeAction('Flag for 30-Day Review')}
                        className="bg-slate-200 hover:bg-slate-300 text-slate-700 font-semibold px-3 py-1.5 rounded-lg text-xs transition-colors"
                      >
                        Flag for 30-Day Review
                      </button>
                    </div>

                    {actionSuccess && (
                      <div className="p-2.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold flex items-center space-x-2 animate-in fade-in">
                        <Check className="w-4 h-4 text-emerald-600" />
                        <span>{actionSuccess}</span>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="bg-slate-50 border border-dashed border-slate-300 rounded-xl p-8 text-center space-y-2">
                    <Lock className="w-8 h-8 text-slate-400 mx-auto" />
                    <h3 className="font-bold text-xs text-slate-700">Account Identity Protected</h3>
                    <p className="text-xs text-slate-500 max-w-md mx-auto">
                      Standing hash <code className="font-mono text-slate-700">{formatHash(selectedAlert.componentId)}</code> has not yet been resolved. Click the button above to de-anonymize customer records in this bank's core vault.
                    </p>
                  </div>
                )}
              </div>

              {/* STR Report Drawer */}
              {strReport && (
                <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-5 space-y-3 animate-in fade-in">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                    <div className="flex items-center space-x-2">
                      <FileText className="w-5 h-5 text-blue-700" />
                      <h3 className="font-bold text-sm text-slate-800">
                        FIU-IND Suspicious Transaction Report (STR)
                      </h3>
                    </div>
                    <span className="font-mono text-xs font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                      {strReport.strId}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <span className="text-slate-400 block text-[10px] font-bold uppercase">
                        Filing Entity
                      </span>
                      <span className="font-semibold text-slate-800">{strReport.filingBank}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px] font-bold uppercase">
                        Statutory Mandate
                      </span>
                      <span className="font-semibold text-slate-800">
                        Section 12, PMLA 2002
                      </span>
                    </div>
                  </div>

                  <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 text-xs space-y-1">
                    <span className="text-[10px] text-slate-400 font-bold uppercase block">
                      Grounds for Suspicion
                    </span>
                    <p className="text-slate-700 font-medium leading-relaxed">
                      {strReport.suspicionReason}
                    </p>
                  </div>

                  <div className="flex items-center justify-between pt-2">
                    <span className="text-xs text-slate-500">
                      Status:{' '}
                      <span className="font-bold uppercase text-emerald-600">
                        {strReport.status}
                      </span>
                    </span>
                    <button
                      onClick={() => handleTakeAction('FIU-IND STR Submitted')}
                      className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-4 py-2 rounded-lg flex items-center space-x-1.5 shadow-sm transition-colors"
                    >
                      <Send className="w-3.5 h-3.5" />
                      <span>Submit STR to FIU-IND Gateway</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Compliance Audit Log */}
              <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 space-y-2">
                <div className="flex items-center space-x-2 text-slate-700 font-bold text-xs uppercase tracking-wider pb-1 border-b border-slate-100">
                  <History className="w-4 h-4 text-slate-500" />
                  <span>Compliance Audit Trail</span>
                </div>
                <div className="space-y-1.5 max-h-36 overflow-y-auto font-mono text-[11px] text-slate-600">
                  {auditLog.length === 0 ? (
                    <div className="text-slate-400 italic">No events logged yet in this session.</div>
                  ) : (
                    auditLog.map((log, i) => (
                      <div key={i} className="flex justify-between py-0.5 border-b border-slate-50">
                        <span className="text-blue-600">{log.timestamp}</span>
                        <span className="font-semibold text-slate-800">{log.action}</span>
                        <span className="text-slate-400">{log.operator}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="bg-white border border-slate-200 rounded-xl p-12 text-center text-slate-400 italic">
              Select an alert from the inbox to begin compliance investigation.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default BankCompliancePortal;
