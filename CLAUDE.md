# CLAUDE.md — AI Session Context & Resume Instructions

> Load this file at the start of every AI session on this project.
> Contains confirmed stack, decisions, and exact resume instructions.

---

## 🧠 Project

**Repo:** `Cloud-AeonX-Digital/cloud-ai-adoption`
**Team:** `AI-Adoption-Team`
**Working branch:** `mrinal-dev`
**Owner:** Mrinal-AeonX (mrinal.jani@aeonx.digital)

**What we're building:** Autonomous AI ops agent — monitors 706 hosts across ~90 AWS/GCP client accounts via Zabbix, classifies alerts with Vertex AI (Gemini), auto-remediates known patterns, creates ManageEngine tickets, sends SES summaries. Human escalation only for unknown/high-risk situations.

---

## ✅ Confirmed Stack (locked in — do not re-ask)

| Layer | Tool | Details |
|-------|------|---------|
| Monitoring | Zabbix (self-hosted) | AWS, 706 hosts, ~90 client groups, ap-south-1 |
| Alert ingestor | AWS Lambda | Lambda 1 — thin normalizer, ap-south-1 |
| AI Decision Engine | EC2 t3.small | FastAPI/Python, ap-south-1, persistent service |
| AI/LLM | GCP Vertex AI (Gemini) | Called over HTTPS from EC2 |
| Ticketing | ManageEngine ServiceDesk Plus | Self-hosted AWS, REST API |
| Notifications | AWS SES | email-smtp.ap-south-1.amazonaws.com → awsalerts@aeonx.digital |
| Secrets | AWS SSM Parameter Store | /aeonx/ai-agent/* |
| Audit | AWS S3 | aeonx-ai-agent-incidents/ |
| IaC | Terraform | Phase 6 |
| CI/CD | GitHub Actions | Cloud-AeonX-Digital / AI-Adoption-Team |
| AWS Account | 761685920937 (Aeonx payer) | Region: ap-south-1 |
| IAM Role | aeonx-ai-agent-role | Files in iam/ |
| Client accounts | 158 accounts | Aeonx-L2-Role exists in each |

**Not in scope:** PagerDuty, Opsgenie, Datadog, Grafana, Prometheus, Slack

---

## 🏗️ Architecture Decision: Lambda + EC2 (not Lambda-only)

- **Lambda 1** = thin ingestor only (receive Zabbix webhook → normalize → forward to EC2)
- **EC2 t3.small** = persistent AI agent service (FastAPI) — handles AI calls, remediation, and future client GUI `/chat` endpoint
- This avoids Lambda timeout limits for AI calls and gives a single service that grows with every phase

---

## 📍 Phase Status

| Phase | Title | Status |
|-------|-------|--------|
| Phase 1 | Foundation & Signal Ingestion | ✅ Code complete — pending infra deployment |
| Phase 2 | AI Classification & Decision Engine | ✅ Code complete — pending GCP setup |
| Phase 3 | Auto-Remediation Layer | 🔲 Pending |
| Phase 4 | Ticketing & Notification | 🔲 Pending |
| Phase 5 | Memory & RAG Layer | 🔲 Pending |
| Phase 6 | CI/CD & Deployment Ops | 🔲 Pending |
| Phase 7 | Observability & Audit | 🔲 Pending |
| Phase 8 | Risks & Guardrails | 🔲 Pending |
| Phase 9 | Client-Facing GUI (Option A) | 🔲 Pending |

---

## 🚧 Current Blockers (infrastructure — code is ready)

| Blocker | Action | Status |
|---------|--------|--------|
| IAM role `aeonx-ai-agent-role` | Create using `iam/` files | ⏳ Mrinal |
| EC2 t3.small launch | Private subnet, assign role, run `agent/setup.sh` | ⏳ Mrinal |
| S3 bucket `aeonx-ai-agent-incidents` | Create with versioning + lifecycle policy | ⏳ Mrinal |
| Lambda 1 deploy | Run `lambda/alert-ingestor/deploy.sh` with SUBNET_ID + SG_ID | ⏳ After EC2 up |
| Zabbix Gen-AI action update | Change operation → Lambda 1 webhook URL | ⏳ After Lambda deployed |
| GCP project + Vertex AI | Create project, enable API, create service account | ⏳ Mrinal |
| GCP service account key → SSM | Store JSON at `/aeonx/ai-agent/gcp-service-account-key` | ⏳ After GCP project |
| ManageEngine API key | Admin → API → generate key | ⏳ Mrinal (Phase 4) |

---

## 🔑 Zabbix (already queried — do not re-query)

- API: `https://cloud-monitor.aeonx.support/api_jsonrpc.php`
- 706 hosts, ~90 client host groups
- "Gen-AI" action (actionid: 14): fires Average/High/Disaster, currently sends email
- **Phase 1 change:** update action operation → HTTP POST to Lambda 1 URL
- Top auto-resolvable alerts: Website Down (19x/wk), High Memory (29x/wk), Service not running (9x/wk)

---

## 🤖 AI Working Instructions

1. Read `PROGRESS.md` for current phase status and blockers
2. Do not re-ask questions already answered above
3. Build one phase at a time — validate before moving forward
4. All secrets → SSM Parameter Store, never hardcoded
5. EC2/VM restart → always check `auto-restart=true` tag first
6. Confidence < 0.75 → always escalate, never auto-act
7. Tone: Senior SRE / Cloud Architect — technical, concise

---

## 🌿 Branch Convention

- Day-to-day: `mrinal-dev`
- Per phase: `phase/<number>-<short-title>`
- Each phase → PR → reviewed → merged to `main`

---

## 📝 Resume Prompt

```
Read CLAUDE.md in Cloud-AeonX-Digital/cloud-ai-adoption.
We are building an autonomous AI ops agent for AeonX (706 hosts, AWS+GCP).
Stack and decisions are confirmed in CLAUDE.md — do not re-ask.
Check PROGRESS.md for current phase status and blockers, then continue.
```
