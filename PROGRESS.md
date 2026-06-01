# PROGRESS.md — Phase Summaries & Handoff Context

> Essential decisions and outputs only. No troubleshooting or exploratory notes.
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
- `README.md`, `CLAUDE.md`, `PROGRESS.md`, `ARCHITECTURE.md` — all current
- IAM policy files: `iam/trust-policy.json` + `iam/agent-permission-policy.json`

**Decisions Made:**
- Build the actual agent (not just a strategy doc)
- Lambda 1 (thin ingestor) → EC2 t3.small (persistent FastAPI agent) — not Lambda-only
- EC2 agent hosts both `/alert` (ops) and `/chat` (future client GUI) on same instance
- GCP Vertex AI (Gemini) as LLM — called over HTTPS from EC2
- 158 client accounts use existing `Aeonx-L2-Role` for cross-account remediation (Phase 3)
- Iterative build: one phase at a time, PR per phase

**Handed to Phase 1:**
- Zabbix "Gen-AI" action (actionid: 14) exists — just needs operation changed to webhook
- IAM role policy files ready to deploy
- Confirmed alert patterns for auto-remediation (see CLAUDE.md)

---

### Phase 1 — Foundation & Signal Ingestion
**Status:** 🔄 In Progress | **Branch:** mrinal-dev

**Goal:** Zabbix alert → Lambda 1 (normalize) → EC2 agent `/alert` endpoint. No AI yet.

**Key Findings:**
- 706 hosts, ~90 client groups in Zabbix
- Only active channel: AWS SES → awsalerts@aeonx.digital
- "Gen-AI" action already exists — change target from email to Lambda 1 webhook
- Top auto-resolvable patterns confirmed from live data (see CLAUDE.md)

**Decisions Made:**
- AWS account: `761685920937`, region: `ap-south-1`
- IAM role: `aeonx-ai-agent-role`, ExternalId: `aeonx-ai-agent-2026`
- EC2 size: `t3.small` — sufficient for current load, resize later if needed
- Secrets path: `/aeonx/ai-agent/*` in SSM

**Blockers:**
- ⏳ Create `aeonx-ai-agent-role` (files in `iam/`)
- ⏳ GCP project ID (Vertex AI)
- ⏳ ManageEngine API key

**Next Steps (once unblocked):**
1. Create IAM role in AWS
2. Launch EC2 t3.small, assign role
3. Write + deploy Lambda 1 (alert ingestor)
4. Write FastAPI skeleton on EC2 (`POST /alert`)
5. Update Zabbix "Gen-AI" action → Lambda 1 URL
6. Test: real Zabbix alert → Lambda → EC2

---

### Phase 2 — AI Classification & Decision Engine
**Status:** 🔲 Pending (blocked on GCP project)

**Inputs needed from Phase 1:**
- Lambda 1 URL (deployed and tested)
- EC2 agent running and reachable
- GCP project ID + Vertex AI enabled + service account key in SSM

---

### Phase 3 — Auto-Remediation Layer
**Status:** 🔲 Pending

**Inputs needed from Phase 2:**
- AI decision schema working: `{action, severity, category, summary, confidence}`
- Confidence threshold defined (default: 0.75)
- List of EC2 instances to tag `auto-restart=true`

---

### Phase 4 — Ticketing & Notification
**Status:** 🔲 Pending (blocked on ManageEngine API key)

**Inputs needed from Phase 3:**
- Remediation action results (success/fail)
- ManageEngine base URL + API key

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
