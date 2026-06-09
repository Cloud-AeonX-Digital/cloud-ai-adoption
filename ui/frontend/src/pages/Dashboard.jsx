import { useEffect, useState, useCallback } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { Bell, Zap, AlertTriangle, Ticket } from 'lucide-react';
import { api } from '../api';
import { SEV_CLASS, SEV_DOT, ACT_CLASS, SEV_ICON, Badge, Card, fmtAgo, fmtTime } from '../utils';
import Drawer from '../components/Drawer';

const BAR_COLORS = { critical: '#ef4444', high: '#f97316', medium: '#fbbf24', low: '#34d399' };
const PIE_COLORS = ['#6c8cff','#34d399','#f97316','#f87171','#a78bfa','#22d3ee','#fbbf24','#fb923c'];

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [liveProblems, setLiveProblems] = useState([]);
  const [sbTab, setSbTab] = useState('problems');
  const [selectedId, setSelectedId] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);

  const load = useCallback(async () => {
    const [s, inc, lp] = await Promise.all([api.stats(), api.incidents({ limit: 100 }), api.liveProblems()]);
    setStats(s); setIncidents(inc); setLiveProblems(lp);
    setLastRefresh(new Date());
  }, []);

  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [load]);

  const chartData = (() => {
    const now = Date.now(), buckets = 36, ms = 5 * 60 * 1000;
    const B = Array.from({ length: buckets }, (_, i) => {
      const t = new Date(now - (buckets - 1 - i) * ms);
      return { t: t.getHours() + ':' + String(t.getMinutes()).padStart(2, '0'), critical: 0, high: 0, medium: 0, low: 0 };
    });
    stats?.timeline?.forEach(({ bucket_epoch, severity, count }) => {
      const idx = Math.floor((parseInt(bucket_epoch) * 1000 - (now - buckets * ms)) / ms);
      if (idx >= 0 && idx < buckets && B[idx][severity] !== undefined) B[idx][severity] += count;
    });
    return B.filter((_, i) => i % 2 === 0);
  })();

  const activeProblems = liveProblems.filter(p => p.status === 'problem');
  const sbList = sbTab === 'problems' ? activeProblems : liveProblems;
  const now = Math.floor(Date.now() / 1000);

  const ttStyle = { background: 'var(--surface)', border: '1px solid var(--border)', fontSize: 11, borderRadius: 8, color: 'var(--text)' };

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-72 flex-shrink-0 border-r border-app bg-surface flex flex-col">
        <div className="p-3 border-b border-app">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-widest text-faint">🔴 Live Problems</span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full border sev-critical">{activeProblems.length}</span>
          </div>
          <div className="flex gap-1 mt-2">
            {['problems', 'recent'].map(t => (
              <button key={t} onClick={() => setSbTab(t)}
                className="flex-1 text-[11px] font-semibold py-1 rounded-md transition-all capitalize"
                style={sbTab === t
                  ? { background: 'var(--blue-bg)', color: 'var(--blue)', border: '1px solid var(--border2)' }
                  : { color: 'var(--text3)', border: '1px solid transparent' }}>
                {t}
              </button>
            ))}
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {sbList.length === 0 ? (
            <div className="p-6 text-center text-faint text-xs">
              ✅ No {sbTab === 'problems' ? 'active problems' : 'recent events'}
            </div>
          ) : sbList.map(p => (
            <div key={p.id}
              className="p-3 border-b border-app cursor-pointer transition-colors"
              style={{ ':hover': { background: 'var(--surface2)' } }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--surface2)'}
              onMouseLeave={e => e.currentTarget.style.background = ''}
              onClick={() => { const m = incidents.find(i => i.alert_name === p.name); if (m) setSelectedId(m.id); }}>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: SEV_DOT[p.severity] || '#6b7280' }} />
                <span className="text-xs font-semibold flex-1 truncate text-primary">{p.host}</span>
                <span className="text-[10px] text-faint">{fmtAgo(now - p.clock)}</span>
              </div>
              <p className="text-[11px] text-muted mt-1 ml-4 truncate">{p.name}</p>
              <div className="flex gap-1.5 mt-1.5 ml-4 flex-wrap">
                <Badge cls={SEV_CLASS[p.severity]}>{SEV_ICON[p.severity]} {p.severity}</Badge>
                {p.status === 'resolved' && <Badge cls="act-auto">✓ Resolved</Badge>}
                {p.acknowledged && <Badge cls="act-ticket">Acked</Badge>}
              </div>
            </div>
          ))}
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4 bg-app">
        {/* Stats */}
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: 'Total Alerts', value: stats?.total ?? '—', icon: <Bell size={18}/>, color: 'var(--blue)', bg: 'var(--blue-bg)' },
            { label: 'Actionable', value: stats?.actionable ?? '—', icon: <Zap size={18}/>, color: 'var(--green)', bg: 'var(--green-bg)' },
            { label: 'Escalated', value: stats?.escalated ?? '—', icon: <AlertTriangle size={18}/>, color: 'var(--red)', bg: 'var(--red-bg)' },
            { label: 'Tickets Created', value: stats?.tickets_created ?? '—', icon: <Ticket size={18}/>, color: 'var(--yellow)', bg: 'var(--yellow-bg)' },
          ].map(({ label, value, icon, color, bg }) => (
            <Card key={label}>
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs text-muted">{label}</p>
                  <p className="text-3xl font-bold mt-1 tracking-tight" style={{ color }}>{value}</p>
                </div>
                <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: bg, color }}>
                  {icon}
                </div>
              </div>
              <p className="text-[10px] text-faint mt-2">{lastRefresh ? `Updated ${fmtTime(lastRefresh)}` : 'Loading...'}</p>
            </Card>
          ))}
        </div>

        {/* Charts */}
        <div className="grid grid-cols-2 gap-4">
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-primary">Alert Activity — Last 3h</h3>
              <span className="text-xs text-faint">{stats?.total ?? 0} total</span>
            </div>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                <XAxis dataKey="t" tick={{ fontSize: 9, fill: 'var(--text3)' }} interval={5} />
                <YAxis tick={{ fontSize: 9, fill: 'var(--text3)' }} allowDecimals={false} />
                <Tooltip contentStyle={ttStyle} />
                {['critical','high','medium','low'].map(s =>
                  <Bar key={s} dataKey={s} stackId="a" fill={BAR_COLORS[s]} radius={s==='critical'?[3,3,0,0]:[0,0,0,0]} />
                )}
              </BarChart>
            </ResponsiveContainer>
            <div className="flex gap-3 mt-2 flex-wrap">
              {['critical','high','medium','low'].map(s => (
                <span key={s} className="flex items-center gap-1 text-[10px] text-muted">
                  <span className="w-2 h-2 rounded-sm" style={{ background: BAR_COLORS[s] }} />{s}
                </span>
              ))}
            </div>
          </Card>

          <Card>
            <h3 className="text-sm font-semibold text-primary mb-3">By Category</h3>
            {stats?.byCategory?.length > 0 ? (
              <div className="flex gap-4 items-center">
                <PieChart width={110} height={110}>
                  <Pie data={stats.byCategory} dataKey="count" nameKey="category" cx="50%" cy="50%" innerRadius={28} outerRadius={48}>
                    {stats.byCategory.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={ttStyle} />
                </PieChart>
                <div className="space-y-1.5 flex-1">
                  {stats.byCategory.slice(0, 6).map((c, i) => (
                    <div key={c.category} className="flex items-center gap-2 text-xs">
                      <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                      <span className="text-muted flex-1 truncate">{c.category}</span>
                      <span className="font-semibold text-primary">{c.count}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : <p className="text-faint text-sm">No data yet</p>}
          </Card>
        </div>

        {/* Recent alerts — table layout */}
        <Card>
          <h3 className="text-sm font-semibold text-primary mb-3">Recent Alerts</h3>
          <div style={{ display: 'table', width: '100%', borderCollapse: 'collapse' }}>
            {/* Header */}
            <div style={{ display: 'table-row' }}>
              {['Host', 'Alert', 'Severity', 'Action', 'Time'].map(h => (
                <div key={h} style={{ display: 'table-cell', padding: '4px 10px', fontSize: 10,
                  fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em',
                  color: 'var(--text3)', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap' }}>
                  {h}
                </div>
              ))}
            </div>
            {incidents.slice(0, 8).map((inc, i) => (
              <div key={inc.id} onClick={() => setSelectedId(inc.id)}
                style={{ display: 'table-row', cursor: 'pointer', borderBottom: i < 7 ? '1px solid var(--border)' : 'none' }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--surface2)'}
                onMouseLeave={e => e.currentTarget.style.background = ''}>
                <div style={{ display: 'table-cell', padding: '9px 10px', fontSize: 12, fontWeight: 500,
                  color: 'var(--text)', whiteSpace: 'nowrap', maxWidth: 160, overflow: 'hidden',
                  textOverflow: 'ellipsis', verticalAlign: 'middle' }}>
                  {inc.host_name}
                </div>
                <div style={{ display: 'table-cell', padding: '9px 10px', fontSize: 12,
                  color: 'var(--text2)', maxWidth: 240, overflow: 'hidden',
                  textOverflow: 'ellipsis', whiteSpace: 'nowrap', verticalAlign: 'middle' }}
                  title={inc.alert_name}>
                  {inc.alert_name}
                </div>
                <div style={{ display: 'table-cell', padding: '9px 10px', verticalAlign: 'middle', whiteSpace: 'nowrap' }}>
                  <Badge cls={SEV_CLASS[inc.severity]}>{SEV_ICON[inc.severity]} {inc.severity}</Badge>
                </div>
                <div style={{ display: 'table-cell', padding: '9px 10px', verticalAlign: 'middle', whiteSpace: 'nowrap' }}>
                  <Badge cls={ACT_CLASS[inc.action]}>{inc.action}</Badge>
                </div>
                <div style={{ display: 'table-cell', padding: '9px 10px', fontSize: 11,
                  color: 'var(--text3)', whiteSpace: 'nowrap', verticalAlign: 'middle' }}>
                  {fmtTime(inc.triggered_at)}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Drawer id={selectedId} onClose={() => setSelectedId(null)} />
    </div>
  );
}
