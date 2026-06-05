"""
Alert Workflow UI — FastAPI routes serving the dashboard.
Reads incident JSON files from output/incidents/ and serves them as a timeline UI.
Mount this onto dev_app.py.
"""
import json
import os
import glob
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()
_INCIDENTS_DIR = os.environ.get("DEV_S3_DIR", "./dev_env/output/incidents")


def _load_incidents(limit=50) -> list:
    files = sorted(
        glob.glob(os.path.join(_INCIDENTS_DIR, "**/*.json"), recursive=True),
        key=os.path.getmtime, reverse=True
    )[:limit]
    incidents = []
    for f in files:
        try:
            with open(f) as fp:
                incidents.append(json.load(fp))
        except Exception:
            pass
    return incidents


@router.get("/ui", response_class=HTMLResponse)
def dashboard():
    return HTMLResponse(content=_HTML)


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


_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AeonX AI Ops Agent — Alert Workflow</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f1117; color: #e2e8f0; min-height: 100vh; }
  header { background: #1a1d2e; border-bottom: 1px solid #2d3748; padding: 16px 24px; display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 18px; font-weight: 600; }
  header .badge { background: #2d6a4f; color: #95d5b2; font-size: 11px; padding: 2px 8px; border-radius: 12px; }
  .layout { display: grid; grid-template-columns: 380px 1fr; height: calc(100vh - 57px); }

  /* Left panel */
  .list-panel { background: #1a1d2e; border-right: 1px solid #2d3748; overflow-y: auto; }
  .list-header { padding: 12px 16px; font-size: 12px; color: #718096; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #2d3748; display: flex; justify-content: space-between; align-items: center; }
  .refresh-btn { background: #2d3748; border: none; color: #a0aec0; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 11px; }
  .refresh-btn:hover { background: #4a5568; }
  .incident-item { padding: 14px 16px; border-bottom: 1px solid #252836; cursor: pointer; transition: background 0.15s; }
  .incident-item:hover { background: #252836; }
  .incident-item.active { background: #1e2a45; border-left: 3px solid #4299e1; }
  .incident-item .host { font-size: 13px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .incident-item .alert-name { font-size: 11px; color: #a0aec0; margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .incident-item .meta { display: flex; gap: 8px; margin-top: 6px; align-items: center; }
  .badge-sev { font-size: 10px; padding: 1px 7px; border-radius: 10px; font-weight: 600; text-transform: uppercase; }
  .sev-critical { background: #742a2a; color: #fc8181; }
  .sev-high { background: #7b341e; color: #f6ad55; }
  .sev-medium { background: #744210; color: #fbd38d; }
  .sev-low { background: #1a365d; color: #90cdf4; }
  .badge-action { font-size: 10px; padding: 1px 7px; border-radius: 10px; }
  .action-actionable { background: #1c4532; color: #68d391; }
  .action-non { background: #2d2d2d; color: #a0aec0; }
  .ts { font-size: 10px; color: #718096; margin-left: auto; }
  .empty { padding: 40px 16px; text-align: center; color: #4a5568; font-size: 13px; }

  /* Right panel */
  .detail-panel { overflow-y: auto; padding: 24px; }
  .no-selection { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: #4a5568; gap: 8px; }
  .no-selection .icon { font-size: 48px; }

  .detail-header { margin-bottom: 24px; }
  .detail-header h2 { font-size: 16px; font-weight: 600; margin-bottom: 4px; }
  .detail-header .sub { font-size: 12px; color: #718096; }
  .detail-header .badges { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }

  .section { background: #1a1d2e; border: 1px solid #2d3748; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
  .section-title { font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: #718096; margin-bottom: 12px; }
  .kv-grid { display: grid; grid-template-columns: 140px 1fr; gap: 6px 12px; font-size: 13px; }
  .kv-key { color: #718096; }
  .kv-val { color: #e2e8f0; word-break: break-all; }

  /* Workflow timeline */
  .timeline { position: relative; padding-left: 24px; }
  .timeline::before { content: ''; position: absolute; left: 7px; top: 8px; bottom: 8px; width: 2px; background: #2d3748; }
  .tl-step { position: relative; margin-bottom: 20px; }
  .tl-dot { position: absolute; left: -20px; top: 3px; width: 14px; height: 14px; border-radius: 50%; border: 2px solid; }
  .tl-dot.done { background: #2d6a4f; border-color: #68d391; }
  .tl-dot.escalated { background: #742a2a; border-color: #fc8181; }
  .tl-dot.pending { background: #1a1d2e; border-color: #4a5568; }
  .tl-dot.ticket { background: #1a365d; border-color: #90cdf4; }
  .tl-dot.email { background: #322659; border-color: #b794f4; }
  .tl-label { font-size: 13px; font-weight: 500; }
  .tl-detail { font-size: 12px; color: #a0aec0; margin-top: 3px; }
  .tl-ts { font-size: 10px; color: #718096; margin-top: 2px; }

  .steps-list { list-style: none; }
  .steps-list li { font-size: 12px; padding: 6px 0; border-bottom: 1px solid #252836; color: #a0aec0; display: flex; gap: 8px; }
  .steps-list li::before { content: '→'; color: #4299e1; flex-shrink: 0; }
  .steps-list li:last-child { border-bottom: none; }

  .summary-box { background: #252836; border-radius: 6px; padding: 12px; font-size: 13px; color: #e2e8f0; line-height: 1.6; }
</style>
</head>
<body>
<header>
  <span>🤖</span>
  <h1>AeonX AI Ops Agent</h1>
  <span class="badge">DEV</span>
  <span style="margin-left:auto;font-size:12px;color:#718096;" id="model-info">Loading...</span>
</header>
<div class="layout">
  <div class="list-panel">
    <div class="list-header">
      <span>Alerts</span>
      <button class="refresh-btn" onclick="loadIncidents()">↺ Refresh</button>
    </div>
    <div id="incident-list"><div class="empty">No alerts yet.<br>Run test_runner.py to generate alerts.</div></div>
  </div>
  <div class="detail-panel" id="detail-panel">
    <div class="no-selection">
      <div class="icon">📋</div>
      <div>Select an alert to view its workflow</div>
    </div>
  </div>
</div>

<script>
const SEV_CLASS = {critical:'sev-critical',high:'sev-high',medium:'sev-medium',low:'sev-low'};
const STEP_LABELS = {
  alert_received: {label:'Alert Received', dot:'done'},
  ai_classified:  {label:'AI Classified', dot:'done'},
  action_decided: {label:'Action Decided', dot:'done'},
  ticket_created: {label:'Ticket Created', dot:'ticket'},
  email_sent:     {label:'Email Sent', dot:'email'},
  auto_remediate: {label:'Auto-Remediation', dot:'done'},
  escalated:      {label:'Escalated to Human', dot:'escalated'},
  resolved:       {label:'Resolved', dot:'done'},
};

let incidents = [];
let selected = null;

async function loadIncidents() {
  const res = await fetch('/api/incidents');
  incidents = await res.json();
  renderList();
  if (selected) renderDetail(incidents.find(i => i.incident_id === selected) || incidents[0]);
}

async function loadHealth() {
  const r = await fetch('/health');
  const d = await r.json();
  document.getElementById('model-info').textContent = `Model: ${d.model || 'unknown'}`;
}

function renderList() {
  const el = document.getElementById('incident-list');
  if (!incidents.length) { el.innerHTML = '<div class="empty">No alerts yet.<br>Run test_runner.py to generate alerts.</div>'; return; }
  el.innerHTML = incidents.map(i => {
    const cls = i.classification || {};
    const ts = new Date(i.alert_triggered_at).toLocaleTimeString();
    const isActive = i.incident_id === selected ? 'active' : '';
    const actionBadge = cls.actionable
      ? `<span class="badge-action action-actionable">✓ Actionable</span>`
      : `<span class="badge-action action-non">Non-actionable</span>`;
    return `<div class="incident-item ${isActive}" onclick="selectIncident('${i.incident_id}')">
      <div class="host">${i.host?.name || 'Unknown host'}</div>
      <div class="alert-name">${i.alert?.name || ''}</div>
      <div class="meta">
        <span class="badge-sev ${SEV_CLASS[cls.severity] || 'sev-medium'}">${cls.severity || '?'}</span>
        ${actionBadge}
        <span class="ts">${ts}</span>
      </div>
    </div>`;
  }).join('');
}

function selectIncident(id) {
  selected = id;
  renderList();
  const inc = incidents.find(i => i.incident_id === id);
  if (inc) renderDetail(inc);
}

function renderDetail(inc) {
  if (!inc) return;
  const cls = inc.classification || {};
  const alert = inc.alert || {};
  const host = inc.host || {};
  const client = inc.client || {};

  const actionable = cls.actionable;
  const actionBadge = actionable
    ? `<span class="badge-action action-actionable" style="font-size:12px;padding:3px 10px;">✓ ACTIONABLE</span>`
    : `<span class="badge-action action-non" style="font-size:12px;padding:3px 10px;">✗ NON-ACTIONABLE</span>`;
  const sevBadge = `<span class="badge-sev ${SEV_CLASS[cls.severity] || 'sev-medium'}" style="font-size:12px;padding:3px 10px;">${(cls.severity||'').toUpperCase()}</span>`;

  // Build workflow steps
  const steps = inc.workflow || [];
  const timelineHTML = steps.map(s => {
    const def = STEP_LABELS[s.step] || {label: s.step, dot: 'done'};
    const dotClass = s.step === 'escalated' ? 'escalated' : (s.step === 'ticket_created' ? 'ticket' : (s.step === 'email_sent' ? 'email' : 'done'));
    return `<div class="tl-step">
      <div class="tl-dot ${dotClass}"></div>
      <div class="tl-label">${def.label}</div>
      <div class="tl-detail">${s.detail || ''}</div>
      <div class="tl-ts">${new Date(s.ts).toLocaleTimeString()}</div>
    </div>`;
  }).join('');

  // Solution steps
  const solutionSteps = (inc.resolution_steps || []).map(s =>
    `<li>${s}</li>`).join('') || '<li style="color:#4a5568">No solution steps defined</li>';

  document.getElementById('detail-panel').innerHTML = `
    <div class="detail-header">
      <h2>${alert.name || 'Unknown Alert'}</h2>
      <div class="sub">${host.name || ''} — ${client.name || ''}</div>
      <div class="badges">${sevBadge}${actionBadge}
        <span class="badge-sev" style="background:#1a1d2e;color:#718096;border:1px solid #2d3748;font-size:12px;padding:3px 10px;">${cls.action || ''}</span>
        ${inc.ticket_id ? `<span class="badge-sev" style="background:#1a365d;color:#90cdf4;font-size:12px;padding:3px 10px;">🎫 #${inc.ticket_id}</span>` : ''}
      </div>
    </div>

    <div class="section">
      <div class="section-title">Workflow Timeline</div>
      <div class="timeline">${timelineHTML || '<div style="color:#4a5568">No timeline data</div>'}</div>
    </div>

    <div class="section">
      <div class="section-title">AI Classification</div>
      <div class="kv-grid">
        <span class="kv-key">Actionable</span><span class="kv-val">${actionable ? '✅ Yes — known solution exists' : '❌ No — no defined solution'}</span>
        <span class="kv-key">Category</span><span class="kv-val">${cls.category || '?'}</span>
        <span class="kv-key">Severity</span><span class="kv-val">${(cls.severity||'').toUpperCase()}</span>
        <span class="kv-key">Confidence</span><span class="kv-val">${((cls.confidence||0)*100).toFixed(0)}%</span>
        <span class="kv-key">Solution ID</span><span class="kv-val">${cls.solution_id || 'None (LLM fallback)'}</span>
      </div>
      <div style="margin-top:12px"><div class="summary-box">${cls.summary || ''}</div></div>
    </div>

    <div class="section">
      <div class="section-title">Alert Details</div>
      <div class="kv-grid">
        <span class="kv-key">Host</span><span class="kv-val">${host.name || ''}</span>
        <span class="kv-key">IP</span><span class="kv-val">${host.ip || ''}</span>
        <span class="kv-key">Client</span><span class="kv-val">${client.name || 'N/A'}</span>
        <span class="kv-key">Alert</span><span class="kv-val">${alert.name || ''}</span>
        <span class="kv-key">Status</span><span class="kv-val">${alert.status || ''}</span>
        <span class="kv-key">Value</span><span class="kv-val">${alert.item_value || 'N/A'}</span>
        <span class="kv-key">Triggered</span><span class="kv-val">${new Date(inc.alert_triggered_at).toLocaleString()}</span>
        <span class="kv-key">Incident ID</span><span class="kv-val" style="font-size:11px;color:#718096">${inc.incident_id}</span>
      </div>
    </div>

    <div class="section">
      <div class="section-title">Resolution Steps ${cls.solution_id ? `(${cls.solution_id})` : '(LLM Suggested)'}</div>
      <ul class="steps-list">${solutionSteps}</ul>
    </div>
  `;
}

loadHealth();
loadIncidents();
setInterval(loadIncidents, 10000); // auto-refresh every 10s
</script>
</body>
</html>"""
