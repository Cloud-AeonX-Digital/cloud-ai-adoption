# GAPS.md — Known Gaps, Loopholes & Fixes

> Identified during architecture cross-check on 2026-06-01.
> All items must be resolved before or during the relevant phase.

---

## 🔴 Gaps & Loopholes

**1. Lambda 1 webhook endpoint has no authentication**
Zabbix POSTs to a public Lambda URL. Anyone who discovers the URL can flood it with fake alerts.
- **Resolution:** Lambda 1, EC2 agent, and Zabbix server are all in the same AWS account (`761685920937`). Lambda URL is kept private — not exposed publicly. EC2 security group restricts inbound to Zabbix server IP only.
- **Status:** ✅ Resolved

**2. EC2 agent network placement not defined**
Lambda 1 needs to reach the EC2 agent via HTTP POST. If EC2 is in a private subnet (recommended), Lambda must be in the same VPC or use a VPC endpoint. If EC2 is public-facing, that's a security risk.
- **Resolution:** All three components (Zabbix, Lambda 1, EC2 agent) in same AWS account and VPC. Private subnet, no public exposure.
- **Status:** ✅ Resolved

**3. SES sender address not verified**
`awsalerts@aeonx.digital` must be verified in AWS SES before it can send emails. This is a required setup step not in the to-do list.
- **Resolution:** SES setup already exists in AWS account `761685920937`.
- **Status:** ✅ Resolved

**4. EC2 agent has no process manager**
If the FastAPI app crashes, nothing restarts it automatically.
- **Resolution:** `agent/aeonx-agent.service` systemd unit created. Auto-restarts on crash with 5s delay. Installed via `agent/setup.sh`.
- **Status:** ✅ Resolved in code (pending deployment)

**5. IAM permission policy has duplicate permissions**
`EC2RemediationAllowlist` and `EC2DescribeOnly` both included `ec2:DescribeInstances` and `ec2:DescribeInstanceStatus`. Redundant — creates confusion during audits.
- **Resolution:** Removed duplicate describe actions from remediation block. Also added `sts:AssumeRole` for `Aeonx-L2-Role` (needed Phase 3).
- **Status:** ✅ Resolved

**6. S3 incident log bucket not in to-do list**
The audit log writes to `aeonx-ai-agent-incidents/` in S3 but creating the bucket, setting lifecycle policies, and enabling versioning is never listed as a task.
- Fix: add S3 bucket setup to infrastructure to-do items.
- Phase: 1

**7. Zabbix webhook payload format unknown**
The "Gen-AI" action exists but the exact payload Zabbix sends was never captured. Lambda 1 normalizer needs to parse it correctly.
- **Resolution:** Queried live Zabbix API. Gen-AI action uses `default_msg:1`. Documented exact payload structure and normalized schema in `zabbix-webhook-payload.md`.
- **Status:** ✅ Resolved

**8. No alert deduplication**
Zabbix re-fires the same alert on escalation steps. The agent will process it multiple times — potentially restarting the same instance twice.
- **Resolution:** `agent/app/dedup.py` — in-memory TTL cache keyed on `trigger_id:host_name`, 30-min window, thread-safe. Single worker enforced to keep store globally consistent.
- **Status:** ✅ Resolved in code (pending deployment)

**9. GCP service account permission scope unclear**
The GCP service account key is for Vertex AI (`Vertex AI User` role). GCP VM restart (Phase 3) needs `Compute Instance Admin` role — a different permission scope. One service account cannot safely hold both.
- Fix: use two separate GCP service accounts — one for Vertex AI, one for Compute operations.
- Phase: 2 (Vertex AI account), Phase 3 (Compute account)

**10. Client GUI has no data isolation design**
When a client asks "is my server up?", the `/chat` endpoint must only return data for that client's hosts — not other clients'. No auth or data isolation design exists yet.
- Fix: design client identity + data scoping before building Option A GUI.
- Phase: 7 (Client GUI)

**11. ManageEngine duplicate ticket prevention missing**
If the same alert fires 3 times before resolution, 3 tickets get created for the same incident.
- **Resolution:** `agent/app/ticketing.py` — `find_open_ticket()` searches for open tickets with same subject+host before creating. If found, adds a note to existing ticket instead.
- **Status:** ✅ Resolved in code

**12. Phase 7 / Client GUI labelling mismatch**
Phase 7 is labelled "Observability & Audit" in the phases table but "Client GUI (Option A)" in the to-do list. These are different things.
- Fix: keep Phase 7 as Observability & Audit. Add Client GUI as Phase 9 (or sub-phase of Phase 7).
- Phase: documentation fix

---

## 🟡 Minor Issues

- To-do item 6 says "Add Bedrock permissions to IAM role (for future fallback)" — Bedrock is not in the architecture. Remove or explicitly document as optional fallback.
- Restart loop prevention (no restart if active incident in last 30 min) is in ARCHITECTURE.md but missing from README Phase 3 safety section.

---

## ✅ Fixes Needed (Priority Order)

| Priority | Gap # | Fix | Phase | Status |
|----------|-------|-----|-------|--------|
| — | 1 | Private network (same AWS account) | — | ✅ Resolved |
| — | 2 | Private network (same AWS account) | — | ✅ Resolved |
| — | 3 | SES already verified | — | ✅ Resolved |
| — | 4 | systemd service in `agent/aeonx-agent.service` | — | ✅ Resolved in code |
| — | 5 | Duplicate IAM permissions removed, `sts:AssumeRole` added | — | ✅ Resolved |
| — | 7 | Zabbix payload documented in `zabbix-webhook-payload.md` | — | ✅ Resolved |
| — | 8 | Dedup in `agent/app/dedup.py` (30-min TTL, single worker) | — | ✅ Resolved in code |
| — | 12 | Phase 7/GUI labelling fixed in README | — | ✅ Resolved |
| 1 | 6 | Create S3 bucket `aeonx-ai-agent-incidents` with lifecycle policy | Phase 1 | ⏳ Infra task |
| 2 | 9 | Create two GCP service accounts: Vertex AI + Compute (separate) | Phase 2/3 | ⏳ Infra task |
| — | 11 | Duplicate ticket check in `ticketing.py` `find_open_ticket()` | — | ✅ Resolved in code |
| 4 | 10 | Design client data isolation for `/chat` endpoint | Phase 9 | ⏳ Future |
