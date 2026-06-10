import { X, CheckCircle, XCircle, Mail, Terminal, RefreshCw, AlertTriangle, HardDrive, MessageSquare, Send, Bot, Loader2 } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { SEV_CLASS, SEV_ICON, ACT_CLASS, Badge, fmtDT } from '../utils';
import { api } from '../api';

const STATUS_STYLE = {
  pending:  { bg: 'var(--yellow-bg)', color: 'var(--yellow)', border: 'var(--yellow)', label: 'Pending Approval' },
  approved: { bg: 'var(--green-bg)',  color: 'var(--green)',  border: 'var(--green)',  label: 'Approved' },
  rejected: { bg: 'var(--red-bg)',    color: 'var(--red)',    border: 'var(--red)',    label: 'Rejected' },
  executed: { bg: 'var(--blue-bg)',   color: 'var(--blue)',   border: 'var(--blue)',   label: 'Executed' },
  expired:  { bg: 'var(--surface2)', color: 'var(--text3)', border: 'var(--border)',  label: 'Expired' },
};

// Map solution/category to a human-readable action preview
function ActionPreview({ approval }) {
  const meta = approval?.metadata || {};
  const category = approval?.type || '';
  const steps = meta.solution_steps || [];
  const aiAction = meta.ai_action || '';
  const host = meta.host?.name || '?';
  const alertName = meta.alert?.name || '';
  const alertValue = meta.alert?.item_value || '';

  const previews = {
    'website-down': {
      icon: <Terminal size={15} />,
      title: 'Service Restart Command',
      color: 'var(--blue)',
      preview: [
        { label: 'Step 1 — SSM Run Command', code: `sudo systemctl restart nginx\n# or: sudo systemctl restart apache2` },
        { label: 'Step 2 — Verify', code: `curl -s -o /dev/null -w "%{http_code}" http://${meta.host?.ip || 'HOST_IP'}/` },
        { label: 'Step 3 (if still down) — EC2 Restart', code: `aws ec2 stop-instances --instance-ids ${meta.host?.instance_id || 'INSTANCE_ID'}\naws ec2 start-instances --instance-ids ${meta.host?.instance_id || 'INSTANCE_ID'}` },
      ]
    },
    'high-memory': {
      icon: <RefreshCw size={15} />,
      title: 'Client Email Preview',
      color: 'var(--orange)',
      preview: [
        { label: 'Email to client', code: `Subject: ⚠️ High Memory Alert — ${host}\n\nDear Client Team,\n\nHigh memory utilization detected on ${host}.\nCurrent usage: ${alertValue}\n\nRecommended Actions:\n1. Check running processes\n2. Restart memory-intensive services\n3. Consider instance type upgrade if recurring\n\nRegards,\nAeonX Cloud Operations` },
      ]
    },
    'service-down': {
      icon: <Terminal size={15} />,
      title: 'Service Restart Commands',
      color: 'var(--yellow)',
      preview: [
        { label: 'Step 1 — Local restart', code: `net start AwsReplicationVolumeUpdaterService\n# or: sc start AwsReplicationVolumeUpdaterService` },
        { label: 'Step 2 — Verify', code: `sc query AwsReplicationVolumeUpdaterService | findstr STATE` },
        { label: 'Step 3 (if fails) — SSM Run Command', code: `aws ssm send-command --instance-id ${meta.host?.instance_id || 'INSTANCE_ID'} \\\n  --document-name AWS-RunPowerShellScript \\\n  --parameters 'commands=["Restart-Service AwsReplicationVolumeUpdaterService"]'` },
      ]
    },
    'agent-unavailable': {
      icon: <Terminal size={15} />,
      title: 'Zabbix Agent Restart',
      color: 'var(--blue)',
      preview: [
        { label: 'SSM Run Command', code: `# Linux\nsudo systemctl restart zabbix-agent2\n\n# Windows\nRestart-Service -Name "Zabbix Agent"` },
        { label: 'Verify', code: `systemctl is-active zabbix-agent2` },
      ]
    },
    'disk-space': {
      icon: <HardDrive size={15} />,
      title: 'EBS Volume Expansion Plan',
      color: 'var(--red)',
      preview: [
        { label: 'Client email (sent first)', code: `Subject: 🔴 Low Disk Space Alert — ${host}\n\nDisk usage critical: ${alertValue}\nFilesystem needs expansion.\n\nPlease reply with approved size increase (e.g. "+20 GB").` },
        { label: 'After approval — AWS SDK', code: `aws ec2 modify-volume \\\n  --volume-id <VOLUME_ID> \\\n  --size <NEW_SIZE_GB>\n\n# Then extend filesystem:\ngrowpart /dev/nvme0n1 1\nresize2fs /dev/nvme0n1p1` },
      ]
    },
    'ec2-terminated': {
      icon: <AlertTriangle size={15} />,
      title: 'Escalation Actions',
      color: 'var(--red)',
      preview: [
        { label: 'Check Auto Scaling Group', code: `aws ec2 describe-instances \\\n  --instance-ids ${meta.host?.instance_id || 'INSTANCE_ID'} \\\n  --query 'Reservations[].Instances[].Tags[?Key==\`aws:autoscaling:groupName\`]'` },
        { label: 'If NOT in ASG — alert client', code: `Subject: 🔴 URGENT: EC2 Terminated — ${host}\n\nEC2 instance ${meta.host?.instance_id || ''} has been terminated.\nImmediate investigation required.` },
      ]
    },
    'high-cpu': {
      icon: <Mail size={15} />,
      title: 'Client Notification Email',
      color: 'var(--orange)',
      preview: [
        { label: 'Email to client', code: `Subject: ⚠️ High CPU Alert — ${host}\n\nCPU utilization: ${alertValue}\n\nPlease check running processes and identify high-CPU tasks.\n\nOur team is monitoring. Contact us if you need help.` },
      ]
    },
  };

  const def = previews[category] || {
    icon: <Terminal size={15} />, title: 'Proposed Action', color: 'var(--blue)',
    preview: [{ label: 'Action', code: approval?.proposed_action || 'No action preview available' }]
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <div style={{ width: 28, height: 28, borderRadius: 8, display: 'flex', alignItems: 'center',
          justifyContent: 'center', background: `color-mix(in srgb, ${def.color} 15%, transparent)`,
          color: def.color, border: `1px solid color-mix(in srgb, ${def.color} 30%, transparent)` }}>
          {def.icon}
        </div>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>{def.title}</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {def.preview.map((p, i) => (
          <div key={i}>
            <p style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase',
              letterSpacing: '0.06em', color: 'var(--text3)', marginBottom: 6 }}>{p.label}</p>
            <pre style={{
              fontSize: 11, lineHeight: 1.6, padding: '10px 14px', borderRadius: 8,
              background: 'var(--surface2)', color: 'var(--text)', fontFamily: 'monospace',
              whiteSpace: 'pre-wrap', wordBreak: 'break-all', margin: 0,
              border: '1px solid var(--border)'
            }}>{p.code}</pre>
          </div>
        ))}
      </div>
    </div>
  );
}

function KV({ label, value, mono }) {
  if (!value) return null;
  return (
    <div style={{ display: 'flex', gap: 10, fontSize: 12, marginBottom: 6 }}>
      <span style={{ color: 'var(--text2)', minWidth: 100, flexShrink: 0 }}>{label}</span>
      <span style={{ color: 'var(--text)', fontFamily: mono ? 'monospace' : undefined, fontSize: mono ? 11 : 12 }}>{value}</span>
    </div>
  );
}

function SectionHeader({ children }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, marginTop: 4 }}>
      <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase',
        letterSpacing: '0.09em', color: 'var(--text3)', whiteSpace: 'nowrap' }}>{children}</span>
      <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
    </div>
  );
}

function AivexMiniChat({ approval }) {
  const meta = approval?.metadata || {};
  const context = {
    host: meta.host?.name,
    instance_id: meta.host?.instance_id,
    account_id: meta.client?.aws_account,
  };
  const alertName = meta.alert?.name || approval?.description || '';
  const initialQ = alertName
    ? `What do you know about this alert on ${meta.host?.name || 'this host'}: "${alertName}"?`
    : '';

  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  // Auto-fetch history when opened
  useEffect(() => {
    if (initialQ && messages.length === 0) sendMsg(initialQ, true);
  }, []); // eslint-disable-line

  async function sendMsg(question, silent = false) {
    const q = (question || input).trim();
    if (!q || loading) return;
    setInput('');
    if (!silent) setMessages(m => [...m, { role: 'user', text: q }]);
    setLoading(true);
    try {
      const res = await api.chat(q, context);
      setMessages(m => [...m, {
        role: 'assistant',
        text: res.answer,
        meta: res.tools_used?.length ? `— ${res.tools_used.join(', ')}` : '',
      }]);
    } catch (e) {
      setMessages(m => [...m, { role: 'assistant', text: `Error: ${e.message}`, error: true }]);
    }
    setLoading(false);
  }

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
      {/* Message area */}
      <div style={{ maxHeight: 260, overflowY: 'auto', padding: '12px 14px',
        display: 'flex', flexDirection: 'column', gap: 10, background: 'var(--surface2)' }}>
        {loading && messages.length === 0 && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', color: 'var(--text3)', fontSize: 12 }}>
            <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} />
            Fetching alert history…
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i}>
            {m.role === 'user' && (
              <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 2 }}>You</div>
            )}
            <div style={{
              fontSize: 12, lineHeight: 1.65, color: m.error ? 'var(--red)' : 'var(--text)',
              whiteSpace: 'pre-wrap', padding: m.role === 'assistant' ? '8px 12px' : '0',
              background: m.role === 'assistant' ? 'var(--surface)' : 'transparent',
              borderRadius: 8, border: m.role === 'assistant' ? '1px solid var(--border)' : 'none',
            }}>{m.text}</div>
            {m.meta && <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 3, paddingLeft: 2 }}>{m.meta}</div>}
          </div>
        ))}
        {loading && messages.length > 0 && (
          <Loader2 size={13} style={{ color: 'var(--text3)', animation: 'spin 1s linear infinite' }} />
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{ display: 'flex', gap: 0, borderTop: '1px solid var(--border)' }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMsg()}
          disabled={loading}
          placeholder="Ask Aivex about this alert…"
          style={{
            flex: 1, padding: '9px 12px', fontSize: 12, background: 'var(--surface)',
            border: 'none', outline: 'none', color: 'var(--text)',
          }}
        />
        <button onClick={() => sendMsg()} disabled={!input.trim() || loading}
          style={{
            padding: '0 14px', background: 'var(--blue)', border: 'none', cursor: 'pointer',
            color: '#fff', opacity: (!input.trim() || loading) ? 0.4 : 1,
          }}>
          <Send size={13} />
        </button>
      </div>
    </div>
  );
}

export default function ApprovalDetail({ approval, onClose, onDecide, deciding }) {
  if (!approval) return null;

  const st = STATUS_STYLE[approval.status] || STATUS_STYLE.pending;
  const meta = approval.metadata || {};
  const alertSev = meta.alert?.severity || meta.severity || '';
  const alertName = meta.alert?.name || approval.description || '';
  const isPending = approval.status === 'pending';

  return (
    <>
      <div onClick={onClose} style={{
        position: 'fixed', inset: 0, zIndex: 60,
        background: 'rgba(0,0,0,0.4)', backdropFilter: 'blur(2px)'
      }} />
      <div style={{
        position: 'fixed', left: '10%', right: '10%', top: 0, bottom: 0, zIndex: 70,
        background: 'var(--surface)', borderLeft: '1px solid var(--border)', borderRight: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', boxShadow: '0 0 60px rgba(0,0,0,0.25)'
      }}>
        {/* Header */}
        <div style={{ padding: '18px 20px', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span style={{
                  fontSize: 10, fontWeight: 700, padding: '3px 10px', borderRadius: 20,
                  textTransform: 'uppercase', letterSpacing: '0.04em', border: '1px solid',
                  background: st.bg, color: st.color, borderColor: `${st.border}66`
                }}>{st.label}</span>
                <span style={{ fontSize: 10, color: 'var(--text3)' }}>{fmtDT(approval.created_at)}</span>
              </div>
              <h2 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', lineHeight: 1.3, marginBottom: 5, wordBreak: 'break-word' }}>
                {alertName}
              </h2>
              <p style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 8 }}>
                🖥 {meta.host?.name || '?'} &nbsp;·&nbsp; 👤 {meta.client?.name || 'N/A'} &nbsp;·&nbsp; {meta.aws_account || meta.client?.aws_account || ''}
              </p>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {alertSev && <Badge cls={`sev-${alertSev}`}>{SEV_ICON[alertSev]} {alertSev?.toUpperCase()}</Badge>}
                {meta.ai_action && <Badge cls={ACT_CLASS[meta.ai_action] || ''}>{meta.ai_action}</Badge>}
                {meta.solution_id && (
                  <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--blue)',
                    background: 'var(--blue-bg)', padding: '2px 8px', borderRadius: 20, border: '1px solid var(--border)' }}>
                    {meta.solution_id}
                  </span>
                )}
              </div>
            </div>
            <button onClick={onClose} style={{
              width: 30, height: 30, borderRadius: 8, cursor: 'pointer', flexShrink: 0,
              background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text2)',
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--red)'; e.currentTarget.style.color = 'var(--red)'; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text2)'; }}>
              <X size={15} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* AI Summary */}
          <section>
            <SectionHeader>AI Assessment</SectionHeader>
            {approval.description && (
              <div style={{
                padding: '10px 14px', fontSize: 13, lineHeight: 1.7, color: 'var(--text)',
                borderRadius: '0 8px 8px 0', background: 'var(--blue-bg)', borderLeft: '3px solid var(--blue)',
                marginBottom: 12
              }}>
                {approval.description}
              </div>
            )}
            <KV label="Alert"       value={alertName} />
            <KV label="Host"        value={meta.host?.name} />
            <KV label="IP"          value={meta.host?.ip} />
            <KV label="Client"      value={meta.client?.name} />
            <KV label="AWS Account" value={meta.client?.aws_account} mono />
            <KV label="Metric"      value={meta.alert?.item_value} />
            <KV label="Confidence"  value={meta.confidence != null ? `${Math.round(meta.confidence * 100)}%` : null} />
          </section>

          {/* Action preview */}
          <section>
            <SectionHeader>What Will Be Executed (Upon Approval)</SectionHeader>
            <ActionPreview approval={approval} />
          </section>

          {/* Steps */}
          {(meta.solution_steps || []).length > 0 && (
            <section>
              <SectionHeader>Execution Steps</SectionHeader>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {meta.solution_steps.map((s, i) => (
                  <div key={i} style={{ display: 'flex', gap: 10, padding: '9px 12px',
                    background: 'var(--surface2)', borderRadius: 8, alignItems: 'flex-start' }}>
                    <span style={{ minWidth: 20, height: 20, borderRadius: 5, background: 'var(--blue-bg)',
                      color: 'var(--blue)', fontSize: 10, fontWeight: 700, display: 'flex',
                      alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>{i + 1}</span>
                    <span style={{ fontSize: 12, color: 'var(--text2)', lineHeight: 1.6 }}>{s}</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Decision info */}
          {approval.decided_at && (
            <section>
              <SectionHeader>Decision</SectionHeader>
              <KV label="Status"     value={approval.status?.toUpperCase()} />
              <KV label="Decided by" value={approval.decided_by} />
              <KV label="Decided at" value={fmtDT(approval.decided_at)} />
              {approval.decision_note && <KV label="Note" value={approval.decision_note} />}
            </section>
          )}

          {/* Aivex mini-chat */}
          <section>
            <SectionHeader>Ask Aivex</SectionHeader>
            <AivexMiniChat approval={approval} />
          </section>
        </div>

        {/* Approve/Reject footer */}
        {isPending && (
          <div style={{ padding: '14px 20px', borderTop: '1px solid var(--border)',
            display: 'flex', gap: 10, alignItems: 'center', flexShrink: 0, background: 'var(--surface)' }}>
            <input placeholder="Optional note…" id={`note-detail-${approval.id}`}
              className="ctrl" style={{ flex: 1, fontSize: 12 }} />
            <button onClick={() => onDecide(approval.id, 'rejected', document.getElementById(`note-detail-${approval.id}`)?.value)}
              disabled={!!deciding[approval.id]}
              style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 8,
                fontSize: 12, fontWeight: 600, cursor: 'pointer', border: '1px solid var(--red)33',
                background: 'var(--red-bg)', color: 'var(--red)' }}>
              <XCircle size={14} />
              {deciding[approval.id] === 'rejected' ? 'Rejecting…' : 'Reject'}
            </button>
            <button onClick={() => onDecide(approval.id, 'approved', document.getElementById(`note-detail-${approval.id}`)?.value)}
              disabled={!!deciding[approval.id]}
              style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 20px', borderRadius: 8,
                fontSize: 12, fontWeight: 700, cursor: 'pointer', border: 'none',
                background: 'var(--green)', color: '#fff' }}>
              <CheckCircle size={14} />
              {deciding[approval.id] === 'approved' ? 'Approving…' : 'Approve'}
            </button>
          </div>
        )}
      </div>
    </>
  );
}
