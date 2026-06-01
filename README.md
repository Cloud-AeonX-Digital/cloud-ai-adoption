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

## 🏗️ Agent Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     SIGNAL INGESTION                         │
│                                                              │
│  Zabbix (706 hosts) ──► Webhook ──► AWS Lambda              │
│  CloudWatch Alarms  ──► SNS     ──► AWS Lambda              │
│  Client email       ──► SES     ──► (future phase)          │
└──────────────────────────┬──────────────────────────────────┘
                           │  normalized alert payload
┌──────────────────────────▼──────────────────────────────────┐
│                     AI AGENT CORE                            │
│                                                              │
│  GCP Vertex AI (Gemini)                                      │
│  ├── Classify: alert type, severity, affected service        │
│  ├── Match: known resolution pattern (RAG from past events)  │
│  └── Decide: auto-remediate / create ticket / escalate       │
└──────┬──────────────────────────┬───────────────────────────┘
       │                          │
┌──────▼──────┐          ┌────────▼────────────┐
│ AUTO-ACTION │          │   HUMAN LOOP         │
│             │          │                      │
│ EC2 restart │          │ ManageEngine ticket  │
│ GCP VM      │          │ auto-created         │
│ restart     │          │                      │
│ (allowlist  │          │ SES email summary    │
│  tag-gated) │          │ → awsalerts@aeonx    │
└──────┬──────┘          └────────┬─────────────┘
       │                          │
       └────────────┬─────────────┘
                    │
         ┌──────────▼──────────┐
         │   AUDIT & MEMORY     │
         │                      │
         │  S3 — incident log   │
         │  SSM — secrets/config│
         │  RAG store — past    │
         │  incidents for AI    │
         └──────────────────────┘
```

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

**Goal:** Wire Zabbix and CloudWatch alerts into a unified Lambda-based normalizer. No AI yet — just reliable signal capture.

**Components:**
- Zabbix webhook → Lambda (reuse existing "Gen-AI" action, change target from email to webhook)
- CloudWatch SNS → Lambda
- Alert normalizer: maps both sources to a standard schema
- Output: normalized JSON event to SQS queue for AI layer

**Status:** 🔄 In Progress

**Blockers:**
- ⏳ IAM role creation (`aeonx-ai-agent-role`) — policy files ready in `iam/`
- ⏳ ManageEngine API key
- ⏳ GCP project ID for Vertex AI

---

## Phase 2 — AI Classification & Decision Engine

**Goal:** Vertex AI (Gemini) receives normalized alerts and returns: severity classification, alert category, recommended action (auto-fix / ticket / escalate).

**Components:**
- GCP Cloud Function — Vertex AI Gemini call
- Prompt template per alert category
- Decision output schema: `{action, severity, summary, confidence}`
- Fallback: if confidence < threshold → always escalate to human

**Status:** 🔲 Pending (blocked on GCP project)

---

## Phase 3 — Auto-Remediation Layer

**Goal:** Execute safe, tag-gated automated fixes for known alert patterns.

**Auto-resolvable patterns identified (from Zabbix data):**
| Alert | Frequency | Action |
|-------|-----------|--------|
| Website Down | 19x/week | Health check → EC2/VM restart if needed |
| High Memory >90% Linux/Windows | 29x/week | Alert + restart if critical |
| AWS Replication Service not running | 9x/week | Service restart via SSM Run Command |
| Zabbix agent not available | 6x/week | EC2/VM restart |

**Safety constraint:** EC2/GCP VM restart only for instances tagged `auto-restart=true`

**Status:** 🔲 Pending

---

## Phase 4 — Ticketing & Notification

**Goal:** Auto-create, update, and close ManageEngine ServiceDesk Plus tickets. Send SES email summaries.

**Components:**
- ManageEngine API integration (ticket create/update/close)
- SES email: incident summary → awsalerts@aeonx.digital
- Auto-close ticket when remediation verified successful

**Status:** 🔲 Pending (blocked on ManageEngine API key)

---

## Phase 5 — Memory & RAG Layer

**Goal:** Store every incident + resolution in a searchable store. Feed into AI context for better classification over time.

**Components:**
- S3 bucket: structured incident log (JSON per event)
- Vector index: past incidents for RAG retrieval
- Gemini uses past similar incidents as context when classifying new alerts

**Status:** 🔲 Pending

---

## Phase 6 — CI/CD & Deployment Ops

**Goal:** GitHub Actions pipelines for agent deployment and client infrastructure operations.

**Components:**
- GitHub Actions under `Cloud-AeonX-Digital` org, `AI-Adoption-Team`
- Lambda deploy pipeline
- Terraform plan/apply pipeline for client infra changes

**Status:** 🔲 Pending

---

## Phase 7 — Observability & Audit

**Goal:** Full visibility into what the agent is doing, why, and what it changed.

**Components:**
- CloudWatch dashboard: agent actions, alert volumes, auto-remediation rate
- Audit log: every action with timestamp, alert ID, decision, outcome
- Weekly digest email: summary of alerts handled, auto-resolved, escalated

**Status:** 🔲 Pending

---

## Phase 8 — Risks & Guardrails

**Goal:** Ensure the agent cannot cause more damage than it prevents.

**Key guardrails:**
- EC2/VM restart: tag-gated (`auto-restart=true`) — opt-in per instance
- AI confidence threshold: actions below threshold always escalate
- No destructive actions (terminate, delete, scale-down) — ever
- All actions logged and reversible
- Human override: any ticket can be flagged to pause agent actions

**Status:** 🔲 Pending

---

## 🛠️ Tech Stack (Confirmed)

| Layer | Tool |
|-------|------|
| Monitoring | Zabbix (self-hosted, AWS) + CloudWatch |
| Alert ingestion | AWS Lambda (ap-south-1) |
| AI/LLM | GCP Vertex AI — Gemini |
| Ticketing | ManageEngine ServiceDesk Plus (self-hosted, AWS) |
| Notifications | AWS SES (email-smtp.ap-south-1.amazonaws.com) |
| Secrets | AWS SSM Parameter Store |
| Audit storage | AWS S3 |
| IaC | Terraform |
| CI/CD | GitHub Actions |
| IAM | `aeonx-ai-agent-role` (ap-south-1, account 761685920937) |

---

## 📌 Constraints

- Payer AWS account (`761685920937`) — minimal IAM footprint, no console access needed
- EC2/VM auto-restart: allowlist only, tag-gated
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
