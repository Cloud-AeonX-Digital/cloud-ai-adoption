# AeonX AI Ops Agent — Master Summary & Pain Points
> Last updated: 2026-06-10 | Repo: Cloud-AeonX-Digital/cloud-ai-adoption | Branch: mrinal-dev

---

## What We Built

An autonomous AI ops agent for AeonX that:
- Monitors 706 hosts across ~90 client AWS/GCP accounts via Zabbix
- Classifies alerts using a Knowledge Base (KB) first, falls back to LLM (gpt-oss-120b via Bedrock)
- Routes every action through **human approval** before execution
- Executes approved actions via SSM Run Command (service restarts, EC2 restart)
- Provides a full monitoring dashboard (React + Node + SQLite)

---

## Architecture (confirmed, in use)

```
Zabbix alert → Lambda 1 (normalizer) → EC2 FastAPI agent (/alert)
    → KB lookup (known-solutions.json)
        ├── MATCH (99% confidence) → human-approval-required
        └── NO MATCH → LLM (gpt-oss-120b, Bedrock ap-south-1) → escalate/create-ticket
    → Approval created → React UI (Approvals tab) OR email link
    → Human approves → SSM executor runs command LIVE on server
    → Services restored → resolved alert logged
```

---

## Tech Stack (confirmed working)

| Layer | Tool | Details |
|-------|------|---------|
| Monitoring | Zabbix (self-hosted) | 706 hosts, ~90 client groups, ap-south-1 |
| Alert ingestor | AWS Lambda 1 | Normalizes Zabbix webhook → standard schema |
| AI Agent | EC2 t3.small FastAPI | `dev_env/dev_app.py` (dev), `agent/app/main.py` (prod) |
| Classification | KB-first + LLM fallback | `dev_env/classifier_dev.py` |
| LLM | gpt-oss-120b via Bedrock | Account 719395381450, ap-south-1 |
| Execution | SSM Run Command | `agent/app/ssm_executor.py` |
| Ticketing | ManageEngine ServiceDesk Plus | `agent/app/ticketing.py` — create works, resolve/close needs Technician role upgrade |
| Notifications | AWS SES | `awsalerts@aeonx.digital` — already verified |
| UI | React + Vite + Tailwind | `ui/frontend/` — port 5174 |
| Backend API | Express + SQLite | `ui/backend/` — port 3001 |
| Secrets | AWS SSM Parameter Store | `/aeonx/ai-agent/*` |
| AWS Account | 719395381450 (Sandbox) | Dev/test. Prod account: 761685920937 |

---

## Knowledge Base (agent/known-solutions.json) — 13 patterns

| ID | Pattern | Category | Actionable | Action |
|----|---------|----------|-----------|--------|
| S001 | This Website is Down | website-down | ✅ | service_restart_then_ec2 |
| S001b | health check failed | website-down | ✅ | service_restart_then_ec2 |
| S002 | High memory utilization | high-memory | ✅ | email_client |
| S003 | AwsReplicationVolumeUpdaterService | service-down | ✅ | local_restart_then_ssm |
| S004 | Zabbix agent is not available | agent-unavailable | ✅ | zabbix_service_restart |
| S005 | Active checks are not available | agent-unavailable | ❌ | notify only |
| S006 | High CPU utilization | high-cpu | ❌ | email_client |
| S007 | CPU queue length is too high | high-cpu | ❌ | email_client |
| S008 | disk space | disk-space | ❌ | human_approval_then_expand |
| S009 | is terminated | ec2-terminated | ❌ | conditional (ASG check) |
| S010 | restarted | host-restarted | ❌ | email_client |
| S011 | Load average is too high | high-load | ❌ | email_client |
| S012 | postgresql | service-down | ✅ | ssm_service_restart |

---

## Test Results (verified 2026-06-09/10)

| Series | Tests | Pass Rate |
|--------|-------|----------|
| KB Series (T1–T10) — exact Zabbix trigger names | 10/10 | 100% |
| LLM Series (L1–L5) — unknown alert types | 5/5 | 100% |
| LLM Variations (V1–V10) — same categories, different wording | 10/10 | 100% |
| **Live SSM Restart** (frontend + backend + postgresql) | 3/3 | 100% ✅ |

---

## Human Approval System

Every action routes through approval:
- `human-approval-required` → approval created → pending in UI
- Human clicks Approve in React UI or email link
- `_execute_action_async()` fires → `execute_approved_action()` → SSM or EBS expand
- Result logged, ticket updated

Approval API endpoints on agent:
- `GET /approvals` `GET /approvals/pending`
- `POST /approvals/{id}/approve` `POST /approvals/{id}/reject`
- `GET /approvals/{id}/approve` (email link, browser-friendly)

---

## File Structure (key files)

```
agent/
  app/main.py              — Production FastAPI agent
  app/classifier.py        — Production classifier (Vertex AI, not yet switched to Bedrock)
  app/ticketing.py         — ManageEngine integration
  app/approval_manager.py  — In-memory approval store
  app/ssm_executor.py      — SSM Run Command executor
  app/disk_actions.py      — EBS volume expansion
  known-solutions.json     — KB with 13 patterns
  email-templates.json     — Client email templates

dev_env/
  dev_app.py               — Dev FastAPI agent (active)
  classifier_dev.py        — Dev classifier (Bedrock gpt-oss-120b)
  notifier_dev.py          — Email mock (writes to output/emails.log)
  logger_dev.py            — S3 mock + Express sync
  test_runner.py           — 7 Zabbix test payloads
  SESSION-NOTES.md         — This file

ui/
  frontend/                — React+Vite+Tailwind (port 5174)
  backend/server.js        — Express+SQLite (port 3001)
  backend/incidents.db     — SQLite database

docs/
  test-results-report.html — Management presentation (25/25 tests)
  alert-classification-matrix.csv — Full KB matrix with action flows
  manageengine-integration.md
  ssm-secrets.md
```

---

## Pain Points — Current Status

| # | Issue | Severity | Status |
|---|-------|----------|--------|
| P1 | S012 PostgreSQL KB match in uvicorn | HIGH | ✅ FIXED |
| P2 | AWS session expires every ~1h | MEDIUM | ⏳ run `aws login` when needed |
| P3 | SSM execution untested | MEDIUM | ✅ FIXED — live tested 2026-06-10 |
| P4 | Resolved alerts create new approval | LOW | ✅ FIXED |
| P5 | Production classifier used Vertex AI | MEDIUM | ✅ FIXED — now Bedrock |
| P6 | ManageEngine resolve/close blocked | MEDIUM | ⏳ upgrade `aws.automation` to Technician |
| P7 | Production infra not deployed | HIGH | ⏳ IAM role, EC2, S3, Lambda 1 in 761685920937 |
| P8 | Zabbix webhook not wired (email is fine for now) | LOW | ⏳ after Lambda 1 deployed |
| P9 | SSM service mapping varies per client | LOW | ⏳ standardize service naming |
| P10 | Agent is single-account only | HIGH | ⏳ Phase B — multi-account tool layer |
| P11 | Agent is if/else routing, not true tool-calling | HIGH | ✅ FIXED — Phase C |
| P12 | No persistent memory / vector store | HIGH | ✅ FIXED — Phase D SQLite FTS5 |

| P13 | Aivex chat unstable — pre-flight SSM latency, disk expand approval action preview | MEDIUM | 🔄 Under Review — test cases added, core works |

---

## Build Roadmap (Full Vision)

### Phase A — Production Deploy `NEXT`
- Create IAM role `aeonx-ai-agent-role` (files in `iam/`)
- Launch EC2 t3.small in 761685920937 (private subnet, same VPC as Zabbix)
- Create S3 bucket `aeonx-ai-agent-incidents`
- Store SSM secrets (`docs/ssm-secrets.md`)
- Deploy Lambda 1 (`lambda/alert-ingestor/deploy.sh`)
- Update Zabbix Gen-AI action → Lambda 1 webhook URL
- Upgrade ManageEngine `aws.automation` → Technician role

### Phase B — Multi-account Tool Layer
Every executor accepts `(account_id, region)` and assumes `Aeonx-L2-Role` dynamically.
Unlocks all 150 client accounts with zero additional infra.

### Phase C — True Agent Tool-Calling Loop ✅ COMPLETE (2026-06-10)
**What was built:**
- `agent/tools/registry.py` — 6 tools: `search_runbook`, `get_service_status`, `get_ec2_info`, `query_cloudwatch_metric`, `get_recent_alerts`, `request_human_approval`
- `agent/app/agent_loop.py` — Bedrock Converse API loop, max 6 iterations, system prompt separate param
- `dev_env/dev_app.py` — `USE_AGENT_LOOP=true` flag (default on), falls back to KB classifier

**Key Converse API notes:**
- Content blocks use `{"toolUse": {...}}` NOT `{"type": "toolUse", ...}`
- Tool results use `{"toolResult": {...}}` NOT `{"type": "toolResult", ...}`
- System prompt is separate `system=[{"text": "..."}]` param
- `gpt-oss-120b` returns `reasoningContent` blocks before `toolUse` blocks

**Live test results:**
- Backend down → agent: search_runbook → get_service_status (confirmed inactive) → get_recent_alerts → request_human_approval(service_restart, confidence=96%) ✅
- PostgreSQL alert but service actually active → agent detected false positive → create_ticket instead of restart ✅ (smart!)

**To add new tools:** Add entry to `TOOL_SPECS` + `_HANDLERS` dict in `agent/tools/registry.py`. Agent loop picks it up automatically.

### Phase D — Persistent Memory
PostgreSQL + pgvector for incident history + semantic runbook search.
Feeds past incidents as context into every LLM call.
Enables RCA, "what changed last 24h", post-incident reports.

### Phase E — Developer Self-Service Chat (`POST /chat`)
Natural language → tool calls → response with approval gate for destructive actions.
"Spin up dev env", "Why is service X slow?", "What changed in prod today?"

### Phase F — Cost / Security / Compliance Tools
Additional tools registered in Phase C framework:
cost anomaly, Security Hub, GuardDuty, Config drift, secrets rotation.

---

## Start Commands (dev env)

```bash
# All 3 servers
python3 << 'EOF'
import subprocess, os
os.chdir('/home/kiro-chats/cloud-ai-adoption/ui/backend')
subprocess.Popen(['node','server.js'], stdout=open('/tmp/express.log','w'), stderr=subprocess.STDOUT, start_new_session=True)
os.chdir('/home/kiro-chats/cloud-ai-adoption/ui/frontend')
env = os.environ.copy(); env['VITE_API_URL']='http://localhost:3001'
subprocess.Popen(['npm','run','dev','--','--host','172.25.29.253','--port','5174'],
    stdout=open('/tmp/vite.log','w'), stderr=subprocess.STDOUT, env=env, start_new_session=True)
os.chdir('/home/kiro-chats/cloud-ai-adoption')
env2 = os.environ.copy(); env2['PYTHONPATH']='/home/kiro-chats/cloud-ai-adoption'; env2['PYTHONDONTWRITEBYTECODE']='1'
p = subprocess.Popen(['dev_env/.venv/bin/python3','-B','-m','uvicorn','dev_env.dev_app:app','--host','172.25.29.253','--port','8000'],
    stdout=open('/tmp/agent.log','w'), stderr=subprocess.STDOUT, env=env2, start_new_session=True)
open('/tmp/agent.pid','w').write(str(p.pid))
EOF

# Access
# UI: http://172.25.29.253:5174
# Agent: http://172.25.29.253:8000
# Docs: http://172.25.29.253:8080 (python3 -m http.server 8080 in docs/)
```

## Resume Prompt
```
Read dev_env/SESSION-NOTES.md in Cloud-AeonX-Digital/cloud-ai-adoption.
This file has the full system summary, architecture, KB patterns, test results, and pain points.
Check "Next Steps" section and continue from there.
```
