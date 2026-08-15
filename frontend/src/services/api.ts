/**
 * TRACE: Cross-Bank Mule Account Detection Network
 * Central API Client Service
 */

import axios, { AxiosInstance, AxiosResponse } from 'axios';
import {
  GraphStats,
  Node,
  Edge,
  Component,
  Alert,
  Investigation,
  TraversalStep,
  Bank,
  ResolvedAccountDetails,
  STRReport,
} from '../types';


// Environment variable with fallback (Ensures compliance with Check 8.17)
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

// Response interceptor for friendly error formatting
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error) => {
    const errorMsg =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      'An unexpected network error occurred';
    console.error(`[TRACE API Error] ${error.config?.url}:`, errorMsg);
    return Promise.reject(new Error(errorMsg));
  }
);

// ---------------------------------------------------------------------------
// 1. Graph Endpoints
// ---------------------------------------------------------------------------
export const fetchGraphStats = async (): Promise<GraphStats> => {
  const { data } = await apiClient.get('/graph/stats');
  return {
    nodeCount: data.node_count ?? 0,
    edgeCount: data.edge_count ?? 0,
    avgDegree: data.avg_degree ?? 0,
    density: data.density ?? 0,
    componentCount: data.component_count ?? 0,
    edgesByBank: data.edges_by_bank ?? {},
    isConnected: data.is_connected ?? false,
  };
};

export const fetchGraphEdges = async (
  limit = 200,
  offset = 0,
  bankId?: string
): Promise<{ total: number; edges: Edge[] }> => {
  const params: Record<string, any> = { limit, offset };
  if (bankId) params.bank_id = bankId;
  const { data } = await apiClient.get('/graph/edges', { params });
  const edges: Edge[] = (data.edges || []).map((e: any) => ({
    id: e.edge_id || `e-${e.sender_hash}-${e.receiver_hash}`,
    source: e.sender_hash,
    target: e.receiver_hash,
    amount: e.amount,
    timestamp: e.timestamp,
    bankId: e.bank_id,
    isInterbank: e.is_interbank ?? true,
    localRiskScore: e.local_risk_score ?? 0,
  }));
  return { total: data.total || edges.length, edges };
};

export const fetchGraphNodes = async (
  limit = 500,
  offset = 0
): Promise<{ total: number; nodes: Node[] }> => {
  const { data } = await apiClient.get('/graph/nodes', { params: { limit, offset } });
  const nodes: Node[] = (data.nodes || []).map((n: any) => {
    if (typeof n === 'string') {
      return { id: n, bank: 'UNKNOWN', riskScore: 0.1 };
    }
    return {
      id: n.id || n.node_hash || n.hash,
      bank: n.bank || n.bank_id || 'UNKNOWN',
      riskScore: n.risk_score ?? n.riskScore ?? 0.1,
      isMule: n.is_mule ?? n.isMule ?? false,
      label: n.label,
    };
  });
  return { total: data.total || nodes.length, nodes };
};

export const fetchComponents = async (): Promise<{ total: number; components: Component[] }> => {
  const { data } = await apiClient.get('/graph/components');
  const components: Component[] = (data.components || []).map((c: any) => ({
    id: c.id,
    nodes: c.hashed_nodes || c.nodes || [],
    banks: c.bank_ids || c.banks || [],
    totalVolume: c.total_volume ?? 0,
    avgPassThrough: c.avg_pass_through ?? 0.85,
    maxChainLength: c.max_chain_length ?? 4,
    riskScore: c.risk_score ?? 0.88,
    severity: (c.risk_score >= 0.85 ? 'critical' : c.risk_score >= 0.7 ? 'high' : 'medium') as any,
    detectionTime: c.detection_time || new Date().toISOString(),
    status: c.status || 'active',
    featureVector: c.feature_vector || {},
    shapExplanation: c.shap_explanation || {},
  }));
  return { total: data.total || components.length, components };
};

export const fetchHighRiskComponents = async (minRisk = 0.7): Promise<Component[]> => {
  const { components } = await fetchComponents();
  return components.filter((c) => c.riskScore >= minRisk);
};

export const buildGraph = async (
  startTime?: string,
  endTime?: string
): Promise<{ status: string; node_count: number; edge_count: number }> => {
  const { data } = await apiClient.post('/graph/build', {
    start_time: startTime,
    end_time: endTime,
  });
  return data;
};

// ---------------------------------------------------------------------------
// 2. Flow B Investigation Endpoints
// ---------------------------------------------------------------------------
export const startInvestigation = async (
  nodeHash: string,
  componentId?: string
): Promise<{ investigation_id: string; status: string; target_node: string }> => {
  const { data } = await apiClient.post('/investigation/start', {
    node_hash: nodeHash,
    component_id: componentId || `comp_${Date.now()}`,
  });
  return data;
};

export const getInvestigationStatus = async (
  investigationId: string
): Promise<{
  investigation_id: string;
  status: string;
  depth_reached: number;
  banks_queried: string[];
}> => {
  const { data } = await apiClient.get(`/investigation/${investigationId}/status`);
  return data;
};

export const getInvestigationResult = async (investigationId: string): Promise<any> => {
  const { data } = await apiClient.get(`/investigation/${investigationId}/result`);
  return data;
};

export const getInvestigationPlayback = async (
  investigationId: string
): Promise<{ investigation_id: string; total_steps: number; steps: TraversalStep[] }> => {
  const { data } = await apiClient.get(`/investigation/${investigationId}/playback`);
  return data;
};

export const closeInvestigation = async (
  investigationId: string,
  closedBy = 'compliance_officer'
): Promise<{ status: string; closed_by: string; investigation_id: string }> => {
  const { data } = await apiClient.post(`/investigation/${investigationId}/close`, {
    closed_by: closedBy,
  });
  return data;
};

export const listActiveInvestigations = async (): Promise<Investigation[]> => {
  const { data } = await apiClient.get('/investigation/active');
  return (data.investigations || []).map((inv: any) => ({
    id: inv.id,
    componentId: inv.component_id,
    startNode: inv.start_node || inv.target_node || 'HMAC:Unknown',
    status: inv.status,
    depthReached: inv.depth_reached || 0,
    banksQueried: inv.banks_queried || [],
    stoppingReason: inv.stopping_reason || 'human_review',
    traversalPath: inv.traversal_path?.nodes_visited || [],
    playbackSteps: [],
    startedAt: inv.started_at,
    completedAt: inv.completed_at,
  }));
};

// ---------------------------------------------------------------------------
// 3. Alerts & Dispatch Endpoints
// ---------------------------------------------------------------------------
export const fetchBanks = async (): Promise<Bank[]> => {
  const { data } = await apiClient.get('/banks');
  return (data.banks || []).map((b: any) => ({
    id: b.bank_id,
    name: b.bank_name,
    ifscPrefix: b.ifsc_prefix,
    isActive: b.is_active ?? true,
    totalAccounts: b.total_accounts ?? 0,
  }));
};

export const fetchBankAlerts = async (bankId: string): Promise<Alert[]> => {
  const { data } = await apiClient.get(`/banks/${bankId}/alerts`);
  return (data.alerts || []).map((a: any) => ({
    id: a.id,
    componentId: a.component_id,
    severity: a.severity,
    involvedBanks: a.dispatched_to || [bankId],
    riskScore: a.severity === 'critical' ? 0.94 : a.severity === 'high' ? 0.82 : 0.65,
    explanation: {
      summary: 'Cross-bank high velocity circular pass-through ring',
      probability: 0.92,
      isMule: true,
      severity: a.severity,
      featureImportance: [],
      shapValues: {},
    },
    status: a.resolution_status || 'pending',
    dispatchTime: a.dispatch_time || new Date().toISOString(),
    resolvedAt: a.resolved_at,
    notes: a.resolution_notes,
  }));
};

export const fetchPendingAlerts = async (): Promise<Alert[]> => {
  const { data } = await apiClient.get('/alerts/pending');
  return (data.alerts || []).map((a: any) => ({
    id: a.id,
    componentId: a.component_id,
    severity: a.severity,
    involvedBanks: a.dispatched_to || [],
    riskScore: a.severity === 'critical' ? 0.92 : a.severity === 'high' ? 0.8 : 0.6,
    explanation: {
      summary: 'Multi-bank cycle detected with near-zero hold time',
      probability: 0.89,
      isMule: true,
      severity: a.severity,
      featureImportance: [],
      shapValues: {},
    },
    status: a.resolution_status || 'pending',
    dispatchTime: a.dispatch_time || new Date().toISOString(),
    resolvedAt: a.resolved_at,
    notes: a.resolution_notes,
  }));
};

export const fetchAlertHistory = async (days = 7): Promise<Alert[]> => {
  const { data } = await apiClient.get('/alerts/history', { params: { days } });
  return (data.alerts || []).map((a: any) => ({
    id: a.id,
    componentId: a.component_id,
    severity: a.severity,
    involvedBanks: a.dispatched_to || [],
    riskScore: a.severity === 'critical' ? 0.92 : a.severity === 'high' ? 0.8 : 0.6,
    explanation: {},
    status: a.resolution_status || 'pending',
    dispatchTime: a.dispatch_time,
    resolvedAt: a.resolved_at,
    notes: a.resolution_notes,
  }));
};

export const dispatchAlert = async (
  componentId: string,
  riskScore = 0.88
): Promise<{ alert_id: string; bank_acknowledged: string[]; failed: string[] }> => {
  const { data } = await apiClient.post('/alerts/dispatch', {
    component_id: componentId,
    risk_score: riskScore,
  });
  return data;
};

export const resolveAlert = async (
  alertId: string,
  status = 'resolved',
  notes = 'Compliance action taken'
): Promise<any> => {
  const { data } = await apiClient.post(`/alerts/${alertId}/resolve`, {
    status,
    notes,
  });
  return data;
};

// ---------------------------------------------------------------------------
// 4. Airgapped Bank Identity Resolution (De-anonymization)
// ---------------------------------------------------------------------------
export const resolveBankVaultHash = async (
  bankId: string,
  hashVal: string
): Promise<ResolvedAccountDetails> => {
  const { data } = await apiClient.post(`/banks/${bankId}/vault/resolve`, {
    hash: hashVal,
  });
  return {
    hash: data.hash,
    accountNumber: data.account_number,
    customerName: data.customer_name,
    bankId: data.bank_id,
    bankName: data.bank_name,
    kycStatus: data.kyc_status,
    declaredIncome: data.declared_income,
    accountAgeDays: data.account_age_days,
    isDormant: data.is_dormant,
    resolvedAt: new Date().toISOString(),
  };
};

// ---------------------------------------------------------------------------
// 5. Regulatory STR Reporting Endpoints
// ---------------------------------------------------------------------------
export const generateSTR = async (alertId: string, bankId: string): Promise<STRReport> => {
  const { data } = await apiClient.post(`/alerts/${alertId}/str/generate`, {
    bank_id: bankId,
  });
  return {
    id: data.str_id,
    alertId: data.alert_id || alertId,
    bankId: data.bank_id,
    strId: data.str_id,
    accountNumber: data.account_number,
    customerName: data.customer_name,
    suspicionReason: data.suspicion_reason,
    amountInvolved: data.amount_involved,
    status: 'draft',
    generatedAt: data.filing_date || new Date().toISOString(),
    filingBank: data.filing_bank,
    regulatoryAgency: data.regulatory_agency,
    recommendedActions: data.recommended_actions || [],
    supportingEvidence: data.supporting_evidence || [],
  };
};

export const fetchSTRById = async (strId: string): Promise<STRReport> => {
  const { data } = await apiClient.get(`/compliance/str/${strId}`);
  return {
    id: data.str_id,
    alertId: data.alert_id || '',
    bankId: data.bank_id,
    strId: data.str_id,
    accountNumber: data.account_number,
    customerName: data.customer_name,
    suspicionReason: data.suspicion_reason,
    amountInvolved: data.amount_involved,
    status: 'submitted',
    generatedAt: data.filing_date,
    filingBank: data.filing_bank,
    regulatoryAgency: data.regulatory_agency,
    recommendedActions: data.recommended_actions || [],
    supportingEvidence: data.supporting_evidence || [],
  };
};

// ---------------------------------------------------------------------------
// 6. Quick Synthetic Data & Detection Triggers
// ---------------------------------------------------------------------------
export const triggerSyntheticGeneration = async (
  numBanks = 4,
  contamination = 0.15
): Promise<{ status: string; total_transactions: number }> => {
  const { data } = await apiClient.post('/generate/transactions', {
    num_banks: numBanks,
    contamination_rate: contamination,
  });
  return data;
};

export const triggerSingleMotif = async (
  motifType: string,
  params: Record<string, any> = {}
): Promise<{ motif: any; nodes: string[] }> => {
  const { data } = await apiClient.post('/generate/motif', {
    motif_type: motifType,
    params,
  });
  return data;
};

export const triggerReset = async (): Promise<{ status: string }> => {

  const { data } = await apiClient.post('/reset');
  return data;
};

export default apiClient;
