import { useEffect, useState, useCallback } from 'react';
import { CheckCircle, XCircle, Clock } from 'lucide-react';
import { api } from '../api';
import { SEV_CLASS, SEV_ICON, ACT_CLASS, Badge, fmtDT, fmtAgo } from '../utils';
import ApprovalDetail from '../components/ApprovalDetail';

const STATUS_STYLE = {
  pending:  { bg: 'var(--yellow-bg)', color: 'var(--yellow)', border: 'var(--yellow)', icon: <Clock size={14}/>,       label: 'Pending' },
  approved: { bg: 'var(--green-bg)',  color: 'var(--green)',  border: 'var(--green)',  icon: <CheckCircle size={14}/>, label: 'Approved' },
  rejected: { bg: 'var(--red-bg)',    color: 'var(--red)',    border: 'var(--red)',    icon: <XCircle size={14}/>,     label: 'Rejected' },
  executed: { bg: 'var(--blue-bg)',   color: 'var(--blue)',   border: 'var(--blue)',   icon: <CheckCircle size={14}/>, label: 'Executed' },
  expired:  { bg: 'var(--surface2)', color: 'var(--text3)', border: 'var(--border)',  icon: <Clock size={14}/>,       label: 'Expired' },
};

export default function Approvals() {
  const [approvals, setApprovals] = useState([]);
  const [filter, setFilter] = useState('pending');
  const [deciding, setDeciding] = useState({});
  const [selected, setSelected] = useState(null);

  const load = useCallback(() => {
    api.approvals(filter || undefined).then(setApprovals);
  }, [filter]);

  useEffect(() => { load(); const t = setInterval(load, 4000); return () => clearInterval(t); }, [load]);

  const pendingCount = approvals.filter(a => a.status === 'pending').length;

  async function decide(id, status, note = '') {
    setDeciding(d => ({ ...d, [id]: status }));
    await api.decide(id, status, 'mrinal.jani@aeonx.digital', note);
    setDeciding(d => { const n = { ...d }; delete n[id]; return n; });
    setSelected(null);
    load();
  }

  return (
    <div className="flex flex-1 overflow-hidden flex-col p-4 gap-3 bg-app">
      {/* Header */}
      <div className="flex items-center gap-4">
        <h2 className="text-base font-bold text-primary">Alert Approvals</h2>
        {pendingCount > 0 && (
          <span className="text-xs font-bold px-2.5 py-1 rounded-full border animate-pulse"
            style={{ background: 'var(--yellow-bg)', color: 'var(--yellow)', borderColor: 'var(--yellow)' }}>
            {pendingCount} pending
          </span>
        )}
        <div className="flex gap-1 ml-auto">
          {['pending','approved','rejected','all'].map(s => (
            <button key={s} onClick={() => setFilter(s === 'all' ? '' : s)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all capitalize"
              style={filter === (s === 'all' ? '' : s)
                ? { background: 'var(--blue-bg)', color: 'var(--blue)', border: '1px solid var(--border2)' }
                : { color: 'var(--text2)', border: '1px solid transparent' }}>
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto space-y-2">
        {approvals.length === 0 ? (
          <div className="card flex items-center justify-center py-16 text-faint text-sm">
            {filter === 'pending' ? '✅ No pending approvals' : 'No approvals found'}
          </div>
        ) : approvals.map(a => {
          const st = STATUS_STYLE[a.status] || STATUS_STYLE.pending;
          const meta = a.metadata || {};
          const host = meta.host?.name || '?';
          const client = meta.client?.name || 'N/A';
          const alertName = meta.alert?.name || a.description || '';
          const alertSev = meta.alert?.severity || '';
          const aiAction = meta.ai_action || '';
          const isPending = a.status === 'pending';
          const now = Math.floor(Date.now() / 1000);

          return (
            <div key={a.id}
              onClick={() => setSelected(a)}
              className="card"
              style={{
                border: isPending ? `1px solid ${st.border}44` : '1px solid var(--border)',
                cursor: 'pointer', transition: 'all 0.15s'
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--border2)'; e.currentTarget.style.boxShadow = '0 2px 12px rgba(0,0,0,0.08)'; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = isPending ? `${st.border}44` : 'var(--border)'; e.currentTarget.style.boxShadow = ''; }}>

              <div className="flex items-start gap-3">
                {/* Status icon */}
                <div style={{ width: 36, height: 36, borderRadius: 10, flexShrink: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: st.bg, color: st.color, border: `1px solid ${st.border}44` }}>
                  {st.icon}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-semibold text-primary truncate">{alertName}</p>
                    <span className="text-[10px] text-faint whitespace-nowrap">{fmtDT(a.created_at)}</span>
                  </div>
                  <p className="text-xs text-muted mt-0.5">🖥 {host} &nbsp;·&nbsp; 👤 {client}</p>

                  <div className="flex gap-2 mt-2 flex-wrap items-center">
                    <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 20,
                      textTransform: 'uppercase', border: `1px solid ${st.border}66`,
                      background: st.bg, color: st.color }}>{st.label}</span>
                    {alertSev && <Badge cls={`sev-${alertSev}`}>{SEV_ICON[alertSev]} {alertSev}</Badge>}
                    {aiAction && <Badge cls={ACT_CLASS[aiAction] || ''}>{aiAction}</Badge>}
                    {meta.solution_id && <span style={{ fontSize: 10, color: 'var(--blue)' }}>{meta.solution_id}</span>}
                    {isPending && a.expires_at && (
                      <span className="text-[10px] text-faint ml-auto">
                        expires {fmtAgo(new Date(a.expires_at).getTime()/1000 - now)}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted mt-2 line-clamp-2">{a.description}</p>
                </div>
              </div>

              {/* Inline approve/reject for pending — stop propagation */}
              {isPending && (
                <div className="flex gap-2 mt-3 pt-3" style={{ borderTop: '1px solid var(--border)' }}
                  onClick={e => e.stopPropagation()}>
                  <input placeholder="Optional note…" id={`note-${a.id}`} className="ctrl flex-1 text-xs" />
                  <button onClick={() => decide(a.id, 'rejected', document.getElementById(`note-${a.id}`)?.value)}
                    disabled={!!deciding[a.id]}
                    style={{ display:'flex', alignItems:'center', gap:5, padding:'6px 14px', borderRadius:8,
                      fontSize:12, fontWeight:600, cursor:'pointer', border:'1px solid var(--red)33',
                      background:'var(--red-bg)', color:'var(--red)' }}>
                    <XCircle size={13}/> {deciding[a.id]==='rejected'?'Rejecting…':'Reject'}
                  </button>
                  <button onClick={() => decide(a.id, 'approved', document.getElementById(`note-${a.id}`)?.value)}
                    disabled={!!deciding[a.id]}
                    style={{ display:'flex', alignItems:'center', gap:5, padding:'6px 18px', borderRadius:8,
                      fontSize:12, fontWeight:700, cursor:'pointer', border:'none',
                      background:'var(--green)', color:'#fff' }}>
                    <CheckCircle size={13}/> {deciding[a.id]==='approved'?'Approving…':'Approve'}
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Detail panel */}
      <ApprovalDetail
        approval={selected}
        onClose={() => setSelected(null)}
        onDecide={decide}
        deciding={deciding}
      />
    </div>
  );
}
