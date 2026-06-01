# AeonX AI Ops Agent — Cloud Monitoring, Support & Deployment Automation

> Autonomous AI agent for monitoring, incident response, and operations across AWS and GCP.
> Human intervention only where required.

---

## 🎯 Objective

Build a production-grade AI agent that autonomously handles monitoring alerts, incident triage, root cause analysis, ticket creation, and safe auto-remediation across all AeonX client environments (AWS + GCP) — with human escalation only for edge cases.

**Pain points being solved:**
- 706 monitored hosts across ~90 client accounts — all alerts routed to a single email inbox
- Manual triage, troubleshooting, and server restarts for every alert
- No correlation between alerts, logs, and past incidents
- On-call fatigue across a 20–25 person team
- Repetitive client communication after every incident

**Target outcomes:**
- AI classifies and triages every Zabbix/CloudWatch alert automatically
- Known patterns (website down, high memory, service stopped) auto-remediated without human touch
- ManageEngine ticket auto-created, updated, and closed per incident
- Incident summary auto-sent via SES to team + client
- Human paged only for unknown/high-risk situations
- Full audit trail of every action taken

---

## 🏗️ Final Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  SIGNAL SOURCES                                                      │
│                                                                      │
│  Zabbix (706 hosts, self-hosted AWS)                                │
│  └── "Gen-AI" action → HTTP webhook                                 │
│                                                                      │
│  CloudWatch Alarms (per client AWS account)          [future]       │
│  └── SNS → Lambda trigger                                           │
│                                                                      │
│  Client Chat GUI                                     [future]       │
│  └── HTTPS → AI Agent API                                           │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  AI AGENT CORE                                                       │
│                                                                      │
│  Lambda 1 — Alert Ingestor  (AWS Lambda, ap-south-1)                │
│  ├── Receives Zabbix webhook POST                                    │
│  ├── Normalizes to standard schema                                   │
│  └── HTTP POST → EC2 AI Agent Service                               │
│                                                                      │
│  EC2 — AI Decision Engine  (t3.small, ap-south-1)                   │
│  FastAPI / Python                                                    │
│  ├── POST /alert  — classify, decide, act                           │
│  └── POST /chat   — client self-service Q&A          [future]       │
└──────┬──────────────────────────────┬───────────────────────────────┘
       │                              │
       ▼                              ▼
┌──────────────────┐       ┌──────────────────────────┐
│  GCP             │       │  NOTIFICATIONS            │
│                  │       │                           │
│  Vertex AI       │       │  AWS SES                  │
│  (Gemini)        │       │  → awsalerts@aeonx.digital│
│  ├── Classify    │       │    (ops team)             │
│  ├── Summarize   │       │  → client email [future]  │
│  └── Q&A [fut.]  │       └──────────────────────────┘
└──────────────────┘                  │
       │                              ▼
       │                   ┌──────────────────────────┐
       │                   │  TICKETING    [Phase 4]   │
       │                   │                           │
       │                   │  ManageEngine             │
       │                   │  ServiceDesk Plus         │
       │                   │  auto create/update/close │
       │                   └──────────────────────────┘
       │                              │
       └──────────────┬───────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│  CLOUD INTEGRATIONS                                  [Phase 3]       │
│                                                                      │
│  AWS                                                                 │
│  ├── EC2 restart (tag-gated: auto-restart=true)                     │
│  ├── SSM Run Command (service restart)                              │
│  └── Cross-account via Aeonx-L2-Role (×158 client accounts)        │
│                                                                      │
│  GCP                                                                 │
│  └── GCP VM restart (allowlist-gated)                               │
└─────────────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│  AUDIT & MEMORY                                                      │
│                                                                      │
│  S3: aeonx-ai-agent-incidents/  — full incident log (JSON)         │
│  SSM Parameter Store            — all secrets + config              │
│  CloudWatch Logs                — Lambda + EC2 agent logs           │
└─────────────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│  CLIENT-FACING GUI                                       [future]    │
│                                                                      │
│  Option A: Chat widget → POST /chat on AI Agent Service             │
│  └── "Is my server up?" → agent queries S3 + Zabbix API            │
│                                                                      │
│  Option B: Full self-service portal (ECS Fargate)        [later]    │
│  └── Per-client auth, incident history, ticket status, chat        │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  CI/CD                                                               │
│  GitHub Actions (Cloud-AeonX-Digital / AI-Adoption-Team)           │
│  └── Deploy Lambda + EC2 agent + infra changes via Terraform        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🧩 Component Summaries

### Signal Sources
Alerts enter the system from two sources today, with a third planned:
- **Zabbix** — self-hosted on AWS, monitors 706 hosts across ~90 client accounts. The existing "Gen-AI" action (already configured) fires on Average/High/Disaster severity and will be pointed at Lambda 1 instead of email.
- **CloudWatch** *(future)* — per-client AWS account alarms routed via SNS into the same Lambda ingestor.
- **Client Chat GUI** *(future)* — clients send questions directly to the agent via a chat widget.

### Lambda 1 — Alert Ingestor
Thin, stateless AWS Lambda function. Receives the raw Zabbix webhook POST, normalizes it into a standard JSON schema (source, host, client, alert type, severity), and forwards it to the EC2 AI Agent Service. Costs nothing when idle.

### EC2 AI Decision Engine
Persistent FastAPI/Python service running on a `t3.small` EC2 in `ap-south-1`. This is the brain of the agent — it receives normalized alerts, calls Vertex AI (Gemini) for classification and decision, then routes the outcome to notifications, ticketing, or remediation. The `/chat` endpoint will serve the client-facing GUI in a future phase without any new infrastructure.

### GCP — Vertex AI (Gemini)
The AI/LLM layer. The EC2 agent calls Gemini with the alert context and receives a structured decision: `{action, severity, category, summary, confidence}`. If confidence is below threshold, the agent always escalates to human rather than acting autonomously.

### Notifications — AWS SES
Every alert processed by the agent triggers an email summary to `awsalerts@aeonx.digital` via AWS SES (`email-smtp.ap-south-1.amazonaws.com`). Summary includes: what happened, which client/host, AI-assessed severity, and what action was taken or recommended.

### Ticketing — ManageEngine ServiceDesk Plus *(Phase 4)*
Auto-creates a ticket when the agent decides human review is needed or when auto-remediation is attempted. Updates the ticket with action taken. Closes it when the issue is verified resolved. Runs on AeonX's self-hosted ManageEngine instance via REST API.

### Cloud Integrations — AWS + GCP *(Phase 3)*
Safe, gated automated actions:
- **EC2 restart** — only on instances tagged `auto-restart=true`
- **SSM Run Command** — service restarts on allowlisted instances
- **Cross-account** — agent assumes `Aeonx-L2-Role` in each of the 158 client accounts to act within their environment
- **GCP VM restart** — allowlist-gated, same safety model as EC2

### Audit & Memory
Every alert, AI decision, and action taken is written to S3 as a structured JSON record. SSM Parameter Store holds all secrets (API keys, GCP service account). CloudWatch captures all Lambda and EC2 agent logs. This store feeds the RAG layer in Phase 5 so the agent learns from past incidents.

### Client-Facing GUI *(future)*
- **Option A** (first): A chat widget where clients ask questions like "Is my server up?" or "What happened last night?" — the agent answers from S3 incident history and live Zabbix data via the `/chat` endpoint on the existing EC2 service.
- **Option B** (later): Full self-service portal on ECS Fargate with per-client authentication, incident history, ticket status, and chat.

### CI/CD
GitHub Actions pipelines under `Cloud-AeonX-Digital / AI-Adoption-Team` handle all deployments — Lambda code updates, EC2 agent deployments, and Terraform infrastructure changes. No manual deployments.

---

## 📋 Build Phases

| Phase | Title | Status |
|-------|-------|--------|
| [Phase 1](#phase-1--foundation--signal-ingestion) | Foundation & Signal Ingestion | 🔄 In Progress |
| [Phase 2](#phase-2--ai-classification--decision-engine) | AI Classification & Decision Engine | 🔲 Pending |
| [Phase 3](#phase-3--auto-remediation-layer) | Auto-Remediation Layer | 🔲 Pending |
| [Phase 4](#phase-4--ticketing--notification) | Ticketing & Notification | 🔲 Pending |
| [Phase 5](#phase-5--memory--rag-layer) | Memory & RAG Layer | 🔲 Pending |
| [Phase 6](#phase-6--cicd--deployment-ops) | CI/CD & Deployment Ops | 🔲 Pending |
| [Phase 7](#phase-7--observability--audit) | Observability & Audit | 🔲 Pending |
| [Phase 8](#phase-8--risks--guardrails) | Risks & Guardrails | 🔲 Pending |

---

## Phase 1 — Foundation & Signal Ingestion

**Goal:** Wire Zabbix alerts into Lambda 1 (normalizer) → EC2 AI Agent Service. No AI yet — just reliable signal capture and forwarding.

**Components:**
- Lambda 1: receives Zabbix webhook, normalizes to standard schema, POSTs to EC2
- EC2 t3.small: FastAPI skeleton with `/alert` endpoint
- Zabbix "Gen-AI" action: change operation from email → webhook URL (Lambda 1)

**Status:** 🔄 In Progress

**Blockers:**
- ⏳ IAM role `aeonx-ai-agent-role` — policy files ready in `iam/`
- ⏳ GCP project ID for Vertex AI
- ⏳ ManageEngine API key

---

## Phase 2 — AI Classification & Decision Engine

**Goal:** EC2 agent calls Vertex AI (Gemini) per alert and returns a structured decision.

**Components:**
- GCP project + Vertex AI API enabled
- GCP service account key in SSM
- Gemini prompt template per alert category
- Decision schema: `{action, severity, category, summary, confidence}`
- SES email with AI-generated summary on every alert

**Status:** 🔲 Pending (blocked on GCP project)

---

## Phase 3 — Auto-Remediation Layer

**Goal:** Execute safe, tag-gated automated fixes for known alert patterns.

**Auto-resolvable patterns (from live Zabbix data):**
| Alert | Frequency | Action |
|-------|-----------|--------|
| Website Down | 19x/week | Health check → EC2/VM restart |
| High Memory >90% Linux/Windows | 29x/week | Restart if critical |
| AWS Replication Service not running | 9x/week | SSM Run Command service restart |
| Zabbix agent not available | 6x/week | EC2/VM restart |

**Safety:** EC2/VM restart only for instances tagged `auto-restart=true`. Cross-account via `Aeonx-L2-Role`.

**Status:** 🔲 Pending

---

## Phase 4 — Ticketing & Notification

**Goal:** Auto-create, update, and close ManageEngine tickets. Send SES summaries.

**Status:** 🔲 Pending (blocked on ManageEngine API key)

---

## Phase 5 — Memory & RAG Layer

**Goal:** Index every incident + resolution. Feed into Gemini context for improving classification over time.

**Status:** 🔲 Pending

---

## Phase 6 — CI/CD & Deployment Ops

**Goal:** GitHub Actions pipelines for agent deployment and client infra operations.

**Status:** 🔲 Pending

---

## Phase 7 — Observability & Audit

**Goal:** CloudWatch dashboard, audit log, weekly digest email.

**Status:** 🔲 Pending

---

## Phase 8 — Risks & Guardrails

**Goal:** Ensure the agent cannot cause more damage than it prevents.

**Key guardrails:**
- EC2/VM restart: tag-gated (`auto-restart=true`) — opt-in per instance
- AI confidence threshold: actions below threshold always escalate
- No destructive actions (terminate, delete, scale-down) — ever
- All actions logged and reversible

**Status:** 🔲 Pending

---

## 🛠️ Tech Stack

| Layer | Tool |
|-------|------|
| Monitoring | Zabbix (self-hosted, AWS) + CloudWatch |
| Alert ingestor | AWS Lambda (ap-south-1) |
| AI Decision Engine | EC2 t3.small — FastAPI/Python (ap-south-1) |
| AI/LLM | GCP Vertex AI — Gemini |
| Ticketing | ManageEngine ServiceDesk Plus (self-hosted, AWS) |
| Notifications | AWS SES (email-smtp.ap-south-1.amazonaws.com) |
| Secrets | AWS SSM Parameter Store |
| Audit storage | AWS S3 |
| IaC | Terraform |
| CI/CD | GitHub Actions |
| IAM | `aeonx-ai-agent-role` (ap-south-1, account 761685920937) |

---

## ✅ Master To-Do List

> See [GAPS.md](./GAPS.md) for known gaps and loopholes with fix details.

### Pre-Build Fixes (before writing any code)
1. Fix duplicate IAM permissions in `iam/agent-permission-policy.json` (Gap #5)
2. Capture Zabbix webhook sample payload — needed to write Lambda 1 normalizer (Gap #7)
3. Verify SES sender address `awsalerts@aeonx.digital` in AWS SES console (Gap #3)

### Infrastructure Setup
4. Create GCP project + enable Vertex AI API
5. Create GCP service account with `Vertex AI User` role → download JSON key
6. Create second GCP service account with `Compute Instance Admin` role (for Phase 3 GCP VM restart) (Gap #9)
7. Store Vertex AI GCP key in SSM: `/aeonx/ai-agent/gcp-service-account-key`
8. Fix duplicate permissions in `iam/agent-permission-policy.json` then create IAM role `aeonx-ai-agent-role`
9. Define VPC, subnet, and security group for EC2 agent (Gap #2)
10. Launch EC2 t3.small in ap-south-1 (private subnet), assign `aeonx-ai-agent-role`
11. Create S3 bucket `aeonx-ai-agent-incidents` with lifecycle policy + versioning (Gap #6)

### Phase 1 — Signal Ingestion
12. Add webhook secret validation to Lambda 1 design (Gap #1)
13. Write Lambda 1 (alert ingestor + normalizer) — place in same VPC as EC2
14. Deploy Lambda 1 via GitHub Actions
15. Write FastAPI skeleton on EC2 (`POST /alert` endpoint)
16. Configure systemd service for FastAPI agent on EC2 (Gap #4)
17. Add alert deduplication logic: `trigger_id + host + 30-min window` (Gap #8)
18. Update Zabbix "Gen-AI" action: change operation from email → Lambda 1 webhook URL
19. Test: trigger a test alert in Zabbix → verify Lambda 1 receives + normalizes it

### Phase 2 — AI Classification
20. Write Gemini prompt template for alert classification
21. Wire EC2 agent `/alert` → Vertex AI call → structured decision
22. Write SES email formatter (AI summary → team email)
23. Test end-to-end: Zabbix alert → Lambda → EC2 → Gemini → SES email

### Phase 3 — Auto-Remediation
24. Add `auto-restart=true` tag to allowlisted EC2 instances
25. Write EC2 restart executor (tag check → stop → start → health verify → 30-min cooldown)
26. Write SSM Run Command executor (service restart)
27. Add trust policy to `Aeonx-L2-Role` in client accounts (script for all 158)
28. Wire GCP Compute service account for GCP VM restart
29. Test: simulate "Website Down" alert → verify auto-restart fires only on tagged instances

### Phase 4 — Ticketing
30. Obtain ManageEngine API key
31. Write ManageEngine ticket create/update/close integration
32. Add duplicate ticket check: query open tickets for same host+alert before creating (Gap #11)
33. Wire: AI decision → ticket created → remediation result → ticket closed
34. Test: full flow with real ManageEngine ticket

### Phase 5 — Memory & RAG
35. Set up S3 incident log writer (JSON per event)
36. Set up vector index on GCS for past incidents
37. Wire RAG context into Gemini prompt

### Phase 6 — CI/CD
38. GitHub Actions: Lambda deploy pipeline
39. GitHub Actions: EC2 agent deploy pipeline
40. GitHub Actions: Terraform plan/apply pipeline

### Phase 7 — Observability & Audit
41. CloudWatch dashboard: alert volumes, auto-remediation rate, agent health
42. Audit log: every action with timestamp, alert ID, decision, outcome
43. Weekly digest email via SES

### Phase 8 — Risks & Guardrails
44. Document and enforce all guardrails (confidence threshold, tag-gate, no destructive actions)
45. Load test: simulate burst of 50 alerts → verify no duplicate processing

### Phase 9 — Client GUI (Option A)
46. Design client identity + data scoping for `/chat` endpoint (Gap #10)
47. Add `POST /chat` endpoint to EC2 agent
48. Build simple chat widget (HTML/JS)
49. Wire: client question → Gemini + S3 incident history → answer

---

## 📌 Constraints

- Payer AWS account (`761685920937`) — minimal IAM footprint
- EC2/VM auto-restart: allowlist only, tag-gated (`auto-restart=true`)
- GCP Vertex AI: preferred LLM provider
- No "big bang" — each phase independently deployable and rollback-safe
- All secrets via SSM Parameter Store — never hardcoded

---

## 🤝 Contributing

- Working branch: `mrinal-dev`
- Branch naming for phases: `phase/<number>-<short-title>`
- Each phase gets its own PR into `main`
- See [CLAUDE.md](./CLAUDE.md) for AI session resume instructions
- See [PROGRESS.md](./PROGRESS.md) for phase handoff context
- See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed system design

---

## 🤖 Sharing AI Context with the Team

| # | Method | How | Best For |
|---|--------|-----|----------|
| 1 | **Kiro Steering file** | `.kiro/steering/your-feature.md` | Auto-loaded rules/conventions for everyone |
| 2 | **Kiro Custom agent** | `.kiro/agents/your-feature.json` | Full workflow with tools, hooks, prompts |
| 3 | **Kiro Skill file** | `.kiro/skills/your-feature.md` | On-demand reference material |
| 4 | **Kiro Hook scripts** | Committed alongside agent config | Automation at trigger points |
| 5 | **KIRO_HOME shared directory** | Point `KIRO_HOME` env var to shared path | Global agents/steering for whole team |
| 6 | **GitHub versioned `.md` file** | Standalone doc in this repo | Manual reference; no Kiro required |

**Current approach:** Option 6 — `CLAUDE.md` for session config, `PROGRESS.md` for phase handoffs. Kiro steering/agent files added as phases mature.
