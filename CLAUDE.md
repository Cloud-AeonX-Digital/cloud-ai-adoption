# CLAUDE.md — AI Session Context & Working Instructions

> This file configures AI assistant sessions (Claude/Kiro) for this project.
> Anyone picking up this repo can resume work with full context.

---

## 🧠 Project Context

**Repo:** `Cloud-AeonX-Digital/cloud-ai-adoption`
**Owner:** Mrinal-AeonX
**Goal:** Design a complete AI adoption strategy for SRE & DevOps operations across AWS and GCP.

The strategy is being built **iteratively, section by section**, with each phase reviewed before moving to the next.

---

## 📍 Current Status

| Phase | Title | Status |
|-------|-------|--------|
| Phase 1 | Current State Analysis | 🔲 Pending |
| Phase 2 | AI Use Cases for SRE / DevOps | 🔲 Pending |
| Phase 3 | Architecture Design | 🔲 Pending |
| Phase 4 | AI System Design | 🔲 Pending |
| Phase 5 | Automation Workflows | 🔲 Pending |
| Phase 6 | Tooling Recommendations | 🔲 Pending |
| Phase 7 | Implementation Roadmap | 🔲 Pending |
| Phase 8 | Risks & Guardrails | 🔲 Pending |

Update this table as phases are completed.

---

## 🎯 Problem Statement

Production cloud team (AWS + GCP) facing:
- High alert volume, manual triaging
- Slow RCA
- Repetitive tickets and escalations
- No intelligent signal correlation
- On-call fatigue

---

## 🤖 AI Working Instructions

When resuming this session, the AI assistant should:

1. **Read `README.md`** to understand current phase status
2. **Work one phase at a time** — do not jump ahead
3. **Ask for validation** after each phase before proceeding
4. **Output format:** Clear sections, ASCII architecture diagrams where needed, actionable content
5. **Tone:** Senior SRE / Cloud Architect — technical, precise, production-aware
6. **Constraints to always respect:**
   - Must work across both AWS and GCP
   - Reliability and safety over automation speed
   - Prefer incremental adoption over "big bang" changes
   - Production-grade assumptions throughout

---

## 🌿 Branch & PR Convention

- Branch naming: `phase/<number>-<short-title>`
  - e.g., `phase/1-current-state-analysis`
- One PR per phase
- PR description should summarize: what was added, key decisions made, open questions

---

## 🛠️ Stack Assumptions (to be validated per phase)

- **Monitoring:** AWS CloudWatch, GCP Cloud Monitoring, Prometheus, Grafana, Datadog
- **Alerting:** PagerDuty / Opsgenie
- **ChatOps:** Slack
- **AI/LLM:** AWS Bedrock, GCP Vertex AI, OpenAI API
- **Storage/Indexing:** OpenSearch, BigQuery, Elastic
- **IaC:** Terraform

---

## 👥 Team

- **Repo Owner:** Mrinal-AeonX
- **Org:** Cloud-AeonX-Digital
- **Collaboration:** All team members work via PRs against `main`

---

## 📝 Session Resume Prompt

To resume this project in a new AI session, use:

```
Read CLAUDE.md and README.md in this repo. We are building a Cloud AI Adoption Strategy for SRE/DevOps operations across AWS and GCP, iteratively phase by phase. Check the current status table in CLAUDE.md and continue from the next pending phase.
```
