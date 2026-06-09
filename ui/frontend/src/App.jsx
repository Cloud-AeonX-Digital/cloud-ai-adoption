import { useState, useEffect } from 'react';
import { LayoutDashboard, List, ShieldCheck, Sun, Moon } from 'lucide-react';
import Dashboard from './pages/Dashboard';
import Alerts from './pages/Alerts';
import Approvals from './pages/Approvals';
import { api } from './api';

export default function App() {
  const [page, setPage] = useState('dashboard');
  const [light, setLight] = useState(true);
  const [model, setModel] = useState('');
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    api.health().then(h => setModel(h.model || '')).catch(() => {});
  }, []);

  useEffect(() => {
    const poll = () => api.approvals('pending').then(a => setPendingCount(a.length)).catch(() => {});
    poll();
    const t = setInterval(poll, 4000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle('light', light);
  }, [light]);

  const pages = [
    { id: 'dashboard', label: 'Dashboard',  icon: <LayoutDashboard size={14} /> },
    { id: 'alerts',    label: 'All Alerts',  icon: <List size={14} /> },
    { id: 'approvals', label: 'Approvals',   icon: <ShieldCheck size={14} />, badge: pendingCount },
  ];

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-app text-primary">
      <nav className="h-12 bg-surface border-b border-app flex items-center px-4 gap-0 flex-shrink-0 shadow-sm">
        <div className="flex items-center gap-2.5 mr-6">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-sm shadow">🤖</div>
          <span className="font-bold text-sm"><span style={{ color: 'var(--blue)' }}>AeonX</span> AI Ops</span>
        </div>
        <div className="flex gap-1 flex-1">
          {pages.map(({ id, label, icon, badge }) => (
            <button key={id} onClick={() => setPage(id)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all relative"
              style={page === id
                ? { background: 'var(--blue-bg)', color: 'var(--blue)', border: '1px solid var(--border2)' }
                : { color: 'var(--text2)', border: '1px solid transparent' }}
              onMouseEnter={e => { if (page !== id) e.currentTarget.style.background = 'var(--surface2)'; }}
              onMouseLeave={e => { if (page !== id) e.currentTarget.style.background = ''; }}>
              {icon}{label}
              {badge > 0 && (
                <span className="ml-1 text-[10px] font-bold px-1.5 py-0.5 rounded-full animate-pulse"
                  style={{ background: 'var(--yellow)', color: '#000', minWidth: 16, textAlign: 'center' }}>
                  {badge}
                </span>
              )}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          {model && (
            <div className="flex items-center gap-1.5 rounded-full px-3 py-1 border border-app" style={{ background: 'var(--surface2)' }}>
              <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
              <span className="text-[11px] text-muted">{model}</span>
            </div>
          )}
          <button onClick={() => setLight(l => !l)}
            className="w-8 h-8 rounded-lg border border-app flex items-center justify-center text-muted transition-all hover:border-app2"
            style={{ background: 'var(--surface2)' }}>
            {light ? <Moon size={14} /> : <Sun size={14} />}
          </button>
        </div>
      </nav>

      <div className="flex flex-1 overflow-hidden bg-app">
        {page === 'dashboard' ? <Dashboard /> : page === 'alerts' ? <Alerts /> : <Approvals />}
      </div>
    </div>
  );
}
