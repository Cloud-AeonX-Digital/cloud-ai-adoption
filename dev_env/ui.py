"""Alert Workflow UI — FastAPI routes + HTML dashboard."""
import json, os, glob
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()
_INCIDENTS_DIR = os.environ.get("DEV_S3_DIR", "./dev_env/output/incidents")


def _load_incidents(limit=100) -> list:
    files = sorted(
        glob.glob(os.path.join(_INCIDENTS_DIR, "**/*.json"), recursive=True),
        key=os.path.getmtime, reverse=True
    )[:limit]
    out = []
    for f in files:
        try:
            with open(f) as fp:
                out.append(json.load(fp))
        except Exception:
            pass
    return out


@router.get("/ui", response_class=HTMLResponse)
def dashboard():
    return HTMLResponse(_HTML)

@router.get("/api/incidents")
def get_incidents():
    return JSONResponse(_load_incidents())

@router.get("/api/incidents/{incident_id}")
def get_incident(incident_id: str):
    files = glob.glob(os.path.join(_INCIDENTS_DIR, f"**/{incident_id}.json"), recursive=True)
    if not files:
        return JSONResponse({"error": "not found"}, status_code=404)
    with open(files[0]) as f:
        return JSONResponse(json.load(f))


_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AeonX AI Ops — Alert Monitor</title>
<style>
:root {
  --bg: #0d0f1a; --surface: #141624; --surface2: #1c1f35;
  --border: #252840; --text: #e2e8f0; --muted: #6b7280;
  --blue: #3b82f6; --green: #10b981; --yellow: #f59e0b;
  --orange: #f97316; --red: #ef4444; --purple: #8b5cf6;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Inter', -apple-system, sans-serif; background: var(--bg); color: var(--text); height: 100vh; overflow: hidden; display: flex; flex-direction: column; }

/* Top bar */
.topbar { height: 52px; background: var(--surface); border-bottom: 1px solid var(--border); display: flex; align-items: center; padding: 0 20px; gap: 16px; flex-shrink: 0; }
.topbar .logo { font-weight: 700; font-size: 15px; display: flex; align-items: center; gap: 8px; }
.topbar .logo span { color: var(--blue); }
.topbar .stats { display: flex; gap: 20px; margin-left: auto; }
.stat { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--muted); }
.stat strong { color: var(--text); font-size: 14px; }
.dot-live { width: 7px; height: 7px; background: var(--green); border-radius: 50%; animation: pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.model-tag { background: var(--surface2); border: 1px solid var(--border); border-radius: 20px; padding: 3px 10px; font-size: 11px; color: var(--muted); }

/* Layout */
.main { display: flex; flex: 1; overflow: hidden; }

/* Left sidebar */
.sidebar { width: 360px; flex-shrink: 0; border-right: 1px solid var(--border); display: flex; flex-direction: column; background: var(--surface); }
.sidebar-header { padding: 14px 16px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 10px; }
.sidebar-header h2 { font-size: 13px; font-weight: 600; flex: 1; }
.btn-refresh { background: var(--surface2); border: 1px solid var(--border); color: var(--muted); padding: 5px 12px; border-radius: 6px; cursor: pointer; font-size: 12px; transition: all .2s; }
.btn-refresh:hover { color: var(--text); border-color: var(--blue); }
.search-box { padding: 10px 16px; border-bottom: 1px solid var(--border); }
.search-box input { width: 100%; background: var(--surface2); border: 1px solid var(--border); border-radius: 6px; padding: 7px 12px; color: var(--text); font-size: 13px; outline: none; }
.search-box input:focus { border-color: var(--blue); }
.incident-list { flex: 1; overflow-y: auto; }
.incident-list::-webkit-scrollbar { width: 4px; }
.incident-list::-webkit-scrollbar-track { background: transparent; }
.incident-list::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

/* Incident card */
.inc-card { padding: 14px 16px; border-bottom: 1px solid var(--border); cursor: pointer; transition: background .15s; position: relative; }
.inc-card:hover { background: var(--surface2); }
.inc-card.active { background: #1a2244; }
.inc-card.active::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--blue); border-radius: 0 2px 2px 0; }
.inc-card .row1 { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 5px; }
.inc-card .host { font-size: 13px; font-weight: 500; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.inc-card .time { font-size: 10px; color: var(--muted); white-space: nowrap; }
.inc-card .alert-name { font-size: 11px; color: var(--muted); margin-bottom: 7px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.inc-card .row3 { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }

/* Badges */
.badge { display: inline-flex; align-items: center; gap: 4px; font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 20px; text-transform: uppercase; letter-spacing: .03em; }
.badge-critical { background: #2d0f0f; color: #ef4444; border: 1px solid #7f1d1d; }
.badge-high     { background: #2d1b0f; color: #f97316; border: 1px solid #7c2d12; }
.badge-medium   { background: #2d230f; color: #f59e0b; border: 1px solid #78350f; }
.badge-low      { background: #0f1f2d; color: #60a5fa; border: 1px solid #1e3a5f; }
.badge-act  { background: #0d2218; color: #34d399; border: 1px solid #065f46; }
.badge-noact { background: #1a1a1a; color: #6b7280; border: 1px solid #374151; }
.badge-dedup { background: #1a1a2e; color: #8b5cf6; border: 1px solid #4c1d95; }
.badge-action-auto { background: #0d2218; color: #34d399; }
.badge-action-ticket { background: #0f172a; color: #60a5fa; }
.badge-action-escalate { background: #2d0f0f; color: #f87171; }

/* Right detail */
.detail { flex: 1; overflow-y: auto; background: var(--bg); }
.detail::-webkit-scrollbar { width: 4px; }
.detail::-webkit-scrollbar-thumb { background: var(--border); }
.empty-state { height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; color: var(--muted); }
.empty-state svg { opacity: .3; }
.empty-state p { font-size: 14px; }

.detail-inner { padding: 24px; max-width: 860px; }

/* Detail header */
.detail-head { margin-bottom: 24px; }
.detail-head .alert-title { font-size: 18px; font-weight: 700; margin-bottom: 6px; line-height: 1.3; }
.detail-head .meta-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }
.detail-head .host-info { font-size: 13px; color: var(--muted); }
.detail-head .badges { display: flex; gap: 8px; flex-wrap: wrap; }

/* Cards grid */
.cards-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }
.card-title { font-size: 11px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin-bottom: 12px; font-weight: 600; }
.kv { display: flex; flex-direction: column; gap: 8px; }
.kv-row { display: flex; gap: 8px; font-size: 12px; }
.kv-key { color: var(--muted); min-width: 110px; flex-shrink: 0; }
.kv-val { color: var(--text); word-break: break-all; }

/* Workflow timeline */
.timeline-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 20px; margin-bottom: 20px; }
.timeline-card .card-title { margin-bottom: 20px; }
.tl { position: relative; }
.tl-line { position: absolute; left: 15px; top: 20px; bottom: 20px; width: 2px; background: var(--border); }
.tl-step { display: flex; gap: 16px; align-items: flex-start; padding: 0 0 24px 0; position: relative; }
.tl-step:last-child { padding-bottom: 0; }
.tl-icon { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; flex-shrink: 0; position: relative; z-index: 1; border: 2px solid; }
.tl-icon.green  { background: #0d2218; border-color: #065f46; }
.tl-icon.blue   { background: #0f172a; border-color: #1e3a5f; }
.tl-icon.yellow { background: #2d230f; border-color: #78350f; }
.tl-icon.red    { background: #2d0f0f; border-color: #7f1d1d; }
.tl-icon.purple { background: #1a1028; border-color: #4c1d95; }
.tl-icon.gray   { background: var(--surface2); border-color: var(--border); }
.tl-body { flex: 1; padding-top: 4px; }
.tl-label { font-size: 13px; font-weight: 600; }
.tl-detail { font-size: 12px; color: var(--muted); margin-top: 3px; line-height: 1.5; }
.tl-ts { font-size: 10px; color: var(--muted); margin-top: 4px; }

/* Steps list */
.steps-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin-bottom: 20px; }
.step-item { display: flex; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--border); font-size: 12px; }
.step-item:last-child { border-bottom: none; padding-bottom: 0; }
.step-num { width: 20px; height: 20px; background: var(--surface2); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 10px; color: var(--blue); font-weight: 700; flex-shrink: 0; }
.step-text { color: var(--muted); line-height: 1.5; }

/* Summary box */
.summary-box { background: var(--surface2); border-left: 3px solid var(--blue); border-radius: 0 6px 6px 0; padding: 12px 14px; font-size: 13px; color: var(--text); line-height: 1.6; margin-top: 12px; }

/* Stats bar */
.stats-bar { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
.stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 14px; text-align: center; }
.stat-card .num { font-size: 22px; font-weight: 700; }
.stat-card .lbl { font-size: 11px; color: var(--muted); margin-top: 4px; text-transform: uppercase; letter-spacing: .05em; }

.no-incidents { padding: 40px; text-align: center; color: var(--muted); font-size: 13px; }
</style>
</head>
<body>
<div class="topbar">
  <div class="logo">🤖 <span>AeonX</span> AI Ops Agent</div>
  <div class="dot-live" title="Live"></div>
  <div class="model-tag" id="model-tag">Loading...</div>
  <div class="stats" id="topbar-stats">
    <div class="stat"><strong id="stat-total">0</strong> Total</div>
    <div class="stat"><strong id="stat-action" style="color:var(--green)">0</strong> Actionable</div>
    <div class="stat"><strong id="stat-escalate" style="color:var(--red)">0</strong> Escalated</div>
  </div>
</div>
<div class="main">
  <div class="sidebar">
    <div class="sidebar-header">
      <h2>Alerts <span id="count-badge" style="color:var(--muted);font-weight:400"></span></h2>
      <button class="btn-refresh" onclick="loadIncidents()">↺ Refresh</button>
    </div>
    <div class="search-box">
      <input type="text" id="search" placeholder="Search host, alert..." oninput="filterList()">
    </div>
    <div class="incident-list" id="incident-list">
      <div class="no-incidents">Loading...</div>
    </div>
  </div>
  <div class="detail" id="detail">
    <div class="empty-state">
      <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>
      <p>Select an alert to view its full workflow</p>
    </div>
  </div>
</div>

<script>
let incidents = [], selected = null;

const SEV = {critical:'badge-critical',high:'badge-high',medium:'badge-medium',low:'badge-low'};
const SEV_ICON = {critical:'🔴',high:'🟠',medium:'🟡',low:'🔵'};
const ACTION_CLASS = {'auto-remediate':'badge-action-auto','create-ticket':'badge-action-ticket','escalate':'badge-action-escalate','deduplicated':'badge-dedup'};
const ACTION_LABEL = {'auto-remediate':'Auto-Remediate','create-ticket':'Ticket','escalate':'Escalate','deduplicated':'Dedup'};

const STEP_DEF = {
  alert_received: {icon:'🔔', color:'green',  label:'Alert Received'},
  ai_classified:  {icon:'🤖', color:'blue',   label:'AI Classified'},
  action_decided: {icon:'⚡', color:'yellow', label:'Action Decided'},
  ticket_created: {icon:'🎫', color:'blue',   label:'Ticket Created'},
  email_sent:     {icon:'📧', color:'purple', label:'Email Sent'},
  escalated:      {icon:'🚨', color:'red',    label:'Escalated to Human'},
  resolved:       {icon:'✅', color:'green',  label:'Resolved'},
};

function fmtTime(ts) {
  const d = new Date(ts);
  return d.toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
}
function fmtDateTime(ts) {
  return new Date(ts).toLocaleString('en-IN',{dateStyle:'medium',timeStyle:'medium'});
}

async function loadIncidents() {
  const r = await fetch('/api/incidents').catch(()=>null);
  if (!r) return;
  incidents = await r.json();
  updateStats();
  renderList();
  if (selected) {
    const inc = incidents.find(i=>i.incident_id===selected);
    if (inc) renderDetail(inc);
  }
}

async function loadHealth() {
  const r = await fetch('/health').catch(()=>null);
  if (!r) return;
  const d = await r.json();
  document.getElementById('model-tag').textContent = d.model || 'unknown';
}

function updateStats() {
  const total = incidents.filter(i=>i.classification?.action!=='deduplicated').length;
  const act = incidents.filter(i=>i.classification?.actionable).length;
  const esc = incidents.filter(i=>i.classification?.action==='escalate').length;
  document.getElementById('stat-total').textContent = total;
  document.getElementById('stat-action').textContent = act;
  document.getElementById('stat-escalate').textContent = esc;
  document.getElementById('count-badge').textContent = `(${incidents.length})`;
}

function filterList() {
  const q = document.getElementById('search').value.toLowerCase();
  const filtered = q ? incidents.filter(i=>
    (i.host?.name||'').toLowerCase().includes(q) ||
    (i.alert?.name||'').toLowerCase().includes(q) ||
    (i.client?.name||'').toLowerCase().includes(q)
  ) : incidents;
  renderList(filtered);
}

function renderList(list) {
  list = list || incidents;
  const el = document.getElementById('incident-list');
  if (!list.length) { el.innerHTML = '<div class="no-incidents">No alerts yet.<br>Run test_runner.py to generate alerts.</div>'; return; }
  el.innerHTML = list.map(i => {
    const cls = i.classification || {};
    const action = cls.action || '';
    const isDedup = action === 'deduplicated';
    const actBadge = cls.actionable
      ? `<span class="badge badge-act">✓ Actionable</span>`
      : `<span class="badge badge-noact">Non-actionable</span>`;
    const actionBadge = `<span class="badge ${ACTION_CLASS[action]||''}">${ACTION_LABEL[action]||action}</span>`;
    const active = i.incident_id === selected ? 'active' : '';
    return `<div class="inc-card ${active}" onclick="selectIncident('${i.incident_id}')">
      <div class="row1">
        <div class="host">${i.host?.name||'Unknown'}</div>
        <div class="time">${fmtTime(i.alert_triggered_at)}</div>
      </div>
      <div class="alert-name">${i.alert?.name||''}</div>
      <div class="row3">
        <span class="badge ${SEV[cls.severity]||'badge-medium'}">${SEV_ICON[cls.severity]||''} ${cls.severity||'?'}</span>
        ${isDedup ? '<span class="badge badge-dedup">🔁 Dedup</span>' : actBadge}
        ${!isDedup ? actionBadge : ''}
      </div>
    </div>`;
  }).join('');
}

function selectIncident(id) {
  selected = id;
  renderList();
  const inc = incidents.find(i=>i.incident_id===id);
  if (inc) renderDetail(inc);
}

function renderDetail(inc) {
  const cls = inc.classification || {};
  const alert = inc.alert || {};
  const host = inc.host || {};
  const client = inc.client || {};
  const steps = inc.workflow || [];
  const solSteps = inc.resolution_steps || [];
  const isDedup = cls.action === 'deduplicated';

  const sevBadge = `<span class="badge ${SEV[cls.severity]||'badge-medium'}" style="font-size:12px;padding:4px 12px">${SEV_ICON[cls.severity]} ${(cls.severity||'?').toUpperCase()}</span>`;
  const actBadge = isDedup ? `<span class="badge badge-dedup" style="font-size:12px;padding:4px 12px">🔁 Deduplicated</span>` :
    cls.actionable
      ? `<span class="badge badge-act" style="font-size:12px;padding:4px 12px">✓ ACTIONABLE</span>`
      : `<span class="badge badge-noact" style="font-size:12px;padding:4px 12px">✗ NON-ACTIONABLE</span>`;
  const actionBadge = `<span class="badge ${ACTION_CLASS[cls.action]||''}" style="font-size:12px;padding:4px 12px">${ACTION_LABEL[cls.action]||cls.action}</span>`;
  const ticketBadge = inc.ticket_id ? `<span class="badge badge-action-ticket" style="font-size:12px;padding:4px 12px">🎫 #${inc.ticket_id}</span>` : '';

  // Timeline
  const tlHTML = steps.map(s => {
    const def = STEP_DEF[s.step] || {icon:'•', color:'gray', label:s.step};
    return `<div class="tl-step">
      <div class="tl-icon ${def.color}">${def.icon}</div>
      <div class="tl-body">
        <div class="tl-label">${def.label}</div>
        <div class="tl-detail">${s.detail||''}</div>
        <div class="tl-ts">${fmtDateTime(s.ts)}</div>
      </div>
    </div>`;
  }).join('');

  // Resolution steps
  const stepsHTML = solSteps.length
    ? solSteps.map((s,i)=>`<div class="step-item"><div class="step-num">${i+1}</div><div class="step-text">${s}</div></div>`).join('')
    : '<div class="step-item"><div class="step-text" style="color:var(--muted)">No defined solution steps — LLM classified</div></div>';

  document.getElementById('detail').innerHTML = `
  <div class="detail-inner">
    <div class="detail-head">
      <div class="alert-title">${alert.name||'Unknown Alert'}</div>
      <div class="meta-row">
        <div class="host-info">🖥 ${host.name||'?'} &nbsp;·&nbsp; ${host.ip||''} &nbsp;·&nbsp; 👤 ${client.name||'N/A'}</div>
      </div>
      <div class="badges">${sevBadge}${actBadge}${actionBadge}${ticketBadge}</div>
    </div>

    <div class="timeline-card">
      <div class="card-title">Workflow Timeline</div>
      <div class="tl">
        <div class="tl-line"></div>
        ${tlHTML || '<div style="color:var(--muted);font-size:13px">No timeline data</div>'}
      </div>
    </div>

    <div class="cards-grid">
      <div class="card">
        <div class="card-title">AI Classification</div>
        <div class="kv">
          <div class="kv-row"><span class="kv-key">Actionable</span><span class="kv-val">${cls.actionable ? '✅ Yes — known solution' : '❌ No — no defined solution'}</span></div>
          <div class="kv-row"><span class="kv-key">Category</span><span class="kv-val">${cls.category||'?'}</span></div>
          <div class="kv-row"><span class="kv-key">Severity</span><span class="kv-val">${(cls.severity||'').toUpperCase()}</span></div>
          <div class="kv-row"><span class="kv-key">Action</span><span class="kv-val">${cls.action||'?'}</span></div>
          <div class="kv-row"><span class="kv-key">Confidence</span><span class="kv-val">${Math.round((cls.confidence||0)*100)}%</span></div>
          <div class="kv-row"><span class="kv-key">Solution ID</span><span class="kv-val">${cls.solution_id||'None (LLM)'}</span></div>
        </div>
        <div class="summary-box">${cls.summary||''}</div>
      </div>
      <div class="card">
        <div class="card-title">Alert Details</div>
        <div class="kv">
          <div class="kv-row"><span class="kv-key">Host</span><span class="kv-val">${host.name||'?'}</span></div>
          <div class="kv-row"><span class="kv-key">IP Address</span><span class="kv-val">${host.ip||'N/A'}</span></div>
          <div class="kv-row"><span class="kv-key">Client</span><span class="kv-val">${client.name||'N/A'}</span></div>
          <div class="kv-row"><span class="kv-key">AWS Account</span><span class="kv-val">${client.aws_account||'N/A'}</span></div>
          <div class="kv-row"><span class="kv-key">Alert Status</span><span class="kv-val">${alert.status||'?'}</span></div>
          <div class="kv-row"><span class="kv-key">Metric Value</span><span class="kv-val">${alert.item_value||'N/A'}</span></div>
          <div class="kv-row"><span class="kv-key">Triggered</span><span class="kv-val">${fmtDateTime(inc.alert_triggered_at)}</span></div>
          <div class="kv-row"><span class="kv-key">Incident ID</span><span class="kv-val" style="font-size:10px;color:var(--muted)">${inc.incident_id}</span></div>
        </div>
      </div>
    </div>

    <div class="steps-card">
      <div class="card-title">Resolution Steps ${cls.solution_id ? `· <span style="color:var(--blue)">${cls.solution_id}</span>` : '· LLM Suggested'}</div>
      ${stepsHTML}
    </div>
  </div>`;
}

loadHealth();
loadIncidents();
setInterval(loadIncidents, 8000);
</script>
</body>
</html>"""
