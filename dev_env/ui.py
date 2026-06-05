"""Alert Workflow UI — FastAPI routes + full dashboard HTML."""
import json, os, glob
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()
_INCIDENTS_DIR = os.environ.get("DEV_S3_DIR", "./dev_env/output/incidents")


def _load_incidents(limit=200) -> list:
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
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>AeonX AI Ops — Monitor</title>
<style>
/* ── Theme Variables ── */
[data-theme="dark"] {
  --bg:#0b0d1a; --bg2:#111327; --surface:#151829; --surface2:#1c2040;
  --border:#232647; --border2:#2d3260;
  --text:#e8eaf6; --text2:#9ca3c8; --text3:#6b7294;
  --blue:#6c8cff; --blue-dim:#1a2456; --blue-glow:rgba(108,140,255,.15);
  --green:#34d399; --green-dim:#0a2e22;
  --yellow:#fbbf24; --yellow-dim:#2d2208;
  --orange:#f97316; --orange-dim:#2d1a08;
  --red:#f87171; --red-dim:#2d0f0f;
  --purple:#a78bfa; --purple-dim:#1e1640;
  --card-shadow:0 4px 24px rgba(0,0,0,.4);
  --nav-bg:#0f1226;
}
[data-theme="light"] {
  --bg:#f0f2ff; --bg2:#e8eaf6; --surface:#ffffff; --surface2:#f4f5ff;
  --border:#dde0ff; --border2:#c5caff;
  --text:#1a1d3a; --text2:#4a4f7a; --text3:#8b90b8;
  --blue:#4361ee; --blue-dim:#dde3ff; --blue-glow:rgba(67,97,238,.08);
  --green:#059669; --green-dim:#d1fae5;
  --yellow:#d97706; --yellow-dim:#fef3c7;
  --orange:#ea580c; --orange-dim:#ffedd5;
  --red:#dc2626; --red-dim:#fee2e2;
  --purple:#7c3aed; --purple-dim:#ede9fe;
  --card-shadow:0 2px 16px rgba(67,97,238,.08);
  --nav-bg:#ffffff;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--text);height:100vh;display:flex;flex-direction:column;overflow:hidden;transition:background .2s,color .2s}
a{text-decoration:none;color:inherit}

/* ── Nav ── */
nav{height:56px;background:var(--nav-bg);border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 24px;gap:0;flex-shrink:0;z-index:100;box-shadow:var(--card-shadow)}
.nav-logo{display:flex;align-items:center;gap:10px;font-weight:700;font-size:15px;margin-right:32px}
.nav-logo .icon{width:32px;height:32px;background:linear-gradient(135deg,var(--blue),var(--purple));border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:16px}
.nav-logo .name{color:var(--text)}
.nav-logo .tag{color:var(--blue);font-weight:800}
.nav-tabs{display:flex;gap:4px;flex:1}
.nav-tab{padding:7px 16px;border-radius:8px;font-size:13px;font-weight:500;color:var(--text2);cursor:pointer;transition:all .15s;border:1px solid transparent}
.nav-tab:hover{background:var(--surface2);color:var(--text)}
.nav-tab.active{background:var(--blue-dim);color:var(--blue);border-color:var(--border2)}
.nav-right{display:flex;align-items:center;gap:12px}
.model-pill{background:var(--surface2);border:1px solid var(--border);border-radius:20px;padding:4px 12px;font-size:11px;color:var(--text3);display:flex;align-items:center;gap:6px}
.live-dot{width:7px;height:7px;background:var(--green);border-radius:50%;animation:blink 2s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
.theme-btn{background:var(--surface2);border:1px solid var(--border);color:var(--text2);padding:6px 10px;border-radius:8px;cursor:pointer;font-size:16px;transition:all .15s}
.theme-btn:hover{border-color:var(--blue);color:var(--blue)}

/* ── Pages ── */
.page{display:none;flex:1;overflow:hidden}
.page.active{display:flex;flex-direction:column}

/* ── Dashboard Page ── */
.dash-body{flex:1;overflow-y:auto;padding:24px;display:flex;flex-direction:column;gap:20px}
.dash-body::-webkit-scrollbar{width:5px}
.dash-body::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}

/* Stats row */
.stats-row{display:grid;grid-template-columns:repeat(5,1fr);gap:14px}
.stat-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px;display:flex;flex-direction:column;gap:8px;box-shadow:var(--card-shadow);transition:transform .15s,box-shadow .15s;cursor:default}
.stat-card:hover{transform:translateY(-2px);box-shadow:0 8px 32px rgba(0,0,0,.3)}
.stat-card .sc-icon{width:38px;height:38px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px}
.stat-card .sc-val{font-size:26px;font-weight:700;letter-spacing:-.5px}
.stat-card .sc-lbl{font-size:12px;color:var(--text2)}
.stat-card .sc-sub{font-size:11px;color:var(--text3);margin-top:2px}

/* Middle row */
.middle-row{display:grid;grid-template-columns:1fr 380px;gap:16px}

/* Chart card */
.chart-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px;box-shadow:var(--card-shadow)}
.card-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
.card-title{font-size:14px;font-weight:600}
.card-sub{font-size:11px;color:var(--text3)}
.chart-area{height:180px;position:relative;display:flex;align-items:flex-end;gap:4px;padding-top:20px}
.chart-bar-group{flex:1;display:flex;gap:2px;align-items:flex-end;height:100%}
.chart-bar{border-radius:4px 4px 0 0;min-width:10px;transition:opacity .2s;cursor:pointer;position:relative}
.chart-bar:hover{opacity:.8}
.chart-bar .bar-tip{position:absolute;top:-24px;left:50%;transform:translateX(-50%);background:var(--surface2);border:1px solid var(--border);border-radius:4px;padding:2px 6px;font-size:10px;white-space:nowrap;opacity:0;transition:opacity .15s;pointer-events:none}
.chart-bar:hover .bar-tip{opacity:1}
.chart-labels{display:flex;gap:4px;margin-top:6px}
.chart-label{flex:1;text-align:center;font-size:9px;color:var(--text3)}
.chart-legend{display:flex;gap:14px;margin-top:10px}
.legend-item{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--text2)}
.legend-dot{width:8px;height:8px;border-radius:50%}

/* Active alerts */
.active-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px;box-shadow:var(--card-shadow);display:flex;flex-direction:column}
.alert-feed{flex:1;overflow-y:auto;margin-top:8px;display:flex;flex-direction:column;gap:8px;max-height:220px}
.alert-feed::-webkit-scrollbar{width:3px}
.alert-feed::-webkit-scrollbar-thumb{background:var(--border)}
.alert-item{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:10px 12px;cursor:pointer;transition:all .15s;display:flex;gap:10px;align-items:flex-start}
.alert-item:hover{border-color:var(--blue);transform:translateX(2px)}
.alert-item .sev-strip{width:3px;border-radius:2px;flex-shrink:0;align-self:stretch}
.alert-item .ai-body{flex:1;min-width:0}
.alert-item .ai-host{font-size:12px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.alert-item .ai-name{font-size:11px;color:var(--text2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:1px}
.alert-item .ai-meta{display:flex;gap:6px;margin-top:5px;align-items:center}
.alert-item .ai-time{font-size:10px;color:var(--text3);margin-left:auto}

/* Bottom row */
.bottom-row{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.donut-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px;box-shadow:var(--card-shadow)}
.donut-wrap{display:flex;align-items:center;gap:24px;margin-top:8px}
.donut-svg{flex-shrink:0}
.donut-legend{display:flex;flex-direction:column;gap:8px;flex:1}
.dl-item{display:flex;align-items:center;gap:8px;font-size:12px}
.dl-dot{width:10px;height:10px;border-radius:3px;flex-shrink:0}
.dl-label{color:var(--text2);flex:1}
.dl-val{font-weight:600}

/* ── Detail Drawer (overlays dashboard) ── */
.drawer-overlay{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:200;display:none;backdrop-filter:blur(4px)}
.drawer-overlay.open{display:block}
.drawer{position:fixed;right:0;top:0;bottom:0;width:580px;background:var(--surface);border-left:1px solid var(--border);z-index:201;transform:translateX(100%);transition:transform .25s cubic-bezier(.4,0,.2,1);overflow-y:auto;display:flex;flex-direction:column}
.drawer.open{transform:translateX(0)}
.drawer-header{padding:20px 24px;border-bottom:1px solid var(--border);display:flex;align-items:flex-start;gap:12px;flex-shrink:0;position:sticky;top:0;background:var(--surface);z-index:1}
.drawer-close{width:32px;height:32px;border-radius:8px;background:var(--surface2);border:1px solid var(--border);color:var(--text2);cursor:pointer;font-size:18px;display:flex;align-items:center;justify-content:center;margin-left:auto;flex-shrink:0;transition:all .15s}
.drawer-close:hover{border-color:var(--red);color:var(--red)}
.drawer-body{padding:20px 24px;flex:1}

/* ── Alerts Page ── */
.alerts-body{flex:1;display:flex;flex-direction:column;overflow:hidden;padding:20px}
.filter-bar{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 16px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:16px;box-shadow:var(--card-shadow)}
.filter-bar select,.filter-bar input{background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:7px 12px;border-radius:8px;font-size:12px;outline:none;transition:border-color .15s;-webkit-appearance:none}
.filter-bar select:focus,.filter-bar input:focus{border-color:var(--blue)}
.filter-bar .search-input{flex:1;min-width:160px}
.btn-clear{background:transparent;border:1px solid var(--border);color:var(--text2);padding:7px 14px;border-radius:8px;cursor:pointer;font-size:12px;transition:all .15s}
.btn-clear:hover{border-color:var(--red);color:var(--red)}
.filter-count{font-size:11px;color:var(--text3);margin-left:auto}

.table-wrap{flex:1;overflow:auto;background:var(--surface);border:1px solid var(--border);border-radius:10px;box-shadow:var(--card-shadow)}
.table-wrap::-webkit-scrollbar{width:5px;height:5px}
.table-wrap::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
table{width:100%;border-collapse:collapse;font-size:12px}
thead{position:sticky;top:0;z-index:1}
th{background:var(--surface2);padding:11px 14px;text-align:left;font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid var(--border);white-space:nowrap;cursor:pointer;user-select:none}
th:hover{color:var(--text)}
th .sort-icon{margin-left:4px;opacity:.4}
td{padding:11px 14px;border-bottom:1px solid var(--border);vertical-align:middle;max-width:220px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
tr:last-child td{border-bottom:none}
tr:hover td{background:var(--surface2)}
tr{cursor:pointer;transition:background .1s}
.td-host{font-weight:500}
.td-alert{color:var(--text2)}
.no-data{padding:60px;text-align:center;color:var(--text3);font-size:13px}

/* ── Shared badge styles ── */
.chip{display:inline-flex;align-items:center;gap:4px;font-size:10px;font-weight:700;padding:2px 9px;border-radius:20px;text-transform:uppercase;letter-spacing:.04em;white-space:nowrap}
.chip-critical{background:var(--red-dim);color:var(--red)}
.chip-high{background:var(--orange-dim);color:var(--orange)}
.chip-medium{background:var(--yellow-dim);color:var(--yellow)}
.chip-low{background:var(--blue-dim);color:var(--blue)}
.chip-act{background:var(--green-dim);color:var(--green)}
.chip-noact{background:var(--surface2);color:var(--text3);border:1px solid var(--border)}
.chip-auto{background:var(--green-dim);color:var(--green)}
.chip-ticket{background:var(--blue-dim);color:var(--blue)}
.chip-escalate{background:var(--red-dim);color:var(--red)}
.chip-dedup{background:var(--purple-dim);color:var(--purple)}

/* ── Drawer detail content ── */
.dw-title{font-size:16px;font-weight:700;line-height:1.3;flex:1}
.dw-meta{font-size:12px;color:var(--text2);margin-top:4px}
.dw-chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
.section{margin-bottom:20px}
.section-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--text3);margin-bottom:10px;display:flex;align-items:center;gap:8px}
.section-title::after{content:'';flex:1;height:1px;background:var(--border)}
.kv-grid{display:grid;grid-template-columns:130px 1fr;gap:6px 12px;font-size:12px}
.kv-key{color:var(--text2)}
.kv-val{color:var(--text);word-break:break-all}

/* Timeline */
.tl{position:relative;padding-left:20px}
.tl::before{content:'';position:absolute;left:11px;top:16px;bottom:16px;width:2px;background:var(--border);border-radius:1px}
.tl-item{position:relative;display:flex;gap:12px;padding-bottom:20px}
.tl-item:last-child{padding-bottom:0}
.tl-dot{width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0;position:relative;z-index:1;border:2px solid}
.tl-dot.c-green{background:var(--green-dim);border-color:var(--green)}
.tl-dot.c-blue{background:var(--blue-dim);border-color:var(--blue)}
.tl-dot.c-yellow{background:var(--yellow-dim);border-color:var(--yellow)}
.tl-dot.c-red{background:var(--red-dim);border-color:var(--red)}
.tl-dot.c-purple{background:var(--purple-dim);border-color:var(--purple)}
.tl-dot.c-gray{background:var(--surface2);border-color:var(--border)}
.tl-body{padding-top:2px;flex:1}
.tl-label{font-size:13px;font-weight:600}
.tl-detail{font-size:11px;color:var(--text2);margin-top:2px;line-height:1.5}
.tl-ts{font-size:10px;color:var(--text3);margin-top:3px}

.step-list{display:flex;flex-direction:column;gap:6px}
.step-row{display:flex;gap:10px;font-size:12px;padding:8px;background:var(--surface2);border-radius:8px;align-items:flex-start}
.step-num{width:22px;height:22px;background:var(--blue-dim);border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:var(--blue);flex-shrink:0}
.step-txt{color:var(--text2);line-height:1.5}
.summary-strip{background:var(--blue-glow);border:1px solid var(--border2);border-left:3px solid var(--blue);border-radius:0 8px 8px 0;padding:12px 14px;font-size:13px;line-height:1.6;margin-top:8px}
</style>
</head>
<body>

<!-- NAV -->
<nav>
  <div class="nav-logo"><div class="icon">🤖</div><div class="name"><span class="tag">AeonX</span> AI Ops</div></div>
  <div class="nav-tabs">
    <div class="nav-tab active" onclick="showPage('dash')">📊 Dashboard</div>
    <div class="nav-tab" onclick="showPage('alerts')">📋 All Alerts</div>
  </div>
  <div class="nav-right">
    <div class="model-pill"><div class="live-dot"></div><span id="model-label">Loading...</span></div>
    <button class="theme-btn" onclick="toggleTheme()" title="Toggle theme">🌙</button>
  </div>
</nav>

<!-- DRAWER OVERLAY -->
<div class="drawer-overlay" id="overlay" onclick="closeDrawer()"></div>
<div class="drawer" id="drawer">
  <div class="drawer-header">
    <div id="dw-head-content"></div>
    <button class="drawer-close" onclick="closeDrawer()">✕</button>
  </div>
  <div class="drawer-body" id="dw-body"></div>
</div>

<!-- PAGE: DASHBOARD -->
<div class="page active" id="page-dash">
  <div class="dash-body">
    <!-- Stats -->
    <div class="stats-row" id="stats-row">
      <div class="stat-card"><div class="sc-icon" style="background:var(--blue-dim)">📡</div><div class="sc-val" id="s-total">—</div><div class="sc-lbl">Total Alerts</div></div>
      <div class="stat-card"><div class="sc-icon" style="background:var(--green-dim)">⚡</div><div class="sc-val" id="s-action" style="color:var(--green)">—</div><div class="sc-lbl">Actionable</div></div>
      <div class="stat-card"><div class="sc-icon" style="background:var(--red-dim)">🚨</div><div class="sc-val" id="s-escalate" style="color:var(--red)">—</div><div class="sc-lbl">Escalated</div></div>
      <div class="stat-card"><div class="sc-icon" style="background:var(--yellow-dim)">🎫</div><div class="sc-val" id="s-ticket" style="color:var(--yellow)">—</div><div class="sc-lbl">Tickets Created</div></div>
      <div class="stat-card"><div class="sc-icon" style="background:var(--purple-dim)">🔁</div><div class="sc-val" id="s-dedup" style="color:var(--purple)">—</div><div class="sc-lbl">Deduplicated</div></div>
    </div>

    <!-- Middle -->
    <div class="middle-row">
      <div class="chart-card">
        <div class="card-header">
          <div><div class="card-title">Alert Activity</div><div class="card-sub">Last 12 hours — by severity</div></div>
        </div>
        <div class="chart-area" id="chart-bars"></div>
        <div class="chart-labels" id="chart-labels"></div>
        <div class="chart-legend">
          <div class="legend-item"><div class="legend-dot" style="background:var(--red)"></div>Critical</div>
          <div class="legend-item"><div class="legend-dot" style="background:var(--orange)"></div>High</div>
          <div class="legend-item"><div class="legend-dot" style="background:var(--yellow)"></div>Medium</div>
          <div class="legend-item"><div class="legend-dot" style="background:var(--blue)"></div>Low</div>
        </div>
      </div>

      <div class="active-card">
        <div class="card-header"><div class="card-title">Recent Alerts</div><div class="card-sub" id="active-count"></div></div>
        <div class="alert-feed" id="alert-feed"></div>
      </div>
    </div>

    <!-- Bottom -->
    <div class="bottom-row">
      <div class="donut-card">
        <div class="card-header"><div class="card-title">By Category</div></div>
        <div class="donut-wrap">
          <svg class="donut-svg" width="100" height="100" viewBox="0 0 100 100" id="donut-cat"></svg>
          <div class="donut-legend" id="donut-cat-legend"></div>
        </div>
      </div>
      <div class="donut-card">
        <div class="card-header"><div class="card-title">By Action</div></div>
        <div class="donut-wrap">
          <svg class="donut-svg" width="100" height="100" viewBox="0 0 100 100" id="donut-act"></svg>
          <div class="donut-legend" id="donut-act-legend"></div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- PAGE: ALL ALERTS -->
<div class="page" id="page-alerts">
  <div class="alerts-body">
    <div class="filter-bar">
      <input class="search-input" type="text" placeholder="🔍  Search host, alert, client..." id="f-search" oninput="applyFilters()">
      <select id="f-severity" onchange="applyFilters()">
        <option value="">All Severities</option>
        <option value="critical">Critical</option>
        <option value="high">High</option>
        <option value="medium">Medium</option>
        <option value="low">Low</option>
      </select>
      <select id="f-action" onchange="applyFilters()">
        <option value="">All Actions</option>
        <option value="auto-remediate">Auto-Remediate</option>
        <option value="escalate">Escalate</option>
        <option value="create-ticket">Create Ticket</option>
        <option value="deduplicated">Deduplicated</option>
      </select>
      <select id="f-actionable" onchange="applyFilters()">
        <option value="">All Types</option>
        <option value="true">Actionable</option>
        <option value="false">Non-Actionable</option>
      </select>
      <select id="f-account" onchange="applyFilters()"><option value="">All Accounts</option></select>
      <select id="f-category" onchange="applyFilters()"><option value="">All Categories</option></select>
      <button class="btn-clear" onclick="clearFilters()">✕ Clear</button>
      <div class="filter-count" id="filter-count"></div>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th onclick="sortBy('alert_triggered_at')">Time <span class="sort-icon">↕</span></th>
            <th onclick="sortBy('host.name')">Host <span class="sort-icon">↕</span></th>
            <th>Alert</th>
            <th onclick="sortBy('client.name')">Client <span class="sort-icon">↕</span></th>
            <th onclick="sortBy('client.aws_account')">AWS Account <span class="sort-icon">↕</span></th>
            <th onclick="sortBy('classification.severity')">Severity <span class="sort-icon">↕</span></th>
            <th>Actionable</th>
            <th onclick="sortBy('classification.action')">Action <span class="sort-icon">↕</span></th>
            <th>Solution</th>
            <th>Ticket</th>
          </tr>
        </thead>
        <tbody id="alerts-table-body">
          <tr><td colspan="10" class="no-data">Loading...</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<script>
let incidents = [], sortField = 'alert_triggered_at', sortDir = -1;
const SEV_C = {critical:'chip-critical',high:'chip-high',medium:'chip-medium',low:'chip-low'};
const SEV_I = {critical:'🔴',high:'🟠',medium:'🟡',low:'🔵'};
const ACT_C = {'auto-remediate':'chip-auto','create-ticket':'chip-ticket','escalate':'chip-escalate','deduplicated':'chip-dedup'};
const CAT_COL = {
  'website-down':'var(--red)','high-memory':'var(--orange)','service-down':'var(--yellow)',
  'agent-unavailable':'var(--blue)','high-cpu':'var(--purple)','disk-space':'var(--orange)',
  'high-load':'var(--yellow)','ec2-terminated':'var(--red)','host-restarted':'var(--green)',
  'unknown':'var(--text3)'
};
const STEP_DEF = {
  alert_received:{i:'🔔',c:'c-green',l:'Alert Received'},
  ai_classified:{i:'🤖',c:'c-blue',l:'AI Classified'},
  action_decided:{i:'⚡',c:'c-yellow',l:'Action Decided'},
  ticket_created:{i:'🎫',c:'c-blue',l:'Ticket Created'},
  email_sent:{i:'📧',c:'c-purple',l:'Email Sent'},
  escalated:{i:'🚨',c:'c-red',l:'Escalated to Human'},
  resolved:{i:'✅',c:'c-green',l:'Resolved'},
};

function g(id){return document.getElementById(id)}
function fmtT(ts){return new Date(ts).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit'})}
function fmtDT(ts){return new Date(ts).toLocaleString('en-IN',{dateStyle:'short',timeStyle:'medium'})}
function deepGet(obj,path){return path.split('.').reduce((o,k)=>o?.[k],obj)}

async function loadAll(){
  const [ir,hr] = await Promise.all([fetch('/api/incidents'),fetch('/health')]).catch(()=>[null,null]);
  if(ir){incidents=await ir.json();updateAll()}
  if(hr){const d=await hr.json();g('model-label').textContent=d.model||'unknown'}
}

function updateAll(){
  updateStats();
  renderFeed();
  renderChart();
  renderDonuts();
  populateFilters();
  applyFilters();
}

function updateStats(){
  const ni=incidents.filter(i=>i.classification?.action!=='deduplicated');
  g('s-total').textContent=ni.length;
  g('s-action').textContent=incidents.filter(i=>i.classification?.actionable).length;
  g('s-escalate').textContent=incidents.filter(i=>i.classification?.action==='escalate').length;
  g('s-ticket').textContent=incidents.filter(i=>i.ticket_id).length;
  g('s-dedup').textContent=incidents.filter(i=>i.classification?.action==='deduplicated').length;
}

function renderFeed(){
  const el=g('alert-feed');
  const recent=incidents.slice(0,12);
  g('active-count').textContent=`${recent.length} shown`;
  if(!recent.length){el.innerHTML='<div style="padding:20px;text-align:center;color:var(--text3);font-size:12px">No alerts yet</div>';return}
  el.innerHTML=recent.map(i=>{
    const cls=i.classification||{};
    const col=SEV_I[cls.severity]||'⚪';
    const sevColor={'critical':'var(--red)','high':'var(--orange)','medium':'var(--yellow)','low':'var(--blue)'}[cls.severity]||'var(--border)';
    return`<div class="alert-item" onclick="openDrawer('${i.incident_id}')">
      <div class="sev-strip" style="background:${sevColor}"></div>
      <div class="ai-body">
        <div class="ai-host">${i.host?.name||'?'}</div>
        <div class="ai-name">${i.alert?.name||''}</div>
        <div class="ai-meta">
          <span class="chip ${SEV_C[cls.severity]||'chip-low'}">${col} ${cls.severity||'?'}</span>
          <span class="chip ${ACT_C[cls.action]||''}">${cls.action||''}</span>
          <span class="ai-time">${fmtT(i.alert_triggered_at)}</span>
        </div>
      </div>
    </div>`;
  }).join('');
}

function renderChart(){
  const now=Date.now(), hrs=12;
  const buckets=Array.from({length:hrs},(_,i)=>({t:new Date(now-(hrs-1-i)*3600000),critical:0,high:0,medium:0,low:0}));
  incidents.forEach(inc=>{
    const t=new Date(inc.alert_triggered_at).getTime();
    const idx=Math.floor((t-(now-hrs*3600000))/3600000);
    if(idx>=0&&idx<hrs){const sev=inc.classification?.severity||'low';if(buckets[idx][sev]!==undefined)buckets[idx][sev]++;}
  });
  const maxV=Math.max(1,...buckets.map(b=>b.critical+b.high+b.medium+b.low));
  const barsEl=g('chart-bars'),labelsEl=g('chart-labels');
  barsEl.innerHTML=buckets.map((b,i)=>{
    const total=b.critical+b.high+b.medium+b.low;
    const h=(v)=>Math.max(2,Math.round((v/maxV)*140));
    return`<div class="chart-bar-group">
      <div class="chart-bar" style="background:var(--red);height:${h(b.critical)}px"><span class="bar-tip">${b.critical} critical</span></div>
      <div class="chart-bar" style="background:var(--orange);height:${h(b.high)}px"><span class="bar-tip">${b.high} high</span></div>
      <div class="chart-bar" style="background:var(--yellow);height:${h(b.medium)}px"><span class="bar-tip">${b.medium} med</span></div>
      <div class="chart-bar" style="background:var(--blue);height:${h(b.low)}px"><span class="bar-tip">${b.low} low</span></div>
    </div>`;
  }).join('');
  labelsEl.innerHTML=buckets.map(b=>`<div class="chart-label">${b.t.getHours().toString().padStart(2,'0')}h</div>`).join('');
}

function renderDonuts(){
  const catCount={},actCount={};
  incidents.forEach(i=>{
    const c=i.classification||{};
    catCount[c.category||'unknown']=(catCount[c.category||'unknown']||0)+1;
    actCount[c.action||'?']=(actCount[c.action||'?']||0)+1;
  });
  drawDonut('donut-cat','donut-cat-legend',catCount,Object.keys(catCount).map(k=>CAT_COL[k]||'var(--text3)'));
  const actColors={'auto-remediate':'var(--green)','escalate':'var(--red)','create-ticket':'var(--blue)','deduplicated':'var(--purple)'};
  drawDonut('donut-act','donut-act-legend',actCount,Object.keys(actCount).map(k=>actColors[k]||'var(--text3)'));
}

function drawDonut(svgId,legendId,data,colors){
  const svgEl=g(svgId),legEl=g(legendId);
  const keys=Object.keys(data),total=Object.values(data).reduce((a,b)=>a+b,0);
  if(!total){svgEl.innerHTML='<circle cx="50" cy="50" r="30" fill="none" stroke="var(--border)" stroke-width="14"/>';legEl.innerHTML='';return}
  let offset=0;const r=30,cx=50,cy=50,circ=2*Math.PI*r;
  const paths=keys.map((k,i)=>{
    const pct=data[k]/total,dash=pct*circ,gap=circ-dash;
    const p=`<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${colors[i]}" stroke-width="14" stroke-dasharray="${dash} ${gap}" stroke-dashoffset="${-offset*circ}" transform="rotate(-90 50 50)" style="transition:all .3s"/>`;
    offset+=pct;return p;
  }).join('');
  svgEl.innerHTML=paths+`<text x="50" y="54" text-anchor="middle" fill="var(--text)" font-size="13" font-weight="700">${total}</text>`;
  legEl.innerHTML=keys.map((k,i)=>`<div class="dl-item"><div class="dl-dot" style="background:${colors[i]}"></div><div class="dl-label">${k}</div><div class="dl-val">${data[k]}</div></div>`).join('');
}

// ── Filters ──
function populateFilters(){
  const accounts=[...new Set(incidents.map(i=>i.client?.aws_account).filter(Boolean))].sort();
  const categories=[...new Set(incidents.map(i=>i.classification?.category).filter(Boolean))].sort();
  const fAcc=g('f-account'),fCat=g('f-category');
  const av=fAcc.value,cv=fCat.value;
  fAcc.innerHTML='<option value="">All Accounts</option>'+accounts.map(a=>`<option value="${a}">${a}</option>`).join('');
  fCat.innerHTML='<option value="">All Categories</option>'+categories.map(c=>`<option value="${c}">${c}</option>`).join('');
  fAcc.value=av;fCat.value=cv;
}

function clearFilters(){
  ['f-search','f-severity','f-action','f-actionable','f-account','f-category'].forEach(id=>{g(id).value='';});
  applyFilters();
}

function applyFilters(){
  const q=g('f-search').value.toLowerCase();
  const sev=g('f-severity').value,act=g('f-action').value;
  const actable=g('f-actionable').value,acc=g('f-account').value,cat=g('f-category').value;
  let filtered=incidents.filter(i=>{
    const cls=i.classification||{};
    if(q&&!`${i.host?.name} ${i.alert?.name} ${i.client?.name} ${i.client?.aws_account}`.toLowerCase().includes(q))return false;
    if(sev&&cls.severity!==sev)return false;
    if(act&&cls.action!==act)return false;
    if(actable!==''&&String(cls.actionable)!==actable)return false;
    if(acc&&i.client?.aws_account!==acc)return false;
    if(cat&&cls.category!==cat)return false;
    return true;
  });
  filtered=[...filtered].sort((a,b)=>{
    const av=deepGet(a,sortField)||'',bv=deepGet(b,sortField)||'';
    return av<bv?sortDir:av>bv?-sortDir:0;
  });
  g('filter-count').textContent=`${filtered.length} of ${incidents.length} alerts`;
  renderTable(filtered);
}

function sortBy(f){sortDir=sortField===f?-sortDir:1;sortField=f;applyFilters();}

function renderTable(list){
  const tbody=g('alerts-table-body');
  if(!list.length){tbody.innerHTML='<tr><td colspan="10" class="no-data">No alerts match your filters</td></tr>';return}
  tbody.innerHTML=list.map(i=>{
    const cls=i.classification||{};
    return`<tr onclick="openDrawer('${i.incident_id}')">
      <td>${fmtDT(i.alert_triggered_at)}</td>
      <td class="td-host" title="${i.host?.name||''}">${i.host?.name||'?'}</td>
      <td class="td-alert" title="${i.alert?.name||''}">${i.alert?.name||''}</td>
      <td title="${i.client?.name||''}">${i.client?.name||'N/A'}</td>
      <td style="font-family:monospace;font-size:11px">${i.client?.aws_account||'N/A'}</td>
      <td><span class="chip ${SEV_C[cls.severity]||'chip-low'}">${SEV_I[cls.severity]||''} ${cls.severity||'?'}</span></td>
      <td><span class="chip ${cls.actionable?'chip-act':'chip-noact'}">${cls.actionable?'✓ Yes':'✗ No'}</span></td>
      <td><span class="chip ${ACT_C[cls.action]||''}">${cls.action||'?'}</span></td>
      <td style="color:var(--blue);font-size:11px">${cls.solution_id||'—'}</td>
      <td>${i.ticket_id?`<span class="chip chip-ticket">🎫 #${i.ticket_id}</span>`:'—'}</td>
    </tr>`;
  }).join('');
}

// ── Drawer ──
function openDrawer(id){
  const inc=incidents.find(i=>i.incident_id===id);
  if(!inc)return;
  const cls=inc.classification||{};
  const sevColor={'critical':'var(--red)','high':'var(--orange)','medium':'var(--yellow)','low':'var(--blue)'}[cls.severity]||'var(--border)';
  g('dw-head-content').innerHTML=`
    <div>
      <div class="dw-title">${inc.alert?.name||'Unknown Alert'}</div>
      <div class="dw-meta">🖥 ${inc.host?.name||'?'} &nbsp;·&nbsp; ${inc.host?.ip||''} &nbsp;·&nbsp; 👤 ${inc.client?.name||'N/A'}</div>
      <div class="dw-chips">
        <span class="chip ${SEV_C[cls.severity]||'chip-low'}">${SEV_I[cls.severity]} ${(cls.severity||'?').toUpperCase()}</span>
        <span class="chip ${cls.actionable?'chip-act':'chip-noact'}">${cls.actionable?'✓ ACTIONABLE':'✗ NON-ACTIONABLE'}</span>
        <span class="chip ${ACT_C[cls.action]||''}">${cls.action||''}</span>
        ${inc.ticket_id?`<span class="chip chip-ticket">🎫 #${inc.ticket_id}</span>`:''}
        ${cls.solution_id?`<span class="chip chip-ticket">${cls.solution_id}</span>`:''}
      </div>
    </div>`;
  const steps=inc.workflow||[];
  const solSteps=inc.resolution_steps||[];
  g('dw-body').innerHTML=`
    <div class="section">
      <div class="section-title">Workflow Timeline</div>
      <div class="tl">
        ${steps.map(s=>{const d=STEP_DEF[s.step]||{i:'•',c:'c-gray',l:s.step};return`
          <div class="tl-item">
            <div class="tl-dot ${d.c}">${d.i}</div>
            <div class="tl-body">
              <div class="tl-label">${d.l}</div>
              <div class="tl-detail">${s.detail||''}</div>
              <div class="tl-ts">${fmtDT(s.ts)}</div>
            </div>
          </div>`;}).join('')||'<div style="color:var(--text3);font-size:12px">No timeline data</div>'}
      </div>
    </div>
    <div class="section">
      <div class="section-title">AI Classification</div>
      <div class="kv-grid">
        <span class="kv-key">Actionable</span><span class="kv-val">${cls.actionable?'✅ Yes — known solution':'❌ No — no defined solution'}</span>
        <span class="kv-key">Category</span><span class="kv-val">${cls.category||'?'}</span>
        <span class="kv-key">Severity</span><span class="kv-val">${(cls.severity||'').toUpperCase()}</span>
        <span class="kv-key">Action</span><span class="kv-val">${cls.action||'?'}</span>
        <span class="kv-key">Confidence</span><span class="kv-val">${Math.round((cls.confidence||0)*100)}%</span>
        <span class="kv-key">Solution ID</span><span class="kv-val">${cls.solution_id||'None (LLM fallback)'}</span>
      </div>
      <div class="summary-strip">${cls.summary||'No summary available'}</div>
    </div>
    <div class="section">
      <div class="section-title">Alert Details</div>
      <div class="kv-grid">
        <span class="kv-key">Host</span><span class="kv-val">${inc.host?.name||'?'}</span>
        <span class="kv-key">IP Address</span><span class="kv-val">${inc.host?.ip||'N/A'}</span>
        <span class="kv-key">Client</span><span class="kv-val">${inc.client?.name||'N/A'}</span>
        <span class="kv-key">AWS Account</span><span class="kv-val">${inc.client?.aws_account||'N/A'}</span>
        <span class="kv-key">Alert Status</span><span class="kv-val">${inc.alert?.status||'?'}</span>
        <span class="kv-key">Metric Value</span><span class="kv-val">${inc.alert?.item_value||'N/A'}</span>
        <span class="kv-key">Triggered</span><span class="kv-val">${fmtDT(inc.alert_triggered_at)}</span>
        <span class="kv-key">Incident ID</span><span class="kv-val" style="font-size:10px;color:var(--text3)">${inc.incident_id}</span>
      </div>
    </div>
    <div class="section">
      <div class="section-title">Resolution Steps ${cls.solution_id?`· ${cls.solution_id}`:''}</div>
      <div class="step-list">
        ${solSteps.length?solSteps.map((s,i)=>`<div class="step-row"><div class="step-num">${i+1}</div><div class="step-txt">${s}</div></div>`).join('')
          :'<div class="step-row"><div class="step-txt" style="color:var(--text3)">No defined steps — LLM classified</div></div>'}
      </div>
    </div>`;
  g('overlay').classList.add('open');
  g('drawer').classList.add('open');
}
function closeDrawer(){g('overlay').classList.remove('open');g('drawer').classList.remove('open')}

// ── Nav ──
function showPage(p){
  document.querySelectorAll('.page').forEach(el=>el.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(el=>el.classList.remove('active'));
  g('page-'+p).classList.add('active');
  event.currentTarget.classList.add('active');
  if(p==='alerts')applyFilters();
}

// ── Theme ──
function toggleTheme(){
  const html=document.documentElement;
  const isDark=html.getAttribute('data-theme')==='dark';
  html.setAttribute('data-theme',isDark?'light':'dark');
  document.querySelector('.theme-btn').textContent=isDark?'🌙':'☀️';
}

// ── Init ──
loadAll();
setInterval(loadAll,8000);
</script>
</body>
</html>"""
