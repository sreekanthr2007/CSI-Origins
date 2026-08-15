/**
 * TRACE: Cross-Bank Mule Account Detection Network
 * UI Formatters, Colors, and Style Utilities
 */

import { SeverityLevel } from '../types';

export const formatHash = (hash: string | undefined | null, length = 16): string => {
  if (!hash) return 'HMAC:None';
  if (hash.length <= length) return hash;
  const prefix = hash.startsWith('HMAC:') ? 'HMAC:' : hash.startsWith('INV:') ? 'INV:' : '';
  const clean = hash.replace(/^(HMAC:|INV:)/, '');
  return `${prefix}${clean.slice(0, 8)}...${clean.slice(-4)}`;
};

export const formatCurrency = (amount: number | undefined | null): string => {
  if (amount === undefined || amount === null || isNaN(amount)) return '₹0.00';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(amount);
};

export const formatTime = (timestamp: string | undefined | null): string => {
  if (!timestamp) return 'Just now';
  try {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDays = Math.floor(diffHour / 24);

    if (diffSec < 60) return `${Math.max(1, diffSec)}s ago`;
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHour < 24) return `${diffHour}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString('en-IN', { month: 'short', day: 'numeric' });
  } catch {
    return String(timestamp);
  }
};

export const formatFullTime = (timestamp: string | undefined | null): string => {
  if (!timestamp) return 'N/A';
  try {
    const date = new Date(timestamp);
    return date.toLocaleString('en-IN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return String(timestamp);
  }
};

export const getSeverityColor = (severity: SeverityLevel | string): string => {
  switch (severity?.toLowerCase()) {
    case 'critical':
      return '#ef4444'; // Red-500
    case 'high':
      return '#f97316'; // Orange-500
    case 'medium':
      return '#eab308'; // Yellow-500
    case 'low':
      return '#3b82f6'; // Blue-500
    default:
      return '#64748b'; // Slate-500
  }
};

export const getSeverityBg = (severity: SeverityLevel | string): string => {
  switch (severity?.toLowerCase()) {
    case 'critical':
      return 'bg-red-500/10 text-red-400 border-red-500/30';
    case 'high':
      return 'bg-orange-500/10 text-orange-400 border-orange-500/30';
    case 'medium':
      return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30';
    case 'low':
      return 'bg-blue-500/10 text-blue-400 border-blue-500/30';
    default:
      return 'bg-slate-500/10 text-slate-400 border-slate-500/30';
  }
};

export const getSeverityBadge = (severity: SeverityLevel | string): string => {
  return getSeverityBg(severity);
};


const BANK_COLORS: Record<string, string> = {
  bank_sbi: '#38bdf8', // Light Blue / SBI
  sbi: '#38bdf8',
  bank_hdfc: '#3b82f6', // Royal Blue / HDFC
  hdfc: '#3b82f6',
  bank_icici: '#f97316', // Orange / ICICI
  icici: '#f97316',
  bank_axis: '#ec4899', // Burgundy/Pink / Axis
  axis: '#ec4899',
  bank_pnb: '#eab308', // Gold / PNB
  pnb: '#eab308',
  bank_bob: '#f59e0b', // Amber / Bank of Baroda
  bob: '#f59e0b',
  bank_canara: '#10b981', // Emerald / Canara
  canara: '#10b981',
  bank_yes: '#06b6d4', // Cyan / Yes Bank
  yes: '#06b6d4',
  bank_kotak: '#ef4444', // Crimson / Kotak
  kotak: '#ef4444',
  bank_indusind: '#8b5cf6', // Purple / IndusInd
  indusind: '#8b5cf6',
};

export const getBankColor = (bankIdOrName: string | undefined | null): string => {
  if (!bankIdOrName) return '#94a3b8';
  const key = bankIdOrName.toLowerCase().replace(/[^a-z0-9_]/g, '');
  for (const [k, color] of Object.entries(BANK_COLORS)) {
    if (key.includes(k)) return color;
  }
  // Deterministic fallback color from string hash
  let hash = 0;
  for (let i = 0; i < key.length; i++) {
    hash = key.charCodeAt(i) + ((hash << 5) - hash);
  }
  const c = (hash & 0x00ffffff).toString(16).toUpperCase();
  return '#' + '00000'.substring(0, 6 - c.length) + c;
};

export const getNodeSize = (riskScore = 0.1): number => {
  if (riskScore >= 0.85) return 36;
  if (riskScore >= 0.7) return 30;
  if (riskScore >= 0.5) return 24;
  return 18;
};
