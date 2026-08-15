import React, { useState } from 'react';
import { Alert } from '../types';
import {
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Search,
  Sparkles,
} from 'lucide-react';

interface AlertTableProps {
  alerts: Alert[];
  onInvestigate?: (componentId: string) => void;
  onDispatch?: (componentId: string, riskScore: number) => void;
  onResolve?: (alertId: string, notes?: string) => void;
  onExplain?: (alert: Alert) => void;
  onSelectAlert?: (alert: Alert) => void;
  onExplainAlert?: (alert: Alert) => void;
  onDispatchAlert?: (componentId: string, riskScore: number) => void;
  onResolveAlert?: (alertId: string, notes?: string) => void;
  loading?: boolean;
}

export const AlertTable: React.FC<AlertTableProps> = ({
  alerts,
  onResolve,
  onExplain,
  onExplainAlert,
  onResolveAlert,
}) => {

  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [expandedAlertId, setExpandedAlertId] = useState<string | null>(null);
  const [sortField, setSortField] = useState<'riskScore' | 'dispatchTime' | 'severity'>('dispatchTime');
  const [sortAsc, setSortAsc] = useState<boolean>(false);

  const handleResolve = onResolve || onResolveAlert;
  const handleExplain = onExplain || onExplainAlert;


  const filteredAlerts = alerts
    .filter((a) => {
      if (severityFilter !== 'all' && a.severity !== severityFilter) return false;
      if (statusFilter !== 'all' && a.status !== statusFilter) return false;
      if (
        searchQuery &&
        !a.componentId?.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !a.id?.toLowerCase().includes(searchQuery.toLowerCase())
      ) {
        return false;
      }
      return true;
    })
    .sort((a, b) => {
      let valA: any = a[sortField];
      let valB: any = b[sortField];
      if (sortField === 'dispatchTime') {
        valA = new Date(a.dispatchTime || 0).getTime();
        valB = new Date(b.dispatchTime || 0).getTime();
      }
      if (valA < valB) return sortAsc ? -1 : 1;
      if (valA > valB) return sortAsc ? 1 : -1;
      return 0;
    });

  const toggleSort = (field: 'riskScore' | 'dispatchTime' | 'severity') => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xs flex flex-col h-full">
      {/* Table Header Controls */}
      <div className="p-4 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3 bg-slate-50/70">
        <div className="flex items-center space-x-2.5">
          <div className="p-2 rounded-xl bg-amber-100 text-amber-800 border border-amber-200">
            <AlertTriangle className="w-4 h-4" />
          </div>
          <div>
            <h2 className="font-bold text-sm text-slate-900 uppercase tracking-wider">
              Cross-Bank Alert Queue ({filteredAlerts.length})
            </h2>
            <span className="text-[11px] text-slate-500">Coordinated Multi-Institution Monitoring</span>
          </div>
        </div>

        {/* Search & Filters */}
        <div className="flex items-center space-x-3 text-xs">
          <div className="flex items-center space-x-2 bg-white border border-slate-200 rounded-xl px-3 py-1.5 shadow-2xs">
            <Search className="w-3.5 h-3.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search alert / component..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-transparent text-slate-800 focus:outline-none placeholder-slate-400 text-xs w-44"
            />
          </div>

          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="bg-white border border-slate-200 text-slate-700 rounded-xl px-2.5 py-1.5 focus:outline-none font-medium shadow-2xs"
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-white border border-slate-200 text-slate-700 rounded-xl px-2.5 py-1.5 focus:outline-none font-medium shadow-2xs"
          >
            <option value="all">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="dispatched">Dispatched</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="resolved">Resolved</option>
          </select>
        </div>
      </div>

      {/* Table Content */}
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50/90 text-slate-500 font-semibold uppercase tracking-wider">
              <th className="py-3 px-4">Alert & Component</th>
              <th
                className="py-3 px-4 cursor-pointer hover:text-slate-900"
                onClick={() => toggleSort('severity')}
              >
                <div className="flex items-center space-x-1">
                  <span>Severity</span>
                  {sortField === 'severity' && (sortAsc ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />)}
                </div>
              </th>
              <th
                className="py-3 px-4 cursor-pointer hover:text-slate-900"
                onClick={() => toggleSort('riskScore')}
              >
                <div className="flex items-center space-x-1">
                  <span>Risk Score</span>
                  {sortField === 'riskScore' && (sortAsc ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />)}
                </div>
              </th>
              <th className="py-3 px-4">Involved Banks</th>
              <th
                className="py-3 px-4 cursor-pointer hover:text-slate-900"
                onClick={() => toggleSort('dispatchTime')}
              >
                <div className="flex items-center space-x-1">
                  <span>Time</span>
                  {sortField === 'dispatchTime' && (sortAsc ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />)}
                </div>
              </th>
              <th className="py-3 px-4">Status</th>
              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filteredAlerts.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-12 text-center text-slate-400">
                  No alerts match current search filters
                </td>
              </tr>
            ) : (
              filteredAlerts.map((alert) => {
                const isExpanded = expandedAlertId === alert.id;
                const isCritical = alert.severity === 'critical';
                const isHigh = alert.severity === 'high';

                return (
                  <React.Fragment key={alert.id}>
                    <tr
                      onClick={() => setExpandedAlertId(isExpanded ? null : alert.id)}
                      className={`hover:bg-slate-50/80 transition-colors cursor-pointer ${
                        isExpanded ? 'bg-blue-50/40' : ''
                      }`}
                    >
                      <td className="py-3 px-4">
                        <div className="font-bold text-slate-900 font-mono">
                          {alert.id.slice(0, 16)}...
                        </div>
                        <div className="text-[11px] text-slate-400 font-mono">
                          {alert.componentId}
                        </div>
                      </td>

                      <td className="py-3 px-4">
                        <span
                          className={`px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase font-mono tracking-wider ${
                            isCritical
                              ? 'bg-red-100 text-red-700 border border-red-200'
                              : isHigh
                              ? 'bg-amber-100 text-amber-800 border border-amber-200'
                              : 'bg-blue-100 text-blue-700 border border-blue-200'
                          }`}
                        >
                          {alert.severity}
                        </span>
                      </td>

                      <td className="py-3 px-4">
                        <div className="flex items-center space-x-2">
                          <span className="font-extrabold font-mono text-slate-900">
                            {((alert.riskScore || 0) * 100).toFixed(0)}%
                          </span>
                          <div className="w-16 bg-slate-100 rounded-full h-1.5 overflow-hidden">
                            <div
                              className={`h-1.5 rounded-full ${
                                isCritical ? 'bg-red-600' : isHigh ? 'bg-amber-500' : 'bg-blue-600'
                              }`}
                              style={{ width: `${(alert.riskScore || 0) * 100}%` }}
                            />
                          </div>
                        </div>
                      </td>

                      <td className="py-3 px-4">
                        <div className="flex flex-wrap gap-1">
                          {(alert.involvedBanks || []).map((b, idx) => (
                            <span
                              key={idx}
                              className="px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200 font-mono text-[10px] text-slate-700 font-bold uppercase"
                            >
                              {b.replace('bank_', '')}
                            </span>
                          ))}
                        </div>
                      </td>

                      <td className="py-3 px-4 text-slate-500 font-mono text-[11px]">
                        {alert.dispatchTime ? new Date(alert.dispatchTime).toLocaleTimeString() : 'Recent'}
                      </td>

                      <td className="py-3 px-4">
                        <span
                          className={`px-2 py-0.5 rounded text-[11px] font-semibold capitalize ${
                            alert.status === 'resolved'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : alert.status === 'acknowledged'
                              ? 'bg-blue-50 text-blue-700 border border-blue-200'
                              : 'bg-amber-50 text-amber-700 border border-amber-200'
                          }`}
                        >
                          {alert.status}
                        </span>
                      </td>


                      <td className="py-3 px-4 text-right space-x-1.5" onClick={(e) => e.stopPropagation()}>
                        {alert.status !== 'resolved' && (
                          <button
                            onClick={() => handleResolve?.(alert.id, 'Resolved by investigator')}
                            className="p-1.5 bg-slate-100 hover:bg-emerald-50 hover:text-emerald-700 text-slate-600 rounded-lg border border-slate-200 transition-colors"
                            title="Mark Resolved"
                          >
                            <CheckCircle className="w-3.5 h-3.5" />
                          </button>
                        )}
                        <button
                          onClick={() => handleExplain?.(alert)}
                          className="px-2.5 py-1 bg-blue-50 hover:bg-blue-100 text-blue-700 font-semibold rounded-lg border border-blue-200 transition-colors inline-flex items-center gap-1"
                        >
                          <Sparkles className="w-3 h-3" />
                          <span>Explain</span>
                        </button>
                      </td>
                    </tr>

                    {/* Expanded Detail Drawer */}
                    {isExpanded && (
                      <tr className="bg-slate-50/90 border-b border-slate-200">
                        <td colSpan={7} className="p-4">
                          <div className="bg-white border border-slate-200 rounded-xl p-4 space-y-3">
                            <div className="flex items-center justify-between text-xs font-bold text-slate-700">
                              <span>Participating Cryptographic Nodes</span>
                              <span className="text-slate-400 font-mono">{(alert.hashedNodes || []).length} Accounts Flagged</span>
                            </div>
                            <div className="grid grid-cols-2 gap-2">
                              {(alert.hashedNodes || []).map((h, i) => (
                                <div key={i} className="p-2 bg-slate-50 border border-slate-200/80 rounded-lg font-mono text-[11px] text-slate-700 truncate">
                                  {h}
                                </div>
                              ))}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default AlertTable;
