# PROGRESS.md — Phase Summaries & Handoff Context

> This file tracks **only the essential output and decisions** from each phase.
> It is the single source of truth for passing context between phases and team members.
> Do NOT include troubleshooting steps, failed attempts, or exploratory notes here.

---

## How to Use This File

- After completing a phase, add a summary block below following the template
- The next phase should read only its **"Inputs from previous phases"** section — not the full history
- Keep each summary tight: decisions made, key outputs, open questions handed forward

---

## Phase Summary Template

```
### Phase N — <Title>
**Status:** ✅ Complete / 🔲 Pending / 🔄 In Progress
**Branch:** phase/N-short-title
**PR:** #<number>

**Key Outputs:**
- <bullet: what was produced>

**Decisions Made:**
- <bullet: architectural or strategic choices locked in>

**Assumptions Validated:**
- <bullet: stack/tooling assumptions confirmed or changed>

**Handed to Phase N+1:**
- <bullet: only what the next phase needs to know>

**Open Questions (if any):**
- <bullet: unresolved items for future phases>
```

---

## Phase Summaries

### Phase 0 — Project Setup
**Status:** ✅ Complete
**Branch:** mrinal-dev

**Key Outputs:**
- Repo created: `Cloud-AeonX-Digital/cloud-ai-adoption`
- Team assigned: `AI-Adoption-Team` (push access)
- Working branch: `mrinal-dev`
- `README.md` — full phase plan with contributing guide and AI sharing options
- `CLAUDE.md` — AI session config with resume prompt, stack assumptions, branch conventions
- `PROGRESS.md` — this file, for phase handoffs

**Decisions Made:**
- Iterative approach: one phase at a time, PR per phase
- Baseline sharing method: GitHub versioned `.md` files (`CLAUDE.md` + `PROGRESS.md`)
- Kiro steering/agent files to be added as phases mature

**Handed to Phase 1:**
- Stack assumptions to validate: CloudWatch, GCP Monitoring, Prometheus, Grafana, Datadog, PagerDuty, Slack
- Approach: map current state first, identify all human-intervention touchpoints before proposing AI solutions

---

### Phase 1 — Current State Analysis
**Status:** 🔄 In Progress

**Key Findings (Zabbix):**
- 706 hosts across ~90 client groups (all AWS accounts, some GCP)
- Only active alert channel: AWS SES Email → awsalerts@aeonx.digital
- "Gen-AI" action already exists in Zabbix (Average/High/Disaster severity) — currently just sends email, no AI connected
- Top repeating alerts (last 7 days): Website Down (19x), High Memory Linux/Windows (29x), Service not running (9x) — ~70% auto-resolvable
- All other channels (Teams, ManageEngine webhook, Slack) are disabled

**Pending — Blocked:**
- ManageEngine API key (read-only creds being created by Mrinal)
- GCP project ID (not yet created — Vertex AI will run here)

**IAM Role (ready to create):**
- Files: `iam/trust-policy.json` + `iam/agent-permission-policy.json`
- Role name to use: `aeonx-ai-agent-role`
- ExternalId: `aeonx-ai-agent-2026`
- EC2 restart restricted to instances tagged `auto-restart=true`
- Secrets stored via SSM Parameter Store under `/aeonx/ai-agent/*`

**Next steps once unblocked:**
1. Mrinal creates IAM role using the policy files above
2. Mrinal provides ManageEngine API key
3. Mrinal creates GCP project and shares project ID
4. Begin Lambda + Zabbix webhook wiring

---

### Phase 2 — AI Use Cases for SRE / DevOps
**Status:** 🔲 Pending

---

### Phase 3 — Architecture Design
**Status:** 🔲 Pending

---

### Phase 4 — AI System Design
**Status:** 🔲 Pending

---

### Phase 5 — Automation Workflows
**Status:** 🔲 Pending

---

### Phase 6 — Tooling Recommendations
**Status:** 🔲 Pending

---

### Phase 7 — Implementation Roadmap
**Status:** 🔲 Pending

---

### Phase 8 — Risks & Guardrails
**Status:** 🔲 Pending
