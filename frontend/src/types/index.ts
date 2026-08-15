/**
 * TRACE: Cross-Bank Mule Account Detection Network
 * Core TypeScript Type Definitions
 */

export type SeverityLevel = 'low' | 'medium' | 'high' | 'critical';
export type AlertStatusType = 'pending' | 'acknowledged' | 'resolved' | 'dismissed';
export type InvestigationStatusType = 'active' | 'completed' | 'closed';
export type StoppingReasonType =
  | 'pattern_decay'
  | 'time_gap'
  | 'historical_relationship'
  | 'hard_cap'
  | 'human_review'
  | 'target_reached';

export interface Node {
  id: string; // HMAC:... standing hash
  bank: string;
  riskScore?: number;
  isMule?: boolean;
  label?: string;
  inDegree?: number;
  outDegree?: number;
  totalVolume?: number;
}

export interface Edge {
  id: string;
  source: string; // sender_hash
  target: string; // receiver_hash
  amount: number;
  timestamp: string;
  bankId: string;
  isInterbank: boolean;
  localRiskScore?: number;
}

export interface GraphStats {
  nodeCount: number;
  edgeCount: number;
  avgDegree: number;
  density: number;
  componentCount: number;
  edgesByBank: Record<string, number>;
  isConnected?: boolean;
}

export interface Component {
  id: string;
  nodes: string[];
  banks: string[];
  totalVolume: number;
  avgPassThrough: number;
  maxChainLength: number;
  riskScore: number;
  severity: SeverityLevel;
  detectionTime: string;
  status: 'active' | 'investigating' | 'resolved';
  featureVector?: Record<string, number>;
  shapExplanation?: Record<string, any>;
}

export interface FeatureImportance {
  feature: string;
  value: number;
  shap: number;
  direction: 'positive' | 'negative';
}

export interface ExplanationData {
  probability: number;
  isMule: boolean;
  severity: SeverityLevel;
  featureImportance: FeatureImportance[];
  summary: string;
  shapValues: Record<string, number>;
  topDrivers?: string[];
}

export interface Alert {
  id: string;
  componentId: string;
  severity: SeverityLevel;
  involvedBanks: string[];
  riskScore: number;
  explanation: ExplanationData | Record<string, any>;
  status: AlertStatusType;
  dispatchTime: string;
  resolvedAt?: string;
  notes?: string;
  hashedNodes?: string[];
}

export interface TraversalStep {
  step_number?: number;
  stepNumber?: number;
  action: string;
  description: string;
  decision: 'ACCEPT' | 'REJECT' | 'START' | 'DONE';
  node?: string;
  from?: string;
  to?: string;
  bank_id?: string;
  bankId?: string;
  amount?: number;
  reason?: string;
  timestamp?: string;
}


export interface Investigation {
  id: string;
  componentId: string;
  startNode: string;
  status: InvestigationStatusType;
  depthReached: number;
  banksQueried: string[];
  stoppingReason?: StoppingReasonType;
  traversalPath: string[];
  playbackSteps: TraversalStep[];
  startedAt: string;
  completedAt?: string;
  closedBy?: string;
}

export interface Bank {
  id: string;
  name: string;
  ifscPrefix: string;
  isActive: boolean;
  totalAccounts?: number;
  logoUrl?: string;
  primaryColor?: string;
}

export interface ResolvedAccountDetails {
  hash: string;
  accountNumber: string;
  customerName: string;
  bankId: string;
  bankName: string;
  kycStatus: string;
  declaredIncome: number;
  accountAgeDays: number;
  isDormant: boolean;
  resolvedAt?: string;
}

export interface STRReport {
  id: string;
  alertId: string;
  bankId: string;
  strId: string;
  accountNumber: string;
  customerName: string;
  suspicionReason: string;
  amountInvolved: number;
  status: 'draft' | 'submitted' | 'accepted';
  generatedAt: string;
  filingBank: string;
  regulatoryAgency: string;
  recommendedActions: string[];
  supportingEvidence: string[];
}

export interface SystemHealth {
  backendConnected: boolean;
  lastIngestionTime: string | null;
  activeInvestigationsCount: number;
  pendingAlertsCount: number;
  totalNodesMonitored: number;
}
