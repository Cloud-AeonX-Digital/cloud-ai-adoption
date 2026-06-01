# ARCHITECTURE.md — AeonX AI Ops Agent Detailed Design

> Technical reference. Read alongside README.md.
> Updated: 2026-06-01

---

## Design Principles

- **Lambda for ingestion** — stateless, event-driven, zero cost at idle
- **EC2 for the agent brain** — persistent service, handles AI calls + future client GUI on same instance
- **GCP Vertex AI (Gemini)** — LLM layer, called over HTTPS from EC2
- **No cross-cloud complexity** — EC2 calls Gemini as a plain HTTPS API; no VPC peering needed
- **Tag-gated remediation** — agent can only touch instances explicitly opted in
- **All secrets in SSM** — never hardcoded, never in environment variables

---

## Normalized Alert Schema

Every alert — regardless of source (Zabbix or CloudWatch) — is normalized to this schema by Lambda 1 before reaching the EC2 agent:

```json
{
  "incident_id": "uuid-v4",
  "source": "zabbix",
  "timestamp": "2026-06-01T08:30:00Z",
  "client": {
    "name": "Ashapura SAP PROD",
    "aws_account": "354594115710",
    "host_group_id": "23"
  },
  "host": {
    "name": "ashapura-sap-prod-01",
    "ip": "10.0.1.50",
    "cloud": "aws",
    "instance_id": "i-0abc123def456"
  },
  "alert": {
    "name": "This Website is Down",
    "severity": "high",
    "status": "problem",
    "trigger_id": "12345"
  },
  "raw": {}
}
```

---

## AI Decision Output Schema

Gemini returns this structure for every alert:

```json
{
  "action": "auto-remediate | create-ticket | escalate",
  "severity": "low | medium | high | critical",
  "category": "website-down | high-memory | service-down | agent-unavailable | unknown",
  "summary": "Website on host ashapura-sap-prod-01 is unreachable. Likely cause: application crash or EC2 unresponsive.",
  "confidence": 0.92,
  "suggested_action": "Restart EC2 instance i-0abc123def456 after verifying no active transactions."
}
```

**Rule:** `confidence < 0.75` → always `escalate`, never auto-act regardless of category.

---

## EC2 Agent API Endpoints

```
POST /alert
  Input:  normalized alert JSON (from Lambda 1)
  Action: call Gemini → route decision → SES email + ticket + remediation
  Output: {incident_id, action_taken, ticket_id}

POST /chat                          [Phase 7 — Client GUI]
  Input:  {client_id, message}
  Action: query S3 incident history + live Zabbix API → Gemini answer
  Output: {response, sources}
```

---

## IAM Role

**Role:** `aeonx-ai-agent-role`
**Account:** `761685920937` (Aeonx payer)
**Region:** `ap-south-1`
**ExternalId:** `aeonx-ai-agent-2026`

| Permission | Scope | Purpose |
|-----------|-------|---------|
| `ec2:Stop/StartInstances` | Tag: `auto-restart=true` only | Auto-remediation |
| `ec2:Describe*` | All | Read instance state |
| `ses:SendEmail` | From `*@aeonx.digital` only | Notifications |
| `ssm:GetParameter` | `/aeonx/ai-agent/*` only | Read secrets |
| `sns:Publish` | `aeonx-ai-agent*` topics only | Event routing |
| `logs:PutLogEvents` | `/aws/lambda/aeonx-ai-agent*` | Lambda logs |

Policy files: `iam/trust-policy.json` + `iam/agent-permission-policy.json`

---

## Cross-Account Remediation (Phase 3)

For 158 client accounts, the agent uses a hub-and-spoke model:

```
aeonx-ai-agent-role (761685920937)
    │
    └── sts:AssumeRole → Aeonx-L2-Role (in each client account)
                              │
                              └── EC2 restart / SSM Run Command
                                  (within that client's account)
```

`Aeonx-L2-Role` already exists in all 158 accounts. Phase 3 adds a trust policy entry to each, allowing `aeonx-ai-agent-role` to assume it. This is scripted — not done manually.

---

## Zabbix Integration

**Existing "Gen-AI" action (actionid: 14):**
- Fires on: Average, High, Disaster severity
- Current operation: send email to 2 users via AWS SES
- **Change for Phase 1:** update operation to HTTP POST → Lambda 1 URL

No new Zabbix setup needed. One config change in the existing action.

---

## Secrets in SSM Parameter Store

| Parameter Path | Value |
|---------------|-------|
| `/aeonx/ai-agent/gcp-service-account-key` | GCP service account JSON (for Vertex AI) |
| `/aeonx/ai-agent/manageengine-api-key` | ManageEngine API key |
| `/aeonx/ai-agent/zabbix-api-token` | Zabbix read-only API token |
| `/aeonx/ai-agent/ses-from-address` | `awsalerts@aeonx.digital` |
| `/aeonx/ai-agent/ec2-agent-url` | Internal URL of EC2 agent service |

---

## Auto-Remediation Allowlist Logic

An instance is eligible for auto-restart only when ALL conditions are true:

1. Instance tagged `auto-restart=true`
2. Alert category is a known auto-resolvable pattern
3. AI confidence ≥ 0.75
4. No other active incident on the same host in last 30 minutes (prevents restart loops)

If any condition fails → create ManageEngine ticket + SES escalation email.

---

## Data Flow — Full Incident Lifecycle

```
1. Zabbix fires alert (severity: High)
        │
2. Lambda 1 receives webhook POST
   └── normalizes → incident JSON
        │
3. Lambda 1 POSTs to EC2 agent /alert
        │
4. EC2 agent calls Vertex AI (Gemini)
   └── returns: {action: auto-remediate, confidence: 0.91, ...}
        │
5a. confidence ≥ 0.75 + tag check passes
    └── EC2 restart via AWS SDK
    └── poll until running (max 5 min)
    └── HTTP health check (website-down category)
        │
5b. confidence < 0.75 OR tag missing
    └── create ManageEngine ticket
    └── SES email to awsalerts@aeonx.digital
        │
6. Write incident record to S3
   └── aeonx-ai-agent-incidents/{date}/{incident_id}.json
        │
7. On success: update/close ticket + send "resolved" SES email
   On failure: escalate ticket + page on-call
```

---

## File Structure

```
cloud-ai-adoption/
├── README.md               — project overview, architecture, phases, to-do
├── ARCHITECTURE.md         — this file: detailed technical design
├── CLAUDE.md               — AI session resume config
├── PROGRESS.md             — phase handoff summaries
├── initial-goal-prompt.md  — original problem statement
├── iam/
│   ├── trust-policy.json           — who can assume aeonx-ai-agent-role
│   └── agent-permission-policy.json — what the role can do
├── lambda/
│   └── alert-ingestor/     — Lambda 1 code (Phase 1)
├── agent/
│   └── app/                — EC2 FastAPI agent code (Phase 1+)
└── terraform/              — infrastructure as code (Phase 6)
```
