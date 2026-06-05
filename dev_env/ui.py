"""Alert Workflow UI - FastAPI routes + full dashboard HTML."""
import json, os, glob, urllib.request, time
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()
_INCIDENTS_DIR = os.environ.get("DEV_S3_DIR", "./dev_env/output/incidents")
_ZBX_URL = "https://cloud-monitor.aeonx.support/api_jsonrpc.php"
_ZBX_TOKEN = "fb8474cd388e055411d55c473d307a41b512e034ec6f6a300e1569ed533f3e83"


def _zabbix(method, params):
    try:
        body = json.dumps({"jsonrpc":"2.0","method":method,"params":params,"id":1}).encode()
        req = urllib.request.Request(_ZBX_URL, data=body,
            headers={"Content-Type":"application/json","Authorization":f"Bearer {_ZBX_TOKEN}"},
            method="POST")
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read()).get("result", [])
    except Exception:
        return []


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

@router.get("/api/live-problems")
def live_problems():
    """Fetch last 30 events from live Zabbix (problems + resolved)."""
    SEV = {0:"not_classified",1:"information",2:"warning",3:"average",4:"high",5:"disaster"}
    events = _zabbix("event.get", {
        "output": ["eventid","name","severity","clock","value","acknowledged"],
        "selectHosts": ["name","hostid"],
        "time_from": int(time.time()) - 3600,
        "sortfield": "clock", "sortorder": "DESC", "limit": 30
    })
    return JSONResponse([{
        "id": e["eventid"],
        "name": e["name"],
        "severity": SEV.get(int(e.get("severity",0)), "unknown"),
        "status": "problem" if e.get("value")=="1" else "resolved",
        "acknowledged": e.get("acknowledged") == "1",
        "clock": int(e.get("clock",0)),
        "host": (e.get("hosts") or [{}])[0].get("name","?"),
    } for e in events])


_HTML = r"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>AeonX AI Ops</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
[data-theme="dark"]{
  --bg:#0b0e1a;--bg2:#0f1222;--surface:#141828;--surface2:#1a1f35;--surface3:#1f2540;
  --border:#252a45;--border2:#2f3560;
  --text:#e8eaf6;--text2:#8b90c0;--text3:#565b80;
  --blue:#6c8cff;--blue-d:#1a2456;--blue-g:rgba(108,140,255,.12);
  --indigo:#818cf8;--cyan:#22d3ee;
  --green:#34d399;--green-d:#082e1e;
  --yellow:#fbbf24;--yellow-d:#2a1e06;
  --orange:#fb923c;--orange-d:#2a1206;
  --red:#f87171;--red-d:#2d0a0a;
  --purple:#a78bfa;--purple-d:#1c1040;
  --shadow:0 4px 24px rgba(0,0,0,.5);
  --nav:#0d1020;
}
[data-theme="light"]{
  --bg:#f0f2ff;--bg2:#e8ebff;--surface:#fff;--surface2:#f4f6ff;--surface3:#eef0ff;
  --border:#dde0ff;--border2:#bcc3ff;
  --text:#1a1d3c;--text2:#4a4f7a;--text3:#8b90b8;
  --blue:#4361ee;--blue-d:#dde3ff;--blue-g:rgba(67,97,238,.07);
  --indigo:#6366f1;--cyan:#0891b2;
  --green:#059669;--green-d:#d1fae5;
  --yellow:#d97706;--yellow-d:#fef3c7;
  --orange:#ea580c;--orange-d:#ffedd5;
  --red:#dc2626;--red-d:#fee2e2;
  --purple:#7c3aed;--purple-d:#ede9fe;
  --shadow:0 2px 16px rgba(67,97,238,.1);
  --nav:#fff;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);height:100vh;display:flex;flex-direction:column;overflow:hidden}

/* NAV */
nav{height:54px;background:var(--nav);border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 16px;gap:0;flex-shrink:0;box-shadow:var(--shadow);z-index:100}
.nav-brand{display:flex;align-items:center;gap:9px;margin-right:24px}
.nav-icon{width:30px;height:30px;background:linear-gradient(135deg,#6c8cff,#a78bfa);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0}
.nav-name{font-weight:700;font-size:14px}
.nav-name span{color:var(--blue)}
.nav-tabs{display:flex;gap:2px;flex:1}
.nav-tab{padding:6px 14px;border-radius:7px;font-size:13px;font-weight:500;color:var(--text2);cursor:pointer;transition:.15s;border:1px solid transparent;display:flex;align-items:center;gap:6px}
.nav-tab:hover{background:var(--surface2);color:var(--text)}
.nav-tab.active{background:var(--blue-d);color:var(--blue);border-color:var(--border2)}
.nav-right{display:flex;align-items:center;gap:10px}
.live-badge{display:flex;align-items:center;gap:6px;background:var(--green-d);border:1px solid var(--green);border-radius:20px;padding:4px 10px;font-size:11px;color:var(--green)}
.live-dot{width:6px;height:6px;background:var(--green);border-radius:50%;animation:blink 2s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
.theme-btn{background:var(--surface2);border:1px solid var(--border);color:var(--text2);width:32px;height:32px;border-radius:8px;cursor:pointer;font-size:15px;display:flex;align-items:center;justify-content:center;transition:.15s}
.theme-btn:hover{border-color:var(--blue);color:var(--blue)}

/* LAYOUT */
.layout{display:flex;flex:1;overflow:hidden}

/* LEFT SIDEBAR */
.sidebar{width:300px;flex-shrink:0;background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden}
.sb-header{padding:14px 16px 10px;border-bottom:1px solid var(--border);flex-shrink:0}
.sb-title{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--text3);display:flex;align-items:center;justify-content:space-between}
.sb-count{background:var(--red-d);color:var(--red);font-size:10px;font-weight:700;padding:2px 7px;border-radius:10px}
.sb-tabs{display:flex;gap:4px;padding:10px 12px 0;flex-shrink:0}
.sb-tab{flex:1;padding:5px 0;text-align:center;font-size:11px;font-weight:600;border-radius:6px;cursor:pointer;color:var(--text3);transition:.15s;border:1px solid transparent}
.sb-tab.active{background:var(--blue-d);color:var(--blue);border-color:var(--border2)}
.sb-tab:hover:not(.active){color:var(--text2)}
.sb-list{flex:1;overflow-y:auto;padding:8px 0}
.sb-list::-webkit-scrollbar{width:3px}
.sb-list::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}

/* Problem row */
.prob-row{padding:10px 14px;border-bottom:1px solid var(--border);cursor:pointer;transition:background .12s;display:flex;flex-direction:column;gap:3px;position:relative}
.prob-row:hover{background:var(--surface2)}
.prob-row.active{background:var(--blue-g);border-left:3px solid var(--blue)}
.prob-row .pr-top{display:flex;align-items:center;gap:7px}
.prob-row .pr-sev{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.prob-row .pr-host{font-size:12px;font-weight:600;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.prob-row .pr-time{font-size:10px;color:var(--text3)}
.prob-row .pr-name{font-size:11px;color:var(--text2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-left:15px}
.prob-row .pr-tags{display:flex;gap:4px;padding-left:15px;margin-top:3px}
.resolved-row{opacity:.55}
.resolved-row .pr-sev{background:var(--green)!important}

/* MAIN CONTENT */
.main-content{flex:1;overflow:hidden;display:flex;flex-direction:column}
.page{display:none;flex:1;overflow:hidden;flex-direction:column}
.page.active{display:flex}

/* Dashboard */
.dash-body{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:16px}
.dash-body::-webkit-scrollbar{width:5px}
.dash-body::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}

/* Stat cards */
.stats-row{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.stat-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px;box-shadow:var(--shadow);transition:.15s;position:relative;overflow:hidden}
.stat-card::after{content:'';position:absolute;top:0;right:0;width:60px;height:60px;border-radius:50%;opacity:.06}
.stat-card:hover{transform:translateY(-2px)}
.stat-card .sc-row{display:flex;align-items:flex-start;justify-content:space-between}
.stat-card .sc-icon{width:40px;height:40px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0}
.stat-card .sc-val{font-size:28px;font-weight:700;letter-spacing:-1px;margin-top:10px}
.stat-card .sc-lbl{font-size:12px;color:var(--text2);margin-top:2px}
.stat-card .sc-trend{font-size:10px;color:var(--text3);margin-top:4px}

/* Mid row */
.mid-row{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.chart-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px;box-shadow:var(--shadow)}
.card-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.card-title{font-size:13px;font-weight:600}
.card-sub{font-size:11px;color:var(--text3)}
.chart-wrap{height:140px;display:flex;align-items:flex-end;gap:5px;padding-top:16px}
.bar-col{flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;height:100%}
.bar-stack{width:100%;display:flex;flex-direction:column-reverse;align-items:center;flex:1;justify-content:flex-start;gap:1px}
.bar-seg{width:100%;border-radius:3px 3px 0 0;min-height:2px;transition:.3s;cursor:pointer;position:relative}
.bar-seg:first-child{border-radius:0}
.bar-seg:last-child{border-radius:3px 3px 0 0}
.bar-lbl{font-size:9px;color:var(--text3);margin-top:4px}
.legend-row{display:flex;gap:12px;margin-top:10px;flex-wrap:wrap}
.leg{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--text2)}
.leg-dot{width:8px;height:8px;border-radius:3px}

/* Donut row */
.donut-row{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.donut-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px;box-shadow:var(--shadow)}
.donut-body{display:flex;align-items:center;gap:18px;margin-top:10px}
.donut-leg{display:flex;flex-direction:column;gap:7px;flex:1}
.dl{display:flex;align-items:center;gap:7px;font-size:12px}
.dl-dot{width:9px;height:9px;border-radius:3px;flex-shrink:0}
.dl-lbl{color:var(--text2);flex:1}
.dl-val{font-weight:600;font-size:13px}

/* Alerts table page */
.alerts-body{flex:1;display:flex;flex-direction:column;overflow:hidden;padding:16px}
.filter-bar{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 14px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px;box-shadow:var(--shadow)}
.f-input,.f-select{background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:7px 11px;border-radius:8px;font-size:12px;outline:none;transition:.15s;-webkit-appearance:none}
.f-input:focus,.f-select:focus{border-color:var(--blue)}
.f-search{flex:1;min-width:150px}
.btn-clear{background:none;border:1px solid var(--border);color:var(--text3);padding:7px 12px;border-radius:8px;cursor:pointer;font-size:12px;transition:.15s}
.btn-clear:hover{border-color:var(--red);color:var(--red)}
.f-count{font-size:11px;color:var(--text3);margin-left:auto;white-space:nowrap}

.tbl-wrap{flex:1;overflow:auto;background:var(--surface);border:1px solid var(--border);border-radius:10px;box-shadow:var(--shadow)}
.tbl-wrap::-webkit-scrollbar{width:5px;height:5px}
.tbl-wrap::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
table{width:100%;border-collapse:collapse;font-size:12px}
thead{position:sticky;top:0;z-index:1}
th{background:var(--surface2);padding:10px 14px;text-align:left;font-size:10px;font-weight:700;color:var(--text3);text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid var(--border);white-space:nowrap;cursor:pointer;user-select:none}
th:hover{color:var(--text2)}
td{padding:10px 14px;border-bottom:1px solid var(--border);vertical-align:middle;max-width:200px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
tr:last-child td{border-bottom:none}
tr:hover td{background:var(--surface2);cursor:pointer}
.no-data{padding:48px;text-align:center;color:var(--text3);font-size:13px}

/* Chips */
.chip{display:inline-flex;align-items:center;gap:3px;font-size:10px;font-weight:700;padding:2px 8px;border-radius:20px;text-transform:uppercase;letter-spacing:.03em;white-space:nowrap}
.c-critical{background:var(--red-d);color:var(--red)}
.c-high{background:var(--orange-d);color:var(--orange)}
.c-medium{background:var(--yellow-d);color:var(--yellow)}
.c-low{background:var(--blue-d);color:var(--blue)}
.c-info{background:var(--purple-d);color:var(--purple)}
.c-noclass{background:var(--surface3);color:var(--text3)}
.c-act{background:var(--green-d);color:var(--green)}
.c-noact{background:var(--surface3);color:var(--text3);border:1px solid var(--border)}
.c-auto{background:var(--green-d);color:var(--green)}
.c-ticket{background:var(--blue-d);color:var(--blue)}
.c-escalate{background:var(--red-d);color:var(--red)}
.c-dedup{background:var(--purple-d);color:var(--purple)}

/* Drawer */
.overlay{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:200;display:none;backdrop-filter:blur(3px)}
.overlay.open{display:block}
.drawer{position:fixed;right:0;top:0;bottom:0;width:560px;background:var(--surface);border-left:1px solid var(--border);z-index:201;transform:translateX(100%);transition:transform .25s cubic-bezier(.4,0,.2,1);display:flex;flex-direction:column;overflow:hidden}
.drawer.open{transform:translateX(0)}
.dw-hdr{padding:18px 20px;border-bottom:1px solid var(--border);flex-shrink:0;display:flex;gap:10px;align-items:flex-start;position:sticky;top:0;background:var(--surface);z-index:1}
.dw-hdr-body{flex:1;min-width:0}
.dw-close{width:30px;height:30px;background:var(--surface2);border:1px solid var(--border);color:var(--text2);border-radius:7px;cursor:pointer;font-size:16px;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:.15s}
.dw-close:hover{border-color:var(--red);color:var(--red)}
.dw-body{flex:1;overflow-y:auto;padding:18px 20px}
.dw-body::-webkit-scrollbar{width:4px}
.dw-body::-webkit-scrollbar-thumb{background:var(--border)}
.dw-title{font-size:15px;font-weight:700;line-height:1.3;margin-bottom:4px}
.dw-sub{font-size:12px;color:var(--text2);margin-bottom:10px}
.dw-chips{display:flex;gap:6px;flex-wrap:wrap}
.sec{margin-bottom:18px}
.sec-title{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--text3);margin-bottom:10px;display:flex;align-items:center;gap:8px}
.sec-title::after{content:'';flex:1;height:1px;background:var(--border)}
.kv{display:grid;grid-template-columns:120px 1fr;gap:5px 10px;font-size:12px}
.kk{color:var(--text2)}
.kv-v{color:var(--text);word-break:break-all}
.summary-box{background:var(--blue-g);border:1px solid var(--border2);border-left:3px solid var(--blue);border-radius:0 8px 8px 0;padding:11px 13px;font-size:12px;line-height:1.6;margin-top:8px}

/* Timeline */
.tl{position:relative;padding-left:18px}
.tl::before{content:'';position:absolute;left:11px;top:20px;bottom:12px;width:2px;background:var(--border)}
.tl-item{position:relative;display:flex;gap:12px;padding-bottom:18px}
.tl-item:last-child{padding-bottom:0}
.tl-dot{width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;flex-shrink:0;position:relative;z-index:1;border:2px solid}
.dg{background:var(--green-d);border-color:var(--green)}
.db{background:var(--blue-d);border-color:var(--blue)}
.dy{background:var(--yellow-d);border-color:var(--yellow)}
.dr{background:var(--red-d);border-color:var(--red)}
.dp{background:var(--purple-d);border-color:var(--purple)}
.dgr{background:var(--surface3);border-color:var(--border2)}
.tl-bd{padding-top:2px;flex:1}
.tl-lbl{font-size:12px;font-weight:600}
.tl-det{font-size:11px;color:var(--text2);margin-top:2px;line-height:1.5}
.tl-ts{font-size:10px;color:var(--text3);margin-top:3px}

.steps{display:flex;flex-direction:column;gap:5px}
.step{display:flex;gap:9px;background:var(--surface2);border-radius:7px;padding:8px 10px;align-items:flex-start}
.step-n{min-width:20px;height:20px;background:var(--blue-d);border-radius:5px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:var(--blue)}
.step-t{font-size:11px;color:var(--text2);line-height:1.5}
</style>
</head>
<body>
<nav>
  <div class="nav-brand">
    <div class="nav-icon">🤖</div>
    <div class="nav-name"><span>AeonX</span> AI Ops</div>
  </div>
  <div class="nav-tabs">
    <div class="nav-tab active" onclick="showPage('dash',this)">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
      Dashboard
    </div>
    <div class="nav-tab" onclick="showPage('alerts',this)">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2"/></svg>
      All Alerts
    </div>
  </div>
  <div class="nav-right">
    <div class="live-badge"><div class="live-dot"></div><span id="model-lbl">Loading…</span></div>
    <button class="theme-btn" id="theme-btn" onclick="toggleTheme()">🌙</button>
  </div>
</nav>

<div class="layout">
  <!-- LEFT SIDEBAR: Live Zabbix Problems -->
  <div class="sidebar">
    <div class="sb-header">
      <div class="sb-title">
        <span>🔴 Live Problems</span>
        <span class="sb-count" id="prob-count">0</span>
      </div>
    </div>
    <div class="sb-tabs">
      <div class="sb-tab active" id="tab-problems" onclick="switchSbTab('problems')">Problems</div>
      <div class="sb-tab" id="tab-recent" onclick="switchSbTab('recent')">Recent</div>
    </div>
    <div class="sb-list" id="sb-list"></div>
  </div>

  <!-- MAIN -->
  <div class="main-content">
    <!-- OVERLAY + DRAWER -->
    <div class="overlay" id="overlay" onclick="closeDrawer()"></div>
    <div class="drawer" id="drawer">
      <div class="dw-hdr">
        <div class="dw-hdr-body" id="dw-hdr-body"></div>
        <button class="dw-close" onclick="closeDrawer()">✕</button>
      </div>
      <div class="dw-body" id="dw-body"></div>
    </div>

    <!-- DASHBOARD PAGE -->
    <div class="page active" id="page-dash">
      <div class="dash-body">
        <div class="stats-row">
          <div class="stat-card">
            <div class="sc-row">
              <div><div class="sc-lbl">Total Alerts</div><div class="sc-val" id="s-total">-</div></div>
              <div class="sc-icon" style="background:var(--blue-d);color:var(--blue)">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/></svg>
              </div>
            </div>
            <div class="sc-trend" id="s-live-count"></div>
          </div>
          <div class="stat-card">
            <div class="sc-row">
              <div><div class="sc-lbl">Actionable</div><div class="sc-val" style="color:var(--green)" id="s-act">-</div></div>
              <div class="sc-icon" style="background:var(--green-d);color:var(--green)">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 11.08 22 12 12 22 2 12 2.76 11.08"/><path d="M12 2L2 7l10 5 10-5-10-5z"/></svg>
              </div>
            </div>
            <div class="sc-trend">Known solution exists</div>
          </div>
          <div class="stat-card">
            <div class="sc-row">
              <div><div class="sc-lbl">Escalated</div><div class="sc-val" style="color:var(--red)" id="s-esc">-</div></div>
              <div class="sc-icon" style="background:var(--red-d);color:var(--red)">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
              </div>
            </div>
            <div class="sc-trend">Needs human review</div>
          </div>
          <div class="stat-card">
            <div class="sc-row">
              <div><div class="sc-lbl">Tickets Created</div><div class="sc-val" style="color:var(--yellow)" id="s-tkt">-</div></div>
              <div class="sc-icon" style="background:var(--yellow-d);color:var(--yellow)">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="4" width="22" height="16" rx="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>
              </div>
            </div>
            <div class="sc-trend">ManageEngine tickets</div>
          </div>
        </div>

        <div class="mid-row">
          <div class="chart-card">
            <div class="card-hdr">
              <div class="card-title">Alert Activity - Last 12h</div>
              <div class="card-sub" id="chart-sub"></div>
            </div>
            <div class="chart-wrap" id="chart-bars"></div>
            <div id="chart-labels" style="display:flex;gap:5px;margin-top:5px"></div>
            <div class="legend-row">
              <div class="leg"><div class="leg-dot" style="background:var(--red)"></div>Critical</div>
              <div class="leg"><div class="leg-dot" style="background:var(--orange)"></div>High</div>
              <div class="leg"><div class="leg-dot" style="background:var(--yellow)"></div>Medium</div>
              <div class="leg"><div class="leg-dot" style="background:var(--blue)"></div>Low</div>
            </div>
          </div>
          <div class="chart-card">
            <div class="card-hdr"><div class="card-title">By Category</div></div>
            <div class="donut-body">
              <svg width="110" height="110" viewBox="0 0 110 110" id="donut-cat"></svg>
              <div class="donut-leg" id="donut-cat-leg"></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ALERTS PAGE -->
    <div class="page" id="page-alerts">
      <div class="alerts-body">
        <div class="filter-bar">
          <input class="f-input f-search" type="text" placeholder="🔍  Search host, alert, client, account…" id="f-search" oninput="applyFilters()">
          <select class="f-select" id="f-sev" onchange="applyFilters()"><option value="">All Severities</option><option>critical</option><option>high</option><option>medium</option><option>low</option></select>
          <select class="f-select" id="f-act" onchange="applyFilters()"><option value="">All Actions</option><option value="auto-remediate">Auto-Remediate</option><option value="escalate">Escalate</option><option value="create-ticket">Create Ticket</option><option value="deduplicated">Deduplicated</option></select>
          <select class="f-select" id="f-able" onchange="applyFilters()"><option value="">All Types</option><option value="true">Actionable</option><option value="false">Non-Actionable</option></select>
          <select class="f-select" id="f-acc" onchange="applyFilters()"><option value="">All Accounts</option></select>
          <select class="f-select" id="f-cat" onchange="applyFilters()"><option value="">All Categories</option></select>
          <button class="btn-clear" onclick="clearFilters()">✕ Clear</button>
          <span class="f-count" id="f-count"></span>
        </div>
        <div class="tbl-wrap">
          <table>
            <thead><tr>
              <th onclick="sortBy('alert_triggered_at')">Time ↕</th>
              <th onclick="sortBy('host.name')">Host ↕</th>
              <th>Alert</th>
              <th onclick="sortBy('client.name')">Client ↕</th>
              <th onclick="sortBy('client.aws_account')">Account ↕</th>
              <th onclick="sortBy('classification.severity')">Severity ↕</th>
              <th>Type</th>
              <th onclick="sortBy('classification.action')">Action ↕</th>
              <th>Solution</th>
              <th>Ticket</th>
            </tr></thead>
            <tbody id="tbl-body"><tr><td colspan="10" class="no-data">Loading…</td></tr></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
const SEV_C={critical:'c-critical',high:'c-high',medium:'c-medium',low:'c-low',information:'c-info',warning:'c-medium',average:'c-high',disaster:'c-critical',not_classified:'c-noclass'};
const SEV_I={critical:'🔴',high:'🟠',medium:'🟡',low:'🔵',information:'⚪',warning:'🟡',average:'🟠',disaster:'🔴',not_classified:'⚫'};
const ACT_C={'auto-remediate':'c-auto','create-ticket':'c-ticket','escalate':'c-escalate','deduplicated':'c-dedup'};
const SDEV={critical:'var(--red)',high:'var(--orange)',medium:'var(--yellow)',low:'var(--blue)',information:'var(--purple)',warning:'var(--yellow)',average:'var(--orange)',disaster:'var(--red)',not_classified:'var(--text3)'};
const TL_DEF={alert_received:{i:'🔔',c:'dg',l:'Alert Received'},ai_classified:{i:'🤖',c:'db',l:'AI Classified'},action_decided:{i:'⚡',c:'dy',l:'Action Decided'},ticket_created:{i:'🎫',c:'db',l:'Ticket Created'},email_sent:{i:'📧',c:'dp',l:'Email Sent'},escalated:{i:'🚨',c:'dr',l:'Escalated to Human'},resolved:{i:'✅',c:'dg',l:'Resolved'}};
const CAT_COL={'website-down':'var(--red)','high-memory':'var(--orange)','service-down':'var(--yellow)','agent-unavailable':'var(--blue)','high-cpu':'var(--purple)','disk-space':'var(--orange)','high-load':'var(--yellow)','ec2-terminated':'var(--red)','host-restarted':'var(--green)','unknown':'var(--text3)'};

let incidents=[],liveProbs=[],sbTab='problems',sortF='alert_triggered_at',sortD=-1;

function g(id){return document.getElementById(id)}
function fmtT(ts){return new Date(ts).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit'})}
function fmtDT(ts){return new Date(ts).toLocaleString('en-IN',{dateStyle:'short',timeStyle:'short'})}
function fmtAgo(sec){if(sec<60)return sec+'s ago';if(sec<3600)return Math.floor(sec/60)+'m ago';return Math.floor(sec/3600)+'h ago'}
function dg(obj,p){return p.split('.').reduce((o,k)=>o?.[k],obj)}

async function loadAll(){
  try{
    const [ir,hr,pr]=await Promise.all([fetch('/api/incidents'),fetch('/health'),fetch('/api/live-problems')]);
    incidents=await ir.json();
    const hd=await hr.json();g('model-lbl').textContent=hd.model||'?';
    liveProbs=await pr.json();
    renderSidebar();updateStats();renderChart();renderDonut();populateFilters();applyFilters();
  }catch(e){console.error(e)}
}

/* SIDEBAR */
function switchSbTab(t){
  sbTab=t;
  g('tab-problems').classList.toggle('active',t==='problems');
  g('tab-recent').classList.toggle('active',t==='recent');
  renderSidebar();
}

function renderSidebar(){
  const now=Math.floor(Date.now()/1000);
  const probs=sbTab==='problems'?liveProbs.filter(p=>p.status==='problem'):liveProbs;
  const activeProbs=liveProbs.filter(p=>p.status==='problem').length;
  g('prob-count').textContent=activeProbs;
  if(!probs.length){g('sb-list').innerHTML='<div style="padding:20px;text-align:center;color:var(--text3);font-size:12px">'+( sbTab==='problems'?'✅ No active problems':'No recent events')+'</div>';return}
  g('sb-list').innerHTML=probs.map(p=>{
    const col=SDEV[p.severity]||'var(--text3)';
    const isRes=p.status==='resolved';
    const ago=fmtAgo(now-p.clock);
    const sevMap={'not_classified':'NC','information':'Info','warning':'Warn','average':'Avg','high':'High','disaster':'DISAS'};
    return`<div class="prob-row${isRes?' resolved-row':''}" onclick="openDrawerByName('${p.name.replace(/'/g,"\\'")}','${p.host}')">
      <div class="pr-top">
        <div class="pr-sev" style="background:${col}"></div>
        <div class="pr-host">${p.host}</div>
        <div class="pr-time">${ago}</div>
      </div>
      <div class="pr-name">${p.name}</div>
      <div class="pr-tags">
        <span class="chip ${SEV_C[p.severity]||'c-noclass'}">${SEV_I[p.severity]||'⚫'} ${sevMap[p.severity]||p.severity}</span>
        ${isRes?'<span class="chip c-act">✓ Resolved</span>':''}
        ${p.acknowledged?'<span class="chip c-ticket">Acked</span>':''}
      </div>
    </div>`;
  }).join('');
}

/* STATS */
function updateStats(){
  const ni=incidents.filter(i=>i.classification?.action!=='deduplicated');
  g('s-total').textContent=ni.length;
  g('s-act').textContent=incidents.filter(i=>i.classification?.actionable).length;
  g('s-esc').textContent=incidents.filter(i=>i.classification?.action==='escalate').length;
  g('s-tkt').textContent=incidents.filter(i=>i.ticket_id).length;
  const live=liveProbs.filter(p=>p.status==='problem').length;
  g('s-live-count').textContent=live?`${live} active in Zabbix`:'No active problems in Zabbix';
}

/* BAR CHART */
function renderChart(){
  const now=Date.now(),hrs=12;
  const B=Array.from({length:hrs},()=>({c:0,h:0,m:0,l:0}));
  incidents.forEach(i=>{
    const idx=Math.floor((new Date(i.alert_triggered_at).getTime()-(now-hrs*3600000))/3600000);
    if(idx>=0&&idx<hrs){const s=i.classification?.severity||'low';if(s==='critical')B[idx].c++;else if(s==='high')B[idx].h++;else if(s==='medium')B[idx].m++;else B[idx].l++;}
  });
  const maxV=Math.max(1,...B.map(b=>b.c+b.h+b.m+b.l));
  const bars=g('chart-bars'),labs=g('chart-labels');
  bars.innerHTML=B.map((b,i)=>{
    const total=b.c+b.h+b.m+b.l;
    const pct=v=>Math.max(2,Math.round((v/maxV)*110));
    return`<div class="bar-col">
      <div class="bar-stack">
        ${b.c?`<div class="bar-seg" style="background:var(--red);height:${pct(b.c)}px" title="${b.c} critical"></div>`:''}
        ${b.h?`<div class="bar-seg" style="background:var(--orange);height:${pct(b.h)}px" title="${b.h} high"></div>`:''}
        ${b.m?`<div class="bar-seg" style="background:var(--yellow);height:${pct(b.m)}px" title="${b.m} medium"></div>`:''}
        ${b.l?`<div class="bar-seg" style="background:var(--blue);height:${pct(b.l)}px" title="${b.l} low"></div>`:''}
        ${!total?`<div class="bar-seg" style="background:var(--border);height:4px"></div>`:''}
      </div>
    </div>`;
  }).join('');
  labs.innerHTML=B.map((_,i)=>{
    const h=new Date(now-(hrs-1-i)*3600000).getHours();
    return`<div style="flex:1;text-align:center;font-size:9px;color:var(--text3)">${String(h).padStart(2,'0')}h</div>`;
  }).join('');
  g('chart-sub').textContent=`${incidents.length} total alerts processed`;
}

/* DONUT */
function renderDonut(){
  const cnt={};
  incidents.forEach(i=>{const c=i.classification?.category||'unknown';cnt[c]=(cnt[c]||0)+1});
  const keys=Object.keys(cnt),total=Object.values(cnt).reduce((a,b)=>a+b,0);
  const cols=keys.map(k=>CAT_COL[k]||'var(--text3)');
  const svgEl=g('donut-cat'),legEl=g('donut-cat-leg');
  if(!total){svgEl.innerHTML='<circle cx="55" cy="55" r="35" fill="none" stroke="var(--border)" stroke-width="16"/>'; legEl.innerHTML='';return}
  const r=35,cx=55,cy=55,circ=2*Math.PI*r;
  let off=0;
  const paths=keys.map((k,i)=>{
    const pct=cnt[k]/total,dash=pct*circ,gap=circ-dash;
    const p=`<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${cols[i]}" stroke-width="16" stroke-dasharray="${dash.toFixed(1)} ${gap.toFixed(1)}" stroke-dashoffset="${(-off*circ).toFixed(1)}" transform="rotate(-90 55 55)"/>`;
    off+=pct;return p;
  }).join('');
  svgEl.innerHTML=paths+`<text x="55" y="59" text-anchor="middle" fill="var(--text)" font-size="14" font-weight="700">${total}</text>`;
  legEl.innerHTML=keys.map((k,i)=>`<div class="dl"><div class="dl-dot" style="background:${cols[i]}"></div><div class="dl-lbl">${k}</div><div class="dl-val">${cnt[k]}</div></div>`).join('');
}

/* FILTERS */
function populateFilters(){
  const accs=[...new Set(incidents.map(i=>i.client?.aws_account).filter(Boolean))].sort();
  const cats=[...new Set(incidents.map(i=>i.classification?.category).filter(Boolean))].sort();
  const fA=g('f-acc'),fC=g('f-cat'),av=fA.value,cv=fC.value;
  fA.innerHTML='<option value="">All Accounts</option>'+accs.map(a=>`<option>${a}</option>`).join('');
  fC.innerHTML='<option value="">All Categories</option>'+cats.map(c=>`<option>${c}</option>`).join('');
  fA.value=av;fC.value=cv;
}
function clearFilters(){['f-search','f-sev','f-act','f-able','f-acc','f-cat'].forEach(id=>g(id).value='');applyFilters()}
function sortBy(f){sortD=sortF===f?-sortD:1;sortF=f;applyFilters()}

function applyFilters(){
  const q=g('f-search').value.toLowerCase(),sev=g('f-sev').value,act=g('f-act').value;
  const able=g('f-able').value,acc=g('f-acc').value,cat=g('f-cat').value;
  let list=incidents.filter(i=>{
    const cls=i.classification||{};
    if(q&&!`${i.host?.name} ${i.alert?.name} ${i.client?.name} ${i.client?.aws_account}`.toLowerCase().includes(q))return false;
    if(sev&&cls.severity!==sev)return false;
    if(act&&cls.action!==act)return false;
    if(able!==''&&String(cls.actionable)!==able)return false;
    if(acc&&i.client?.aws_account!==acc)return false;
    if(cat&&cls.category!==cat)return false;
    return true;
  }).sort((a,b)=>{const av=dg(a,sortF)||'',bv=dg(b,sortF)||'';return av<bv?sortD:av>bv?-sortD:0});
  g('f-count').textContent=`${list.length} / ${incidents.length}`;
  g('tbl-body').innerHTML=list.map(i=>{
    const cls=i.classification||{};
    return`<tr onclick="openDrawer('${i.incident_id}')">
      <td>${fmtDT(i.alert_triggered_at)}</td>
      <td title="${i.host?.name||''}" style="font-weight:500">${i.host?.name||'?'}</td>
      <td title="${i.alert?.name||''}" style="color:var(--text2)">${i.alert?.name||''}</td>
      <td>${i.client?.name||'-'}</td>
      <td style="font-family:monospace;font-size:11px">${i.client?.aws_account||'-'}</td>
      <td><span class="chip ${SEV_C[cls.severity]||'c-low'}">${SEV_I[cls.severity]||''} ${cls.severity||'?'}</span></td>
      <td><span class="chip ${cls.actionable?'c-act':'c-noact'}">${cls.actionable?'✓ Yes':'✗ No'}</span></td>
      <td><span class="chip ${ACT_C[cls.action]||''}">${cls.action||'?'}</span></td>
      <td style="color:var(--blue);font-size:11px">${cls.solution_id||'-'}</td>
      <td>${i.ticket_id?`<span class="chip c-ticket">🎫 ${i.ticket_id}</span>`:'-'}</td>
    </tr>`;
  }).join('')||`<tr><td colspan="10" class="no-data">No alerts match filters</td></tr>`;
}

/* DRAWER */
function openDrawer(id){
  const inc=incidents.find(i=>i.incident_id===id);
  if(!inc)return;renderDrawer(inc);
}
function openDrawerByName(name,host){
  const inc=incidents.find(i=>i.alert?.name===name&&i.host?.name===host)||incidents.find(i=>i.alert?.name===name);
  if(inc){renderDrawer(inc);return}
  // Show Zabbix problem info only
  const prob=liveProbs.find(p=>p.name===name&&p.host===host);
  if(!prob)return;
  const now=Math.floor(Date.now()/1000);
  g('dw-hdr-body').innerHTML=`<div class="dw-title">${prob.name}</div><div class="dw-sub">🖥 ${prob.host}</div><div class="dw-chips"><span class="chip ${SEV_C[prob.severity]||'c-low'}">${SEV_I[prob.severity]} ${prob.severity.toUpperCase()}</span><span class="chip ${prob.status==='resolved'?'c-act':'c-escalate'}">${prob.status.toUpperCase()}</span></div>`;
  g('dw-body').innerHTML=`<div class="sec"><div class="sec-title">Zabbix Event</div><div class="kv"><span class="kk">Host</span><span class="kv-v">${prob.host}</span><span class="kk">Alert</span><span class="kv-v">${prob.name}</span><span class="kk">Severity</span><span class="kv-v">${prob.severity}</span><span class="kk">Status</span><span class="kv-v">${prob.status}</span><span class="kk">Time</span><span class="kv-v">${fmtAgo(now-prob.clock)}</span></div><div class="summary-strip" style="margin-top:10px">This alert is from live Zabbix and has not yet been processed by the AI agent. Run the agent to classify and act on it.</div></div>`;
  g('overlay').classList.add('open');g('drawer').classList.add('open');
}

function renderDrawer(inc){
  const cls=inc.classification||{};
  g('dw-hdr-body').innerHTML=`
    <div class="dw-title">${inc.alert?.name||'?'}</div>
    <div class="dw-sub">🖥 ${inc.host?.name||'?'} &nbsp;·&nbsp; ${inc.host?.ip||''} &nbsp;·&nbsp; 👤 ${inc.client?.name||'N/A'}</div>
    <div class="dw-chips">
      <span class="chip ${SEV_C[cls.severity]||'c-low'}">${SEV_I[cls.severity]} ${(cls.severity||'?').toUpperCase()}</span>
      <span class="chip ${cls.actionable?'c-act':'c-noact'}">${cls.actionable?'✓ ACTIONABLE':'✗ NON-ACTIONABLE'}</span>
      <span class="chip ${ACT_C[cls.action]||''}">${cls.action||''}</span>
      ${inc.ticket_id?`<span class="chip c-ticket">🎫 #${inc.ticket_id}</span>`:''}
      ${cls.solution_id?`<span class="chip c-ticket">${cls.solution_id}</span>`:''}
    </div>`;
  const steps=(inc.workflow||[]).map(s=>{const d=TL_DEF[s.step]||{i:'•',c:'dgr',l:s.step};return`<div class="tl-item"><div class="tl-dot ${d.c}">${d.i}</div><div class="tl-bd"><div class="tl-lbl">${d.l}</div><div class="tl-det">${s.detail||''}</div><div class="tl-ts">${fmtDT(s.ts)}</div></div></div>`;}).join('');
  const solSteps=(inc.resolution_steps||[]).map((s,i)=>`<div class="step"><div class="step-n">${i+1}</div><div class="step-t">${s}</div></div>`).join('');
  g('dw-body').innerHTML=`
    <div class="sec"><div class="sec-title">Workflow Timeline</div><div class="tl">${steps||'<div style="color:var(--text3);font-size:12px">No timeline data</div>'}</div></div>
    <div class="sec"><div class="sec-title">AI Classification</div>
      <div class="kv">
        <span class="kk">Actionable</span><span class="kv-v">${cls.actionable?'✅ Yes - known solution':'❌ No - LLM fallback'}</span>
        <span class="kk">Category</span><span class="kv-v">${cls.category||'?'}</span>
        <span class="kk">Severity</span><span class="kv-v">${(cls.severity||'').toUpperCase()}</span>
        <span class="kk">Action</span><span class="kv-v">${cls.action||'?'}</span>
        <span class="kk">Confidence</span><span class="kv-v">${Math.round((cls.confidence||0)*100)}%</span>
        <span class="kk">Solution ID</span><span class="kv-v">${cls.solution_id||'LLM'}</span>
      </div>
      <div class="summary-box">${cls.summary||'No summary'}</div>
    </div>
    <div class="sec"><div class="sec-title">Alert Details</div>
      <div class="kv">
        <span class="kk">Host</span><span class="kv-v">${inc.host?.name||'?'}</span>
        <span class="kk">IP</span><span class="kv-v">${inc.host?.ip||'N/A'}</span>
        <span class="kk">Client</span><span class="kv-v">${inc.client?.name||'N/A'}</span>
        <span class="kk">AWS Account</span><span class="kv-v">${inc.client?.aws_account||'N/A'}</span>
        <span class="kk">Alert Status</span><span class="kv-v">${inc.alert?.status||'?'}</span>
        <span class="kk">Metric Value</span><span class="kv-v">${inc.alert?.item_value||'N/A'}</span>
        <span class="kk">Triggered</span><span class="kv-v">${fmtDT(inc.alert_triggered_at)}</span>
      </div>
    </div>
    <div class="sec"><div class="sec-title">Resolution Steps ${cls.solution_id?`· ${cls.solution_id}`:''}</div>
      <div class="steps">${solSteps||'<div class="step"><div class="step-t" style="color:var(--text3)">No defined steps</div></div>'}</div>
    </div>`;
  g('overlay').classList.add('open');g('drawer').classList.add('open');
}
function closeDrawer(){g('overlay').classList.remove('open');g('drawer').classList.remove('open')}

/* NAV + THEME */
function showPage(p,el){
  document.querySelectorAll('.page').forEach(x=>x.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(x=>x.classList.remove('active'));
  g('page-'+p).classList.add('active');
  el.classList.add('active');
}
function toggleTheme(){
  const h=document.documentElement,isDark=h.getAttribute('data-theme')==='dark';
  h.setAttribute('data-theme',isDark?'light':'dark');
  g('theme-btn').textContent=isDark?'🌙':'☀️';
}

loadAll();
setInterval(loadAll,10000);
</script>
</body>
</html>"""
