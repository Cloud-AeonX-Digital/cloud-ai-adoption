export const SEV_CLASS = {
  critical: 'sev-critical', high: 'sev-high', medium: 'sev-medium',
  average: 'sev-average', low: 'sev-low', warning: 'sev-warning',
  disaster: 'sev-disaster', information: 'sev-information',
};

export const SEV_DOT = {
  critical: '#ef4444', high: '#f97316', medium: '#fbbf24', average: '#f97316',
  low: '#34d399', warning: '#fbbf24', disaster: '#ef4444', information: '#a78bfa',
};

export const ACT_CLASS = {
  'auto-remediate': 'act-auto', 'create-ticket': 'act-ticket',
  'escalate': 'act-escalate', 'deduplicated': 'act-dedup',
};

export const SEV_ICON = {
  critical:'🔴', high:'🟠', medium:'🟡', low:'🔵', warning:'🟡',
  average:'🟠', disaster:'🔴', information:'⚪', not_classified:'⚫',
};

export function fmtTime(ts) {
  return new Date(ts).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}
export function fmtDT(ts) {
  return new Date(ts).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' });
}
export function fmtAgo(sec) {
  if (sec < 60) return `${sec}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  return `${Math.floor(sec / 3600)}h ago`;
}

export function Badge({ children, cls = '' }) {
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wide border ${cls}`}>
      {children}
    </span>
  );
}

export function Card({ children, className = '' }) {
  return <div className={`card ${className}`}>{children}</div>;
}
