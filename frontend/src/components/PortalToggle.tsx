/**
 * TRACE: Dual-Portal Navigation & Bank Node Switcher (Light Theme)
 */

import React, { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Shield, Building2, ChevronDown, Check } from 'lucide-react';
import { Bank } from '../types';
import * as api from '../services/api';

export const PortalToggle: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [banks, setBanks] = useState<Bank[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const isBankPortal = location.pathname.startsWith('/bank');
  const currentBankId = isBankPortal
    ? location.pathname.split('/')[2] || 'bank_sbi'
    : 'bank_sbi';

  useEffect(() => {
    api.fetchBanks().then(setBanks).catch(() => []);
  }, []);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as HTMLElement)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelectCentral = () => {
    setIsOpen(false);
    navigate('/central');
  };

  const handleSelectBank = (bankId: string) => {
    setIsOpen(false);
    navigate(`/bank/${bankId}`);
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center space-x-2.5 px-3.5 py-1.5 rounded-xl border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-800 text-xs font-bold shadow-2xs transition-all cursor-pointer"
      >
        {isBankPortal ? (
          <>
            <Building2 className="w-4 h-4 text-blue-600" />
            <span>Bank Portal ({currentBankId.replace('bank_', '').toUpperCase()})</span>
          </>
        ) : (
          <>
            <Shield className="w-4 h-4 text-blue-600" />
            <span>Central Intelligence</span>
          </>
        )}
        <ChevronDown className="w-3.5 h-3.5 opacity-60 ml-1 text-slate-500" />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-64 bg-white border border-slate-200 rounded-2xl shadow-xl py-2 z-50 text-slate-800 text-xs animate-in fade-in">
          <div className="px-3.5 py-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
            Portal Modes
          </div>

          {/* Central Intelligence Option */}
          <button
            onClick={handleSelectCentral}
            className={`w-full flex items-center justify-between px-3.5 py-2 hover:bg-blue-50 transition-colors text-left cursor-pointer ${
              !isBankPortal ? 'bg-blue-50/80 text-blue-700 font-bold' : 'text-slate-700'
            }`}
          >
            <div className="flex items-center space-x-2.5">
              <Shield className="w-4 h-4 text-blue-600" />
              <span>Central Intelligence (Zero-PII)</span>
            </div>
            {!isBankPortal && <Check className="w-3.5 h-3.5 text-blue-600" />}
          </button>

          <div className="my-1.5 border-t border-slate-100" />

          <div className="px-3.5 py-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
            Bank Compliance Nodes
          </div>

          <div className="max-h-52 overflow-y-auto">
            {banks.map((b) => {
              const active = isBankPortal && currentBankId === b.id;
              return (
                <button
                  key={b.id}
                  onClick={() => handleSelectBank(b.id)}
                  className={`w-full flex items-center justify-between px-3.5 py-2 hover:bg-blue-50 transition-colors text-left cursor-pointer ${
                    active ? 'bg-blue-50/80 text-blue-700 font-bold' : 'text-slate-700'
                  }`}
                >
                  <div className="flex items-center space-x-2.5">
                    <Building2 className="w-3.5 h-3.5 text-slate-400" />
                    <span>{b.name}</span>
                  </div>
                  {active && <Check className="w-3.5 h-3.5 text-blue-600" />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default PortalToggle;
