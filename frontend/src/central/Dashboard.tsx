/**
 * TRACE: Central Intelligence Dashboard View (Light Theme, Zero-PII)
 */

import React, { useState } from 'react';
import { useGraph, useAlerts, useInvestigation } from '../hooks/useGraph';
import MuleNetworkGraph from '../components/MuleNetworkGraph';
import { AlertTable } from '../components/AlertTable';
import { InspectionModal } from '../components/InspectionModal';
import { InvestigationWorkbench } from '../components/InvestigationWorkbench';
import { Node } from '../types';
import * as api from '../services/api';
import {
  Activity,
  ShieldAlert,
  Layers,
  Zap,
  Sliders,
  Filter,
} from 'lucide-react';



export const CentralDashboard: React.FC = () => {
  const {
    allNodes,
    allEdges,
    stats,
    components,
    bankFilter,
    setBankFilter,
    riskFilter,
    setRiskFilter,
    refreshGraph,
  } = useGraph();

  const {
    alerts,
    loading: alertsLoading,
    dispatchAlert,
    resolveAlert,
    refreshAlerts,
  } = useAlerts();

  const [activeTab, setActiveTab] = useState<'graph' | 'alerts' | 'investigation'>('graph');
  const [inspectingNode, setInspectingNode] = useState<Node | null>(null);
  const [activeInvestigationId, setActiveInvestigationId] = useState<string | null>(null);

  const {
    investigation,
    playback,
    startInvestigation,
    closeInvestigation,
  } = useInvestigation(activeInvestigationId || undefined);

  // Trigger Flow B investigation from node or alert
  const handleStartInvestigation = async (nodeHashOrComponentId: string) => {
    try {
      const res = await startInvestigation(nodeHashOrComponentId);
      if (res?.investigation_id) {
        setActiveInvestigationId(res.investigation_id);
        setActiveTab('investigation');
      }
    } catch (err) {
      console.error('Failed to launch investigation:', err);
    }
  };

  // Quick Scenario Loader
  const handleLoadScenario = async (scenarioNum: number) => {
    try {
      if (scenarioNum === 1) {
        await api.triggerSingleMotif('chain', { num_hops: 4, amount: 500000 });
      } else if (scenarioNum === 2) {
        await api.triggerSingleMotif('collector_star', { num_senders: 8, amount_per_sender: 48000 });
      } else if (scenarioNum === 3) {
        await api.triggerSingleMotif('distributor_star', { num_receivers: 10, amount_per_receiver: 49500 });
      } else {
        await api.triggerSyntheticGeneration(6, 0.05);
      }
      await refreshGraph();
      if (refreshAlerts) await refreshAlerts();
    } catch (err) {
      console.error('Scenario load error:', err);
    }
  };


  const highRiskComponents = components.filter((c) => c.riskScore >= 0.7);
  const connectedEdges = inspectingNode
    ? allEdges.filter((e) => e.source === inspectingNode.id || e.target === inspectingNode.id)
    : [];

  return (
    <div className="flex-1 flex flex-col bg-slate-50 text-slate-800 overflow-hidden font-sans">
      {/* Top Stat Cards Ribbon */}
      <div className="p-4 grid grid-cols-2 sm:grid-cols-4 gap-3 bg-white border-b border-slate-200/90 shadow-xs">
        <div className="bg-slate-50 border border-slate-200/80 p-3.5 rounded-xl flex items-center space-x-3.5 shadow-xs">
          <div className="p-2.5 rounded-xl bg-blue-100 text-blue-600 border border-blue-200/80">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[11px] uppercase font-bold text-slate-500 block tracking-wider">
              Monitored Nodes
            </span>
            <span className="text-xl font-extrabold text-slate-900 font-mono">
              {stats?.nodeCount ?? allNodes.length}
            </span>
          </div>
        </div>

        <div className="bg-slate-50 border border-slate-200/80 p-3.5 rounded-xl flex items-center space-x-3.5 shadow-xs">
          <div className="p-2.5 rounded-xl bg-indigo-100 text-indigo-600 border border-indigo-200/80">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[11px] uppercase font-bold text-slate-500 block tracking-wider">
              Active Transactions
            </span>
            <span className="text-xl font-extrabold text-slate-900 font-mono">
              {stats?.edgeCount ?? allEdges.length}
            </span>
          </div>
        </div>

        <div className="bg-slate-50 border border-slate-200/80 p-3.5 rounded-xl flex items-center space-x-3.5 shadow-xs">
          <div className="p-2.5 rounded-xl bg-red-100 text-red-600 border border-red-200/80">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[11px] uppercase font-bold text-slate-500 block tracking-wider">
              Flagged Mule Rings
            </span>
            <span className="text-xl font-extrabold text-red-600 font-mono">
              {highRiskComponents.length > 0 ? highRiskComponents.length : (allNodes.filter(n => (n.riskScore ?? 0) >= 0.7).length > 0 ? Math.ceil(allNodes.filter(n => (n.riskScore ?? 0) >= 0.7).length / 3) : 0)}
            </span>
          </div>
        </div>

        <div className="bg-slate-50 border border-slate-200/80 p-3.5 rounded-xl flex items-center space-x-3.5 shadow-xs">
          <div className="p-2.5 rounded-xl bg-amber-100 text-amber-700 border border-amber-200/80">
            <Zap className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[11px] uppercase font-bold text-slate-500 block tracking-wider">
              Pending Alerts
            </span>
            <span className="text-xl font-extrabold text-amber-700 font-mono">
              {alerts.length}
            </span>
          </div>
        </div>
      </div>

      {/* Navigation Tabs & Global Filters */}
      <div className="px-5 py-2.5 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3 bg-white">
        {/* Navigation Tabs */}
        <div className="flex items-center space-x-1.5 bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs font-semibold">
          <button
            onClick={() => setActiveTab('graph')}
            className={`px-3.5 py-1.5 rounded-lg transition-all ${
              activeTab === 'graph'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
            }`}
          >
            Multi-Bank Topology Graph
          </button>
          <button
            onClick={() => setActiveTab('alerts')}
            className={`px-3.5 py-1.5 rounded-lg transition-all ${
              activeTab === 'alerts'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
            }`}
          >
            Alert Queue ({alerts.length})
          </button>
          <button
            onClick={() => setActiveTab('investigation')}
            className={`px-3.5 py-1.5 rounded-lg transition-all ${
              activeTab === 'investigation'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
            }`}
          >
            Flow B Workbench
          </button>
        </div>

        {/* Graph Filters & Quick Scenarios */}
        {activeTab === 'graph' && (
          <div className="flex items-center space-x-3 text-xs">
            {/* Quick Scenario Buttons */}
            <div className="hidden lg:flex items-center space-x-1.5 border-r border-slate-200 pr-3">
              <span className="text-[11px] text-slate-400 font-semibold uppercase">Quick Scenarios:</span>
              <button
                onClick={() => handleLoadScenario(1)}
                className="px-2 py-1 bg-slate-100 hover:bg-blue-50 hover:text-blue-700 rounded-md border border-slate-200 font-medium transition-colors"
                title="Scenario 1: Fast 4-Bank Chain"
              >
                1: 4-Bank Chain
              </button>
              <button
                onClick={() => handleLoadScenario(2)}
                className="px-2 py-1 bg-slate-100 hover:bg-amber-50 hover:text-amber-800 rounded-md border border-slate-200 font-medium transition-colors"
                title="Scenario 2: Collector Star"
              >
                2: Collector
              </button>
              <button
                onClick={() => handleLoadScenario(3)}
                className="px-2 py-1 bg-slate-100 hover:bg-purple-50 hover:text-purple-700 rounded-md border border-slate-200 font-medium transition-colors"
                title="Scenario 3: Smurfing Ring"
              >
                3: Smurfing
              </button>
            </div>

            {/* Bank Filter */}
            <div className="flex items-center space-x-1.5 text-slate-600">
              <Filter className="w-3.5 h-3.5 text-slate-400" />
              <span>Bank:</span>
              <select
                value={bankFilter}
                onChange={(e) => setBankFilter(e.target.value)}
                className="bg-white border border-slate-200 text-slate-800 rounded-lg px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500 font-medium"
              >
                <option value="all">All Banks (6)</option>
                <option value="sbi">SBI</option>
                <option value="hdfc">HDFC</option>
                <option value="icici">ICICI</option>
                <option value="axis">Axis</option>
                <option value="pnb">PNB</option>
                <option value="bob">Bank of Baroda</option>
              </select>
            </div>

            {/* Min Risk Slider */}
            <div className="flex items-center space-x-2 text-slate-600">
              <Sliders className="w-3.5 h-3.5 text-slate-400" />
              <span>Min Risk ({(riskFilter * 100).toFixed(0)}%):</span>
              <input
                type="range"
                min={0.0}
                max={0.90}
                step={0.05}
                value={riskFilter}
                onChange={(e) => setRiskFilter(parseFloat(e.target.value))}
                className="w-24 accent-blue-600 cursor-pointer"
              />
            </div>
          </div>
        )}
      </div>

      {/* Main Tab Content Canvas */}
      <div className="flex-1 flex overflow-hidden">
        {activeTab === 'graph' && (
          <MuleNetworkGraph
            nodes={allNodes}
            edges={allEdges}
            onNodeClick={(node) => setInspectingNode(node)}
            stats={stats}
            alerts={alerts}
          />
        )}

        {activeTab === 'alerts' && (
          <div className="flex-1 overflow-y-auto p-4">
            <AlertTable
              alerts={alerts}
              loading={alertsLoading}
              onSelectAlert={(a) => {
                const targetNode = allNodes.find((n) => a.hashedNodes?.includes(n.id));
                if (targetNode) setInspectingNode(targetNode);
              }}
              onExplainAlert={(a) => {
                const targetNode = allNodes.find((n) => a.hashedNodes?.includes(n.id));
                if (targetNode) setInspectingNode(targetNode);
              }}
              onDispatchAlert={dispatchAlert}
              onResolveAlert={resolveAlert}
            />
          </div>
        )}

        {activeTab === 'investigation' && (
          <div className="flex-1 flex overflow-hidden">
            <InvestigationWorkbench
              investigation={investigation}
              playback={playback}
              onStartInvestigation={handleStartInvestigation}
              onCloseInvestigation={closeInvestigation}
            />
          </div>
        )}
      </div>

      {/* Modal Profile Overlay on Node Click */}
      <InspectionModal
        isOpen={Boolean(inspectingNode)}
        onClose={() => setInspectingNode(null)}
        selectedNode={inspectingNode}
        selectedComponent={components[0] || null}
        connectedEdges={connectedEdges}
        onLaunchInvestigation={handleStartInvestigation}
      />
    </div>
  );
};
