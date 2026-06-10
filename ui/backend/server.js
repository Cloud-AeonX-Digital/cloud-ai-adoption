const express = require('express');
const Database = require('better-sqlite3');
const cors = require('cors');
const path = require('path');
const https = require('https');

const app = express();
const PORT = process.env.PORT || 3001;
const ZABBIX_URL = 'https://cloud-monitor.aeonx.support/api_jsonrpc.php';
const ZABBIX_TOKEN = 'fb8474cd388e055411d55c473d307a41b512e034ec6f6a300e1569ed533f3e83';

app.use(cors());
app.use(express.json());

// --- DB setup ---
const db = new Database(path.join(__dirname, 'incidents.db'));
db.exec(`
  CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    source TEXT,
    triggered_at TEXT,
    host_name TEXT,
    host_ip TEXT,
    client_name TEXT,
    aws_account TEXT,
    alert_name TEXT,
    alert_severity TEXT,
    alert_status TEXT,
    alert_value TEXT,
    actionable INTEGER,
    action TEXT,
    category TEXT,
    severity TEXT,
    confidence REAL,
    solution_id TEXT,
    summary TEXT,
    ticket_id TEXT,
    raw JSON,
    created_at TEXT DEFAULT (datetime('now'))
  );
  CREATE INDEX IF NOT EXISTS idx_triggered_at ON incidents(triggered_at DESC);
  CREATE INDEX IF NOT EXISTS idx_action ON incidents(action);
  CREATE INDEX IF NOT EXISTS idx_category ON incidents(category);

  CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    incident_id TEXT,
    type TEXT,
    description TEXT,
    proposed_action TEXT,
    metadata JSON,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now')),
    decided_at TEXT,
    decided_by TEXT,
    decision_note TEXT,
    approve_url TEXT,
    reject_url TEXT,
    expires_at TEXT
  );
  CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);
  CREATE INDEX IF NOT EXISTS idx_approvals_incident ON approvals(incident_id);
`);

// --- Zabbix helper ---
function zbxRequest(method, params) {
  return new Promise((resolve) => {
    const body = JSON.stringify({ jsonrpc: '2.0', method, params, id: 1 });
    const req = https.request(ZABBIX_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${ZABBIX_TOKEN}`, 'Content-Length': Buffer.byteLength(body) }
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => { try { resolve(JSON.parse(data).result || []); } catch { resolve([]); } });
    });
    req.on('error', () => resolve([]));
    req.write(body);
    req.end();
  });
}

// --- Routes ---

// POST /incidents — called by Python agent
app.post('/incidents', (req, res) => {
  const inc = req.body;
  const cls = inc.classification || {};
  try {
    db.prepare(`
      INSERT OR REPLACE INTO incidents
      (id, source, triggered_at, host_name, host_ip, client_name, aws_account,
       alert_name, alert_severity, alert_status, alert_value,
       actionable, action, category, severity, confidence, solution_id, summary, ticket_id, raw)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    `).run(
      inc.incident_id, inc.source, inc.alert_triggered_at || inc.timestamp,
      inc.host?.name, inc.host?.ip, inc.client?.name, inc.client?.aws_account,
      inc.alert?.name, inc.alert?.severity, inc.alert?.status, inc.alert?.item_value,
      cls.actionable ? 1 : 0, cls.action, cls.category, cls.severity,
      cls.confidence, cls.solution_id, cls.summary, inc.ticket_id,
      JSON.stringify(inc)
    );
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// POST /approvals — sync from Python agent
app.post('/approvals', (req, res) => {
  const a = req.body;
  try {
    db.prepare(`
      INSERT OR REPLACE INTO approvals
      (id, incident_id, type, description, proposed_action, metadata, status,
       created_at, decided_at, decided_by, decision_note, approve_url, reject_url, expires_at)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    `).run(
      a.approval_id, a.incident_id, a.type, a.description, a.proposed_action,
      JSON.stringify(a.metadata || {}), a.status || 'pending',
      a.created_at, a.decided_at, a.decided_by, a.decision_note,
      a.approve_url, a.reject_url, a.expires_at
    );
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// GET /approvals
app.get('/approvals', (req, res) => {
  const { status, incident_id } = req.query;
  let sql = 'SELECT * FROM approvals WHERE 1=1';
  const params = [];
  if (status)      { sql += ' AND status = ?';      params.push(status); }
  if (incident_id) { sql += ' AND incident_id = ?'; params.push(incident_id); }
  sql += ' ORDER BY created_at DESC';
  const rows = db.prepare(sql).all(...params).map(r => ({ ...r, metadata: JSON.parse(r.metadata || '{}') }));
  res.json(rows);
});

// GET /approvals/:id
app.get('/approvals/:id', (req, res) => {
  const row = db.prepare('SELECT * FROM approvals WHERE id = ?').get(req.params.id);
  if (!row) return res.status(404).json({ error: 'not found' });
  row.metadata = JSON.parse(row.metadata || '{}');
  res.json(row);
});

// PATCH /approvals/:id — approve or reject from UI
app.patch('/approvals/:id', (req, res) => {
  const { status, decided_by, decision_note } = req.body;
  if (!['approved','rejected'].includes(status)) {
    return res.status(400).json({ error: 'status must be approved or rejected' });
  }
  const now = new Date().toISOString();
  db.prepare(`
    UPDATE approvals SET status=?, decided_at=?, decided_by=?, decision_note=?
    WHERE id=? AND status='pending'
  `).run(status, now, decided_by || 'ui', decision_note || '', req.params.id);

  // Also forward decision to Python agent
  const row = db.prepare('SELECT * FROM approvals WHERE id = ?').get(req.params.id);
  if (row) {
    const agentBase = process.env.AGENT_URL || 'http://172.25.29.253:8000';
    const action = status === 'approved' ? 'approve' : 'reject';
    fetch(`${agentBase}/approvals/${req.params.id}/${action}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decided_by: decided_by || 'ui', note: decision_note || '' })
    }).catch(() => {}); // non-blocking
  }

  row.metadata = JSON.parse(row?.metadata || '{}');
  res.json(row || { id: req.params.id, status });
});

// GET /incidents
app.get('/incidents', (req, res) => {
  const { severity, action, actionable, account, category, search, limit = 200 } = req.query;
  let sql = 'SELECT * FROM incidents WHERE 1=1';
  const params = [];
  if (severity)   { sql += ' AND severity = ?';   params.push(severity); }
  if (action)     { sql += ' AND action = ?';     params.push(action); }
  if (actionable !== undefined) { sql += ' AND actionable = ?'; params.push(actionable === 'true' ? 1 : 0); }
  if (account)    { sql += ' AND aws_account = ?'; params.push(account); }
  if (category)   { sql += ' AND category = ?';   params.push(category); }
  if (search)     { sql += ' AND (host_name LIKE ? OR alert_name LIKE ? OR client_name LIKE ? OR aws_account LIKE ?)'; const s = `%${search}%`; params.push(s,s,s,s); }
  sql += ' ORDER BY triggered_at DESC LIMIT ?';
  params.push(parseInt(limit));
  res.json(db.prepare(sql).all(...params));
});

// GET /incidents/:id
app.get('/incidents/:id', (req, res) => {
  const row = db.prepare('SELECT * FROM incidents WHERE id = ?').get(req.params.id);
  if (!row) return res.status(404).json({ error: 'not found' });
  row.raw = JSON.parse(row.raw || '{}');
  res.json(row);
});

// GET /stats
app.get('/stats', (req, res) => {
  const stats = db.prepare(`
    SELECT
      COUNT(*) as total,
      SUM(actionable) as actionable,
      SUM(CASE WHEN action='escalate' THEN 1 ELSE 0 END) as escalated,
      SUM(CASE WHEN action='create-ticket' THEN 1 ELSE 0 END) as tickets,
      SUM(CASE WHEN action='deduplicated' THEN 1 ELSE 0 END) as deduplicated,
      SUM(CASE WHEN ticket_id IS NOT NULL THEN 1 ELSE 0 END) as tickets_created
    FROM incidents
  `).get();
  const byCategory = db.prepare('SELECT category, COUNT(*) as count FROM incidents GROUP BY category ORDER BY count DESC').all();
  const byAction = db.prepare('SELECT action, COUNT(*) as count FROM incidents GROUP BY action').all();
  const timeline = db.prepare(`
    SELECT 
      strftime('%s', strftime('%Y-%m-%dT%H:%M:00', triggered_at)) as bucket_epoch,
      severity, COUNT(*) as count
    FROM incidents
    WHERE triggered_at >= datetime('now', '-6 hours')
    GROUP BY bucket_epoch, severity
    ORDER BY bucket_epoch
  `).all();
  res.json({ ...stats, byCategory, byAction, timeline });
});

// GET /filters — distinct values for filter dropdowns
app.get('/filters', (req, res) => {
  res.json({
    accounts: db.prepare('SELECT DISTINCT aws_account FROM incidents WHERE aws_account IS NOT NULL').all().map(r => r.aws_account),
    categories: db.prepare('SELECT DISTINCT category FROM incidents WHERE category IS NOT NULL').all().map(r => r.category),
    severities: ['critical','high','medium','low'],
    actions: ['auto-remediate','create-ticket','escalate','deduplicated'],
  });
});

// GET /live-problems — from Zabbix
app.get('/live-problems', async (req, res) => {
  const SEV = {0:'not_classified',1:'information',2:'warning',3:'average',4:'high',5:'disaster'};
  const events = await zbxRequest('event.get', {
    output: ['eventid','name','severity','clock','value','acknowledged'],
    selectHosts: ['name'],
    time_from: Math.floor(Date.now()/1000) - 10800,
    sortfield: 'clock', sortorder: 'DESC', limit: 50
  });
  res.json(events.map(e => ({
    id: e.eventid, name: e.name,
    severity: SEV[parseInt(e.severity)] || 'unknown',
    status: e.value === '1' ? 'problem' : 'resolved',
    acknowledged: e.acknowledged === '1',
    clock: parseInt(e.clock),
    host: (e.hosts || [{}])[0]?.name || '?',
  })));
});

app.get('/health', (_, res) => res.json({ status: 'ok', db: 'sqlite', incidents: db.prepare('SELECT COUNT(*) as n FROM incidents').get().n }));

// POST /chat — proxy to Python agent (fixes browser CORS)
app.post('/chat', async (req, res) => {
  const agentBase = process.env.AGENT_URL || 'http://172.25.29.253:8000';
  try {
    const r = await fetch(`${agentBase}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req.body),
    });
    const data = await r.json();
    res.json(data);
  } catch (e) {
    res.status(502).json({ answer: `Agent unreachable: ${e.message}`, tools_used: [], approval_id: null });
  }
});

app.listen(PORT, () => console.log(`Backend running on http://localhost:${PORT}`));
