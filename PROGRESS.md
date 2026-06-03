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
**Status:** ✅ Code Complete — Pending Deployment | **Branch:** mrinal-dev | **PR:** #3 merged to main

**Goal:** Zabbix alert → Lambda 1 (normalize) → EC2 agent `/alert` endpoint.

**Key Outputs:**
- `lambda/alert-ingestor/handler.py` — receives Zabbix webhook, normalizes to standard schema, forwards to EC2
- `lambda/alert-ingestor/deploy.sh` — one-command deploy, outputs webhook URL for Zabbix
- `agent/app/main.py` — FastAPI service, `POST /alert` + `GET /health`
- `agent/app/models.py` — Pydantic schemas matching Lambda output exactly
- `agent/app/dedup.py` — 30-min TTL dedup (Gap #8 resolved)
- `agent/aeonx-agent.service` — systemd unit, auto-restart (Gap #4 resolved)
- `agent/setup.sh` — one-command EC2 setup
- `zabbix-webhook-payload.md` — exact payload structure documented (Gap #7 resolved)
- `iam/` — trust policy + permission policy (Gap #5 resolved, S3 permission added)

**Decisions Made:**
- AWS account: `761685920937`, region: `ap-south-1`
- IAM role: `aeonx-ai-agent-role`, ExternalId: `aeonx-ai-agent-2026`
- EC2 size: `t3.small`, single uvicorn worker (for dedup consistency)
- Secrets path: `/aeonx/ai-agent/*` in SSM

**Pending (infrastructure — not blocking code):**
- ⏳ Create `aeonx-ai-agent-role` in AWS using `iam/` files
- ⏳ Launch EC2 t3.small, assign role, run `agent/setup.sh`
- ⏳ Create S3 bucket `aeonx-ai-agent-incidents` (Gap #6)
- ⏳ Deploy Lambda 1 via `lambda/alert-ingestor/deploy.sh`
- ⏳ Update Zabbix "Gen-AI" action → Lambda 1 webhook URL

**Handed to Phase 2:**
- Normalized alert schema confirmed (see `agent/app/models.py`)
- EC2 agent `/alert` endpoint ready to receive and process
- GCP project ID + Vertex AI service account key needed in SSM before Phase 2 activates

---

### Phase 2 — AI Classification & Decision Engine
**Status:** ✅ Code Complete — Pending GCP Setup | **Branch:** mrinal-dev | **PR:** #3 merged to main

**Key Outputs:**
- `agent/app/classifier.py` — Gemini (Vertex AI) call, confidence threshold, safe fallback to escalate
- `agent/app/notifier.py` — SES email with full incident + AI summary
- `agent/app/logger.py` — S3 incident log writer (date-partitioned JSON)
- `agent/requirements.txt` — pinned deps: fastapi, uvicorn, pydantic, boto3, google-auth

**Decisions Made:**
- Gemini model: `gemini-1.5-flash`
- Confidence threshold: 0.75 (env var `CONFIDENCE_THRESHOLD`)
- GCP location: `us-central1` (env var `GCP_LOCATION`)
- Credential caching: service account token cached in memory, refreshed on expiry (no SSM re-fetch every hour)
- All failures non-fatal: SES/S3 errors logged but don't crash the request

**Pending (infrastructure):**
- ⏳ Create GCP project + enable Vertex AI API
- ⏳ Create GCP service account (`Vertex AI User` role) → store JSON key in SSM `/aeonx/ai-agent/gcp-service-account-key`
- ⏳ Set `GCP_PROJECT_ID` in systemd service file before deploying

---

### Phase 3 — Auto-Remediation Layer
**Status:** 🔲 Pending

**Inputs needed from Phase 2:**
- AI decision schema working: `{action, severity, category, summary, confidence}`
- Confidence threshold defined (default: 0.75)
- List of EC2 instances to tag `auto-restart=true`

---

### Phase 4 — Ticketing & Notification
**Status:** ✅ Code Complete — Pending SSM key storage | **Branch:** mrinal-dev

**Key Outputs:**
- `agent/app/ticketing.py` — full ManageEngine integration:
  - `find_open_ticket()` — duplicate prevention (Gap #11 resolved)
  - `create_ticket()` — creates with correct mandatory fields (category, subcategory, request_type, group, udf_pick_307)
  - `resolve_ticket()` — follows AeonX lifecycle: Open→Assigned→In Progress→Resolved
  - `add_note()` — adds worklog note to existing ticket
- `main.py` updated — ticketing wired into alert handling flow

**Lifecycle discovered (AeonX Life Cycle id:2):**
```
Open → Assigned (needs technician+group+subcategory)
     → In Progress (needs udf_pick_302)
     → Resolved (needs resolution+worklog)
     → Closed
```

**Field IDs confirmed from live API:**
- category: 601 (AWS Support)
- subcategory: 313 (Monitoring & Logging)
- request_type: 303 (AWS Support Incident)
- group: 615 (AWS Support Internal)
- requester: aws.automation@aeonx.digital (id: 4511)

**Pending:**
- ⏳ Store ManageEngine API key in SSM: `aws ssm put-parameter --name /aeonx/ai-agent/manageengine-api-key --value DDD251A1-B6B0-4801-A83E-C9200A12DF41 --type SecureString --region ap-south-1`
- ⏳ Confirm `udf_pick_302` valid values for In Progress transition

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
