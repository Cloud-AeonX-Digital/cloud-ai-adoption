# CLAUDE.md — AI Session Context & Resume Instructions

> Load this file at the start of every AI session on this project.
> It contains the confirmed stack, decisions made, and exact resume instructions.

---

## 🧠 Project

**Repo:** `Cloud-AeonX-Digital/cloud-ai-adoption`
**Team:** `AI-Adoption-Team`
**Working branch:** `mrinal-dev`
**Owner:** Mrinal-AeonX (mrinal.jani@aeonx.digital)

**What we're building:** An autonomous AI ops agent that monitors 706 hosts across ~90 AWS/GCP client accounts, classifies alerts via Vertex AI (Gemini), auto-remediates known patterns, creates ManageEngine tickets, and sends SES email summaries — with human escalation only for unknown/high-risk situations.

---

## ✅ Confirmed Stack (do not assume — these are locked in)

| Layer | Tool | Details |
|-------|------|---------|
| Monitoring | Zabbix (self-hosted) | Hosted on AWS, 706 hosts, ~90 client groups |
| Monitoring | AWS CloudWatch | Per-client AWS accounts |
| Alert channel | AWS SES | email-smtp.ap-south-1.amazonaws.com → awsalerts@aeonx.digital |
| AI/LLM | GCP Vertex AI (Gemini) | Preferred; GCP project TBD |
| Ticketing | ManageEngine ServiceDesk Plus | Self-hosted on AWS, API available |
| Notifications | AWS SES | awsalerts@aeonx.digital |
| Secrets | AWS SSM Parameter Store | Path: `/aeonx/ai-agent/*` |
| IaC | Terraform | Used for some clients |
| CI/CD | GitHub Actions | Under Cloud-AeonX-Digital / AI-Adoption-Team |
| AWS Account | 761685920937 (payer) | Region: ap-south-1 |
| IAM Role | aeonx-ai-agent-role | Policy files in `iam/` |

**Not in use:** PagerDuty, Opsgenie, Datadog, Grafana, Prometheus, Slack (Teams used for a few clients only — excluded from agent scope)

---

## 📍 Current Phase Status

| Phase | Title | Status |
|-------|-------|--------|
| Phase 1 | Foundation & Signal Ingestion | 🔄 In Progress |
| Phase 2 | AI Classification & Decision Engine | 🔲 Pending |
| Phase 3 | Auto-Remediation Layer | 🔲 Pending |
| Phase 4 | Ticketing & Notification | 🔲 Pending |
| Phase 5 | Memory & RAG Layer | 🔲 Pending |
| Phase 6 | CI/CD & Deployment Ops | 🔲 Pending |
| Phase 7 | Observability & Audit | 🔲 Pending |
| Phase 8 | Risks & Guardrails | 🔲 Pending |

---

## 🚧 Current Blockers (Phase 1)

| Blocker | Owner | Status |
|---------|-------|--------|
| IAM role `aeonx-ai-agent-role` creation | Mrinal | ⏳ Policy files ready in `iam/` |
| ManageEngine API key | Mrinal | ⏳ Creating read-only creds |
| GCP project ID for Vertex AI | Mrinal | ⏳ Project not yet created |

---

## 🔑 Key Zabbix Findings (already queried)

- Zabbix API: `https://cloud-monitor.aeonx.support/api_jsonrpc.php`
- 706 hosts, ~90 client host groups
- Active alert action: **"Gen-AI"** (actionid: 14) — fires on Average/High/Disaster severity
  - Currently sends email via AWS SES to 2 users
  - **Plan: change operation to call webhook → Lambda instead of email**
- Top alert patterns (last 7 days, auto-resolvable):
  - Website Down: 19x
  - High Memory >90% (Linux + Windows): 29x combined
  - AWS Replication Service not running: 9x
  - Zabbix agent not available: 6x

---

## 🤖 AI Working Instructions

When resuming this session:

1. Read `PROGRESS.md` — check current phase status and blockers
2. Do not re-ask questions already answered (stack is confirmed above)
3. Build one phase at a time — validate with Mrinal before moving forward
4. All secrets go to SSM Parameter Store — never hardcoded
5. EC2/VM restart actions must always check for `auto-restart=true` tag
6. Tone: Senior SRE / Cloud Architect — technical, concise, production-aware

---

## 🌿 Branch & PR Convention

- Working branch: `mrinal-dev` (day-to-day work)
- Phase branches: `phase/<number>-<short-title>`
- Each phase → own PR → reviewed → merged to `main`

---

## 📝 Session Resume Prompt

```
Read CLAUDE.md in the Cloud-AeonX-Digital/cloud-ai-adoption repo.
We are building an autonomous AI ops agent for AeonX — monitoring 706 hosts across AWS/GCP client accounts.
Stack is confirmed in CLAUDE.md. Check PROGRESS.md for current phase status and blockers, then continue from where we left off.
```
