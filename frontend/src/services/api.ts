import axios from 'axios';
import { Bank } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const fetchHealth = async () => {
  const res = await apiClient.get('/health');
  return res.data;
};

export const fetchBanks = async (): Promise<Bank[]> => {
  const res = await apiClient.get<Bank[]>('/api/banks');
  return res.data;
};

export const fetchSystemStatus = async () => {
  const res = await apiClient.get('/api/status');
  return res.data;
};
