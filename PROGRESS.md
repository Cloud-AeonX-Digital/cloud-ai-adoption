# PROGRESS.md — Phase Summaries & Handoff Context

> Essential decisions and outputs only. No troubleshooting notes or exploratory context.
> Each phase reads only what it needs from previous phases.

---

## Template

```
### Phase N — <Title>
**Status:** ✅ Complete / 🔄 In Progress / 🔲 Pending
**Branch:** phase/N-short-title | PR: #N

**Key Outputs:** what was produced
**Decisions Made:** architectural/strategic choices locked in
**Handed to Phase N+1:** only what the next phase needs
**Blockers:** unresolved items
```

---

## Phase Summaries

---

### Phase 0 — Project Setup
**Status:** ✅ Complete | **Branch:** mrinal-dev

**Key Outputs:**
- Repo: `Cloud-AeonX-Digital/cloud-ai-adoption`, team `AI-Adoption-Team`, branch `mrinal-dev`
- `README.md`, `CLAUDE.md`, `PROGRESS.md`, `ARCHITECTURE.md` committed
- IAM policy files in `iam/`

**Decisions Made:**
- Pivot from "strategy document" to "actually building the agent"
- Iterative build: one phase at a time, PR per phase into `main`
- Sharing method: GitHub versioned `.md` files as baseline; Kiro steering files added as phases mature

**Handed to Phase 1:**
- Confirmed stack (see CLAUDE.md)
- Zabbix API accessible, "Gen-AI" action exists and can be repurposed
- IAM role policy files ready to deploy

---

### Phase 1 — Foundation & Signal Ingestion
**Status:** 🔄 In Progress | **Branch:** mrinal-dev

**Goal:** Wire Zabbix + CloudWatch alerts into a unified Lambda normalizer. No AI yet — reliable signal capture only.

**Key Findings:**
- 706 hosts, ~90 client groups in Zabbix
- Only active alert channel: AWS SES → awsalerts@aeonx.digital
- Zabbix "Gen-AI" action (actionid: 14) already exists — fires on Average/High/Disaster
  - Currently: sends email to 2 users
  - Plan: change to webhook → Lambda (zero disruption to existing setup)
- All other channels (Teams, ManageEngine webhook, Slack) are disabled — clean slate
- Top auto-resolvable alert patterns confirmed from live data:

| Alert | Weekly Frequency | Planned Action |
|-------|-----------------|----------------|
| Website Down | 19x | Health check → EC2/VM restart |
| High Memory >90% (Linux + Windows) | 29x | Restart if critical |
| AWS Replication Service not running | 9x | SSM Run Command service restart |
| Zabbix agent not available | 6x | EC2/VM restart |

**Decisions Made:**
- Reuse existing "Gen-AI" Zabbix action — change operation target from email to webhook
- EC2/VM restart gated on `auto-restart=true` tag — opt-in per instance
- AWS account: `761685920937`, region: `ap-south-1`
- IAM role: `aeonx-ai-agent-role`, ExternalId: `aeonx-ai-agent-2026`
- Secrets path: `/aeonx/ai-agent/*` in SSM Parameter Store

**IAM Files Ready:**
- `iam/trust-policy.json` — allows Lambda + account 761685920937 to assume role
- `iam/agent-permission-policy.json` — EC2 (tag-gated), SES, SSM, SNS, CloudWatch Logs

**Blockers:**
- ⏳ Mrinal to create `aeonx-ai-agent-role` using files in `iam/`
- ⏳ ManageEngine API key (read-only creds being created)
- ⏳ GCP project ID (Vertex AI — project not yet created)

**Next Steps (once unblocked):**
1. Create IAM role in AWS console/CLI using `iam/` policy files
2. Provide ManageEngine API key
3. Create GCP project → share project ID
4. Build Lambda alert normalizer (Zabbix webhook + CloudWatch SNS → standard schema)
5. Update Zabbix "Gen-AI" action: email → webhook URL

---

### Phase 2 — AI Classification & Decision Engine
**Status:** 🔲 Pending (blocked on GCP project)

**Inputs needed from Phase 1:**
- Lambda webhook URL (Zabbix → Lambda working)
- Normalized alert schema confirmed
- GCP project ID

---

### Phase 3 — Auto-Remediation Layer
**Status:** 🔲 Pending

**Inputs needed from Phase 2:**
- AI decision output schema: `{action, severity, summary, confidence}`
- Confidence threshold defined

---

### Phase 4 — Ticketing & Notification
**Status:** 🔲 Pending (blocked on ManageEngine API key)

**Inputs needed from Phase 3:**
- Remediation action results (success/fail)
- ManageEngine API key + base URL

---

### Phase 5 — Memory & RAG Layer
**Status:** 🔲 Pending

---

### Phase 6 — CI/CD & Deployment Ops
**Status:** 🔲 Pending

---

### Phase 7 — Observability & Audit
**Status:** 🔲 Pending

---

### Phase 8 — Risks & Guardrails
**Status:** 🔲 Pending
