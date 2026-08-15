/**
 * TRACE: Cross-Bank Mule Account Detection Network
 * Root Application Router & Layout
 */

import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Header } from './components/Header';
import { CentralDashboard } from './central/Dashboard';
import { BankCompliancePortal } from './components/BankCompliancePortal';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100 font-sans selection:bg-indigo-500 selection:text-white">
        <Header />
        <main className="flex-1 flex flex-col overflow-hidden">
          <Routes>
            <Route path="/" element={<Navigate to="/central" replace />} />
            <Route path="/central" element={<CentralDashboard />} />
            <Route path="/bank" element={<Navigate to="/bank/bank_sbi" replace />} />
            <Route path="/bank/:bankId" element={<BankCompliancePortal />} />
            <Route path="*" element={<Navigate to="/central" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
};

export default App;
