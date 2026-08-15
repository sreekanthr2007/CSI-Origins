/**
 * Core type definitions for Cross-Bank Mule Account Detection Network.
 */

export interface Bank {
  bank_id: string;
  bank_name: string;
  ifsc_prefix: string;
}

export interface NodeData {
  id: string;
  label?: string;
  bankId: string;
  isMule?: boolean;
  role?: 'victim' | 'hop' | 'collector' | 'distributor' | 'terminal_cashout' | 'normal';
  riskScore?: number;
  passThroughRatio?: number;
}

export interface EdgeData {
  id: string;
  source: string;
  target: string;
  amount: number;
  timestamp: string;
  isCrossBank: boolean;
  localRiskScore: number;
}

export interface MuleComponentAlert {
  alert_id: string;
  component_id: string;
  risk_score: number;
  severity: 'HIGH' | 'CRITICAL' | 'MEDIUM';
  bank_ids: string[];
  nodes_count: number;
  edges_count: number;
  pattern_type: 'RAPID_CHAIN' | 'COLLECTOR_STAR' | 'DISTRIBUTOR_SMURFING' | 'CYCLE';
  top_drivers: Array<{
    feature: string;
    impact: number;
    description: string;
  }>;
  narrative: string;
  flagged_at: string;
}

export interface DeAnonymizedRecord {
  account_number: string;
  ifsc: string;
  customer_name: string;
  kyc_status: string;
  account_age_days: number;
  declared_monthly_income: number;
  risk_factors: string[];
}
