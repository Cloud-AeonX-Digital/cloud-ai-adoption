import { useEffect, useState } from 'react';
import { X, ShieldCheck } from 'lucide-react';
import { api } from '../api';
import { SEV_CLASS, ACT_CLASS, SEV_ICON, Badge, fmtDT } from '../utils';
import ApprovalDetail from './ApprovalDetail';

const STEP_DEF = {
  alert_received: { icon: '🔔', label: 'Alert Received',    color: 'var(--green)' },
  ai_classified:  { icon: '🤖', label: 'AI Classified',     color: 'var(--blue)' },
  action_decided: { icon: '⚡', label: 'Action Decided',    color: 'var(--yellow)' },
  ticket_created: { icon: '🎫', label: 'Ticket Created',    color: 'var(--blue)' },
  email_sent:     { icon: '📧', label: 'Email Sent',        color: 'var(--purple)' },
  escalated:      { icon: '🚨', label: 'Escalated',         color: 'var(--red)' },
  resolved:       { icon: '✅', label: 'Resolved',          color: 'var(--green)' },
};

function SectionHeader({ children }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
      <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase',
        letterSpacing: '0.09em', color: 'var(--text3)', whiteSpace: 'nowrap' }}>
        {children}
      </span>
      <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
    </div>
  );
}

function KVRow({ label, value, mono }) {
  if (!value) return null;
  return (
    <div style={{ display: 'flex', gap: 12, fontSize: 12, marginBottom: 7 }}>
      <span style={{ color: 'var(--text2)', minWidth: 110, flexShrink: 0 }}>{label}</span>
      <span style={{ color: 'var(--text)', wordBreak: 'break-all',
        fontFamily: mono ? 'monospace' : undefined, fontSize: mono ? 11 : 12 }}>
        {value}
      </span>
    </div>
  );
}

export default function Drawer({ id, onClose }) {
  const [inc, setInc] = useState(null);
  const [approval, setApproval] = useState(null);
  const [showApproval, setShowApproval] = useState(false);

  useEffect(() => {
    if (!id) { setInc(null); setApproval(null); return; }
    api.incident(id).then(d => {
      setInc(d);
      // Fetch linked approval if exists
      if (d?.approval_id) {
        api.approval(d.approval_id).then(setApproval).catch(() => {});
      } else {
        // Try fetching from Express by incident_id
        fetch(`http://localhost:3001/approvals?incident_id=${d?.id}`)
          .then(r => r.json())
          .then(list => { if (list.length) setApproval(list[0]); })
          .catch(() => {});
      }
    });
  }, [id]);

  if (!id) return null;

  const raw = inc?.raw || {};
  const cls = raw.classification || {};
  const workflow = raw.workflow || [];
  const steps = raw.resolution_steps || [];

  return (
    <>
      {/* Overlay */}
      <div onClick={onClose} style={{
        position: 'fixed', inset: 0, zIndex: 40,
        background: 'rgba(0,0,0,0.4)', backdropFilter: 'blur(2px)'
      }} />

      {/* Drawer */}
      <div style={{
        position: 'fixed', right: 0, top: 0, bottom: 0, width: '45vw', minWidth: 520, zIndex: 50,
        background: 'var(--surface)', borderLeft: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', boxShadow: '-8px 0 32px rgba(0,0,0,0.15)'
      }}>
        {/* Header */}
        <div style={{
          padding: '18px 20px', borderBottom: '1px solid var(--border)',
          background: 'var(--surface)', flexShrink: 0
        }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <h2 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)',
                lineHeight: 1.3, marginBottom: 5, wordBreak: 'break-word' }}>
                {inc?.alert_name || '…'}
              </h2>
              <p style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 10 }}>
                🖥 {inc?.host_name || '?'} &nbsp;·&nbsp; {inc?.host_ip || ''} &nbsp;·&nbsp; 👤 {inc?.client_name || 'N/A'}
              </p>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                {inc?.severity && <Badge cls={SEV_CLASS[inc.severity]}>{SEV_ICON[inc.severity]} {inc.severity?.toUpperCase()}</Badge>}
                {inc?.actionable !== undefined && (
                  <span style={{
                    fontSize: 10, fontWeight: 700, padding: '2px 9px', borderRadius: 20,
                    textTransform: 'uppercase', letterSpacing: '0.03em', border: '1px solid',
                    background: inc.actionable ? 'var(--green-bg)' : 'var(--surface2)',
                    color: inc.actionable ? 'var(--green)' : 'var(--text2)',
                    borderColor: inc.actionable ? 'var(--green)' : 'var(--border)',
                  }}>
                    {inc.actionable ? '✓ ACTIONABLE' : '✗ NON-ACTIONABLE'}
                  </span>
                )}
                {inc?.action && <Badge cls={ACT_CLASS[inc.action]}>{inc.action}</Badge>}
                {inc?.ticket_id && <Badge cls="act-ticket">🎫 #{inc.ticket_id}</Badge>}
                {inc?.solution_id && (
                  <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--blue)',
                    background: 'var(--blue-bg)', padding: '2px 8px', borderRadius: 20,
                    border: '1px solid var(--border)' }}>
                    {inc.solution_id}
                  </span>
                )}
              </div>
              {/* Approval button — separate row, right-aligned */}
              {approval && (
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 10 }}>
                  <button onClick={() => setShowApproval(true)} style={{
                    display: 'flex', alignItems: 'center', gap: 7, padding: '8px 18px',
                    borderRadius: 10, fontSize: 13, fontWeight: 700, cursor: 'pointer',
                    background: approval.status === 'pending' ? 'var(--yellow-bg)' : 'var(--green-bg)',
                    color: approval.status === 'pending' ? 'var(--yellow)' : 'var(--green)',
                    border: `1.5px solid ${approval.status === 'pending' ? 'var(--yellow)' : 'var(--green)'}`,
                    boxShadow: `0 2px 8px ${approval.status === 'pending' ? 'rgba(251,191,36,0.2)' : 'rgba(52,211,153,0.2)'}`,
                    transition: 'all 0.15s'
                  }}
                    onMouseEnter={e => e.currentTarget.style.opacity = '0.85'}
                    onMouseLeave={e => e.currentTarget.style.opacity = '1'}>
                    <ShieldCheck size={15} />
                    {approval.status === 'pending' ? '⏳ View Pending Approval' : `✓ Approval ${approval.status}`}
                  </button>
                </div>
              )}
            </div>
            <button onClick={onClose} style={{
              width: 30, height: 30, borderRadius: 8, flexShrink: 0, cursor: 'pointer',
              background: 'var(--surface2)', border: '1px solid var(--border)',
              color: 'var(--text2)', display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'all 0.15s'
            }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--red)'; e.currentTarget.style.color = 'var(--red)'; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text2)'; }}>
              <X size={15} />
            </button>
          </div>
        </div>

        {/* Scrollable body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', gap: 20 }}>
          {!inc ? (
            <div style={{ textAlign: 'center', paddingTop: 48, color: 'var(--text3)', fontSize: 13 }}>Loading…</div>
          ) : (
            <>
              {/* Workflow Timeline */}
              {workflow.length > 0 && (
                <section>
                  <SectionHeader>Workflow Timeline</SectionHeader>
                  <div style={{ position: 'relative', paddingLeft: 28 }}>
                    <div style={{ position: 'absolute', left: 11, top: 18, bottom: 12,
                      width: 2, background: 'var(--border)', borderRadius: 1 }} />
                    {workflow.map((s, i) => {
                      const d = STEP_DEF[s.step] || { icon: '•', label: s.step, color: 'var(--border2)' };
                      return (
                        <div key={i} style={{ display: 'flex', gap: 12, paddingBottom: i < workflow.length - 1 ? 18 : 0 }}>
                          <div style={{
                            position: 'absolute', left: 0,
                            width: 24, height: 24, borderRadius: '50%', flexShrink: 0,
                            border: `2px solid ${d.color}`, background: 'var(--surface)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: 11, zIndex: 1
                          }}>
                            {d.icon}
                          </div>
                          <div style={{ paddingTop: 2, paddingLeft: 4 }}>
                            <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', marginBottom: 2 }}>{d.label}</p>
                            <p style={{ fontSize: 12, color: 'var(--text2)', lineHeight: 1.5, marginBottom: 2 }}>{s.detail}</p>
                            <p style={{ fontSize: 10, color: 'var(--text3)' }}>{fmtDT(s.ts)}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </section>
              )}

              {/* AI Classification */}
              <section>
                <SectionHeader>AI Classification</SectionHeader>
                <div style={{ marginBottom: 4 }}>
                  <KVRow label="Actionable"  value={cls.actionable ? '✅ Yes — known solution' : '❌ No'} />
                  <KVRow label="Category"    value={cls.category} />
                  <KVRow label="Severity"    value={(cls.severity || '').toUpperCase()} />
                  <KVRow label="Action"      value={cls.action} />
                  <KVRow label="Confidence"  value={cls.confidence != null ? `${Math.round(cls.confidence * 100)}%` : null} />
                  <KVRow label="Solution ID" value={cls.solution_id || 'LLM fallback'} />
                </div>
                {cls.summary && (
                  <div style={{
                    marginTop: 10, padding: '10px 14px', fontSize: 12, lineHeight: 1.7,
                    color: 'var(--text)', borderRadius: '0 8px 8px 0',
                    background: 'var(--blue-bg)', borderLeft: '3px solid var(--blue)'
                  }}>
                    {cls.summary}
                  </div>
                )}
              </section>

              {/* Alert Details */}
              <section>
                <SectionHeader>Alert Details</SectionHeader>
                <KVRow label="Host"        value={inc.host_name} />
                <KVRow label="IP Address"  value={inc.host_ip} />
                <KVRow label="Client"      value={inc.client_name} />
                <KVRow label="AWS Account" value={inc.aws_account} mono />
                <KVRow label="Alert"       value={inc.alert_name} />
                <KVRow label="Status"      value={inc.alert_status} />
                <KVRow label="Value"       value={inc.alert_value} />
                <KVRow label="Triggered"   value={fmtDT(inc.triggered_at)} />
              </section>

              {/* Resolution Steps */}
              <section>
                <SectionHeader>
                  Resolution Steps {cls.solution_id ? `· ${cls.solution_id}` : ''}
                </SectionHeader>
                {steps.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {steps.map((s, i) => (
                      <div key={i} style={{
                        display: 'flex', gap: 10, padding: '9px 12px',
                        background: 'var(--surface2)', borderRadius: 8, alignItems: 'flex-start'
                      }}>
                        <span style={{
                          minWidth: 20, height: 20, borderRadius: 5,
                          background: 'var(--blue-bg)', color: 'var(--blue)',
                          fontSize: 10, fontWeight: 700, display: 'flex',
                          alignItems: 'center', justifyContent: 'center', flexShrink: 0
                        }}>{i + 1}</span>
                        <span style={{ fontSize: 12, color: 'var(--text2)', lineHeight: 1.6 }}>{s}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p style={{ fontSize: 12, color: 'var(--text3)' }}>No defined steps — LLM classified</p>
                )}
              </section>
            </>
          )}
        </div>
      </div>
      {showApproval && approval && (
        <ApprovalDetail
          approval={approval}
          onClose={() => setShowApproval(false)}
          onDecide={async (id, status, note) => {
            await api.decide(id, status, 'mrinal.jani@aeonx.digital', note || '');
            setShowApproval(false);
            api.approval(id).then(setApproval).catch(() => {});
          }}
          deciding={{}}
        />
      )}
    </>
  );
}
