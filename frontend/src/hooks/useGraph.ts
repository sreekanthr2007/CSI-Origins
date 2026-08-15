/**
 * TRACE: Custom React Hooks for Graph, Alerts, and Investigations State
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Node,
  Edge,
  GraphStats,
  Alert,
  Investigation,
  TraversalStep,
  Bank,
  Component,
} from '../types';
import * as api from '../services/api';

export function useGraph() {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [components, setComponents] = useState<Component[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<Edge | null>(null);
  const [bankFilter, setBankFilter] = useState<string>('all');
  const [riskFilter, setRiskFilter] = useState<number>(0.0);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsRes, edgesRes, nodesRes, compsRes] = await Promise.all([
        api.fetchGraphStats().catch(() => null),
        api.fetchGraphEdges(300, 0).catch(() => ({ total: 0, edges: [] })),
        api.fetchGraphNodes(500, 0).catch(() => ({ total: 0, nodes: [] })),
        api.fetchComponents().catch(() => ({ total: 0, components: [] })),
      ]);

      if (statsRes) setStats(statsRes);
      setEdges(edgesRes.edges);
      setNodes(nodesRes.nodes);
      setComponents(compsRes.components);
    } catch (err: any) {
      setError(err.message || 'Failed to load graph data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const selectNode = (nodeId: string | null) => {
    if (!nodeId) {
      setSelectedNode(null);
      return;
    }
    const found = nodes.find((n) => n.id === nodeId) || {
      id: nodeId,
      bank: 'UNKNOWN',
      riskScore: 0.85,
    };
    setSelectedNode(found);
  };

  const selectEdge = (edgeId: string | null) => {
    if (!edgeId) {
      setSelectedEdge(null);
      return;
    }
    const found = edges.find((e) => e.id === edgeId) || null;
    setSelectedEdge(found);
  };

  // Filtered views
  const filteredNodes = nodes.filter((n) => {
    if (bankFilter !== 'all' && !n.bank?.toLowerCase().includes(bankFilter.toLowerCase())) {
      return false;
    }
    if ((n.riskScore ?? 0) < riskFilter) {
      return false;
    }
    return true;
  });

  const filteredNodeIds = new Set(filteredNodes.map((n) => n.id));
  const filteredEdges = edges.filter(
    (e) => filteredNodeIds.has(e.source) && filteredNodeIds.has(e.target)
  );

  return {
    nodes: filteredNodes,
    allNodes: nodes,
    edges: filteredEdges,
    allEdges: edges,
    stats,
    components,
    loading,
    error,
    refetch: fetchData,
    refreshGraph: fetchData,
    selectNode,
    selectedNode,
    selectEdge,
    selectedEdge,
    bankFilter,
    setBankFilter,
    riskFilter,
    setRiskFilter,
  };
}

export function useAlerts(bankId?: string) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let data: Alert[] = [];
      if (bankId) {
        data = await api.fetchBankAlerts(bankId);
      } else {
        data = await api.fetchPendingAlerts();
      }
      setAlerts(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load alerts');
    } finally {
      setLoading(false);
    }
  }, [bankId]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  const dispatchAlert = async (componentId: string, riskScore = 0.85) => {
    const res = await api.dispatchAlert(componentId, riskScore);
    await fetchAlerts();
    return res;
  };

  const resolveAlert = async (alertId: string, status = 'resolved', notes?: string) => {
    const res = await api.resolveAlert(alertId, status, notes);
    await fetchAlerts();
    return res;
  };


  return {
    alerts,
    loading,
    error,
    refetch: fetchAlerts,
    refreshAlerts: fetchAlerts,
    dispatchAlert,
    resolveAlert,
  };
}

export function useInvestigation(investigationId?: string) {
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [playback, setPlayback] = useState<TraversalStep[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDetails = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const [statusRes, playbackRes] = await Promise.all([
        api.getInvestigationStatus(id),
        api.getInvestigationPlayback(id).catch(() => ({ steps: [] })),
      ]);

      setInvestigation({
        id,
        componentId: (statusRes as any).component_id || 'comp_active',
        startNode: (statusRes as any).start_node || 'HMAC:Target',
        status: statusRes.status as any,
        depthReached: statusRes.depth_reached,
        banksQueried: statusRes.banks_queried,
        traversalPath: [],
        playbackSteps: playbackRes.steps || [],
        startedAt: new Date().toISOString(),
      });
      setPlayback(playbackRes.steps || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load investigation');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (investigationId) {
      fetchDetails(investigationId);
    }
  }, [investigationId, fetchDetails]);

  const startInvestigation = async (nodeHash: string, componentId?: string) => {
    setLoading(true);
    try {
      const res = await api.startInvestigation(nodeHash, componentId);
      await fetchDetails(res.investigation_id);
      return res;
    } catch (err: any) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const closeInvestigation = async (id?: string) => {
    const targetId = id || investigationId;
    if (!targetId) return;
    try {
      await api.closeInvestigation(targetId);
      await fetchDetails(targetId);
    } catch (err: any) {
      setError(err.message);
      throw err;
    }
  };

  return {
    investigation,
    playback,
    loading,
    error,
    startInvestigation,
    closeInvestigation,
    refetch: () => (investigationId ? fetchDetails(investigationId) : null),
  };
}

export function useBanks() {
  const [banks, setBanks] = useState<Bank[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .fetchBanks()
      .then(setBanks)
      .catch(() => [])
      .finally(() => setLoading(false));
  }, []);

  return { banks, loading };
}
