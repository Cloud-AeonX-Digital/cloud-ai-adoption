import { useEffect, useState, useCallback } from 'react';
import { Search, X } from 'lucide-react';
import { api } from '../api';
import { SEV_CLASS, ACT_CLASS, SEV_ICON, Badge, fmtDT } from '../utils';
import Drawer from '../components/Drawer';

export default function Alerts() {
  const [incidents, setIncidents] = useState([]);
  const [filters, setFilters] = useState({});
  const [form, setForm] = useState({ search: '', severity: '', action: '', actionable: '', account: '', category: '' });
  const [selectedId, setSelectedId] = useState(null);
  const [sortField, setSortField] = useState('triggered_at');
  const [sortDir, setSortDir] = useState(-1);

  useEffect(() => { api.filters().then(setFilters); }, []);

  const load = useCallback(() => {
    api.incidents({ ...form, limit: 300 }).then(setIncidents);
  }, [form]);

  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [load]);

  const sorted = [...incidents].sort((a, b) => {
    const av = a[sortField] || '', bv = b[sortField] || '';
    return av < bv ? sortDir : av > bv ? -sortDir : 0;
  });

  function sort(f) { setSortDir(sortField === f ? -sortDir : 1); setSortField(f); }
  function setF(k, v) { setForm(p => ({ ...p, [k]: v })); }
  function clear() { setForm({ search: '', severity: '', action: '', actionable: '', account: '', category: '' }); }

  const Th = ({ children, field }) => (
    <th onClick={() => sort(field)}
      className="px-3 py-2.5 text-left text-[10px] font-bold uppercase tracking-widest cursor-pointer whitespace-nowrap select-none"
      style={{ background: 'var(--surface2)', color: 'var(--text3)', borderBottom: '1px solid var(--border)' }}
      onMouseEnter={e => e.currentTarget.style.color = 'var(--text2)'}
      onMouseLeave={e => e.currentTarget.style.color = 'var(--text3)'}>
      {children} <span style={{ opacity: 0.4 }}>{sortField === field ? (sortDir === 1 ? '↑' : '↓') : '↕'}</span>
    </th>
  );

  const StaticTh = ({ children }) => (
    <th className="px-3 py-2.5 text-left text-[10px] font-bold uppercase tracking-widest whitespace-nowrap"
      style={{ background: 'var(--surface2)', color: 'var(--text3)', borderBottom: '1px solid var(--border)' }}>
      {children}
    </th>
  );

  return (
    <div className="flex flex-1 overflow-hidden flex-col p-4 gap-3 bg-app">
      {/* Filter bar */}
      <div className="card flex gap-2 flex-wrap items-center p-3">
        <div className="relative flex-1 min-w-40">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: 'var(--text3)' }} />
          <input value={form.search} onChange={e => setF('search', e.target.value)}
            placeholder="Search host, alert, client, account…"
            className="ctrl w-full pl-8" />
        </div>
        {[
          ['severity', ['critical','high','medium','low']],
          ['action', ['auto-remediate','create-ticket','escalate','deduplicated']],
          ['account', filters.accounts || []],
          ['category', filters.categories || []],
        ].map(([key, opts]) => (
          <select key={key} value={form[key]} onChange={e => setF(key, e.target.value)} className="ctrl capitalize">
            <option value="">All {key}s</option>
            {opts.map(o => <option key={o} value={o}>{o}</option>)}
          </select>
        ))}
        <select value={form.actionable} onChange={e => setF('actionable', e.target.value)} className="ctrl">
          <option value="">All Types</option>
          <option value="true">Actionable</option>
          <option value="false">Non-Actionable</option>
        </select>
        <button onClick={clear}
          className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg border transition-all"
          style={{ color: 'var(--text3)', borderColor: 'var(--border)', background: 'transparent' }}
          onMouseEnter={e => { e.currentTarget.style.color = 'var(--red)'; e.currentTarget.style.borderColor = 'var(--red)'; }}
          onMouseLeave={e => { e.currentTarget.style.color = 'var(--text3)'; e.currentTarget.style.borderColor = 'var(--border)'; }}>
          <X size={12} /> Clear
        </button>
        <span className="text-xs text-faint ml-auto">{sorted.length} / {incidents.length}</span>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto rounded-xl border border-app" style={{ background: 'var(--surface)' }}>
        <table className="w-full text-xs border-collapse">
          <thead className="sticky top-0 z-10">
            <tr>
              <Th field="triggered_at">Time</Th>
              <Th field="host_name">Host</Th>
              <StaticTh>Alert</StaticTh>
              <Th field="client_name">Client</Th>
              <Th field="aws_account">Account</Th>
              <Th field="severity">Severity</Th>
              <StaticTh>Type</StaticTh>
              <Th field="action">Action</Th>
              <StaticTh>Solution</StaticTh>
              <StaticTh>Ticket</StaticTh>
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 ? (
              <tr><td colSpan={10} className="py-16 text-center text-faint">No alerts match filters</td></tr>
            ) : sorted.map(inc => (
              <tr key={inc.id} onClick={() => setSelectedId(inc.id)}
                className="border-t cursor-pointer transition-colors"
                style={{ borderColor: 'var(--border)' }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--surface2)'}
                onMouseLeave={e => e.currentTarget.style.background = ''}>
                <td className="px-3 py-2.5 text-muted whitespace-nowrap">{fmtDT(inc.triggered_at)}</td>
                <td className="px-3 py-2.5 font-medium max-w-[140px] truncate text-primary" title={inc.host_name}>{inc.host_name}</td>
                <td className="px-3 py-2.5 text-muted max-w-[200px] truncate" title={inc.alert_name}>{inc.alert_name}</td>
                <td className="px-3 py-2.5 text-muted max-w-[120px] truncate">{inc.client_name || '—'}</td>
                <td className="px-3 py-2.5 font-mono text-[10px] text-faint">{inc.aws_account || '—'}</td>
                <td className="px-3 py-2.5"><Badge cls={SEV_CLASS[inc.severity]}>{SEV_ICON[inc.severity]} {inc.severity}</Badge></td>
                <td className="px-3 py-2.5">
                  <Badge cls={inc.actionable ? 'act-auto' : 'border text-faint'} style={{ borderColor: 'var(--border)' }}>
                    {inc.actionable ? '✓ Yes' : '✗ No'}
                  </Badge>
                </td>
                <td className="px-3 py-2.5"><Badge cls={ACT_CLASS[inc.action] || ''}>{inc.action}</Badge></td>
                <td className="px-3 py-2.5 text-[11px]" style={{ color: 'var(--blue)' }}>{inc.solution_id || '—'}</td>
                <td className="px-3 py-2.5">{inc.ticket_id ? <Badge cls="act-ticket">🎫 {inc.ticket_id}</Badge> : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Drawer id={selectedId} onClose={() => setSelectedId(null)} />
    </div>
  );
}
