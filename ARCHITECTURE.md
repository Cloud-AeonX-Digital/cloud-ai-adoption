# ARCHITECTURE.md — AeonX AI Ops Agent System Design

> Detailed technical architecture. Read alongside README.md.

---

## System Overview

The agent operates as an event-driven pipeline: alerts flow in from Zabbix and CloudWatch, get normalized, classified by Vertex AI, and routed to either auto-remediation or human escalation — with every action logged.

---

## Component Map

```
┌──────────────────────────────────────────────────────────────────┐
│  SIGNAL SOURCES                                                   │
│                                                                   │
│  Zabbix (706 hosts, ~90 client groups)                           │
│  └── "Gen-AI" action (actionid:14) → HTTP webhook                │
│                                                                   │
│  AWS CloudWatch Alarms                                            │
│  └── SNS topic → Lambda subscription                             │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  INGESTION LAYER  (AWS Lambda, ap-south-1)                        │
│                                                                   │
│  aeonx-ai-agent-normalizer (Lambda)                              │
│  ├── Accepts: Zabbix webhook POST + CloudWatch SNS event         │
│  ├── Normalizes to standard schema (see below)                   │
│  └── Publishes to SQS: aeonx-ai-agent-events                    │
└────────────────────────┬─────────────────────────────────────────┘
                         │
              Normalized alert payload
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  AI AGENT CORE  (GCP Cloud Function + Vertex AI Gemini)          │
│                                                                   │
│  Input: normalized alert JSON                                    │
│  Context: RAG — similar past incidents from vector store         │
│                                                                   │
│  Output:                                                         │
│  {                                                               │
│    "action": "auto-remediate" | "create-ticket" | "escalate",   │
│    "severity": "low" | "medium" | "high" | "critical",          │
│    "category": "website-down" | "high-memory" | "service-down"  │
│                  | "agent-unavailable" | "unknown",              │
│    "summary": "<human-readable incident summary>",              │
│    "confidence": 0.0–1.0,                                       │
│    "suggested_action": "<what to do>"                           │
│  }                                                               │
│                                                                   │
│  Rule: confidence < 0.75 → always escalate, never auto-act      │
└──────┬──────────────────────────┬───────────────────────────────┘
       │                          │
       │ action=auto-remediate    │ action=create-ticket / escalate
       ▼                          ▼
┌──────────────┐        ┌─────────────────────────┐
│ REMEDIATION  │        │  HUMAN LOOP              │
│  (Lambda)    │        │                          │
│              │        │  ManageEngine ticket     │
│  EC2 restart │        │  auto-created with:      │
│  → check tag │        │  - AI summary            │
│    auto-     │        │  - severity              │
│    restart=  │        │  - suggested action      │
│    true      │        │                          │
│              │        │  SES email →             │
│  GCP VM      │        │  awsalerts@aeonx.digital │
│  restart     │        │                          │
│  → allowlist │        │  (escalate only):        │
│    check     │        │  page on-call engineer   │
│              │        └─────────────────────────┘
│  SSM Run     │
│  Command     │
│  (service    │
│   restart)   │
└──────┬───────┘
       │
       │ post-action health check
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  VERIFICATION                                                     │
│  - EC2/VM: poll DescribeInstanceStatus until running             │
│  - Website: HTTP health check (200 OK)                           │
│  - Service: SSM Run Command status check                         │
│  - On success: update/close ManageEngine ticket + SES resolved   │
│  - On failure: escalate to human loop                            │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  AUDIT & MEMORY                                                   │
│                                                                   │
│  S3: aeonx-ai-agent-incidents/                                   │
│  └── {date}/{incident-id}.json  (full event + decision + outcome)│
│                                                                   │
│  SSM Parameter Store: /aeonx/ai-agent/*                         │
│  └── API keys, config, thresholds                                │
│                                                                   │
│  Vector store (Phase 5): past incidents indexed for RAG          │
└──────────────────────────────────────────────────────────────────┘
```

---

## Normalized Alert Schema

Every alert — regardless of source — is normalized to this schema before hitting the AI:

```json
{
  "incident_id": "uuid",
  "source": "zabbix" | "cloudwatch",
  "timestamp": "ISO8601",
  "client": {
    "name": "Ashapura Group",
    "aws_account": "354594115710",
    "host_group_id": "23"
  },
  "host": {
    "name": "hostname",
    "ip": "x.x.x.x",
    "cloud": "aws" | "gcp",
    "instance_id": "i-xxxxxxxxx"
  },
  "alert": {
    "name": "This Website is Down",
    "severity": "average" | "high" | "disaster",
    "status": "problem" | "resolved",
    "trigger_id": "zabbix-trigger-id or cloudwatch-alarm-name"
  },
  "raw": {}
}
```

---

## IAM Role

**Role name:** `aeonx-ai-agent-role`
**Account:** `761685920937`
**Region:** `ap-south-1`
**ExternalId:** `aeonx-ai-agent-2026`

**Permissions (minimal footprint):**
- EC2: describe + stop/start/reboot — only on instances tagged `auto-restart=true`
- SES: send email — only from `*@aeonx.digital`
- SSM: get parameters — only under `/aeonx/ai-agent/*`
- SNS: publish — only to `aeonx-ai-agent*` topics
- CloudWatch Logs: write — only to `/aws/lambda/aeonx-ai-agent*`

Policy files: `iam/trust-policy.json` + `iam/agent-permission-policy.json`

---

## Zabbix Integration

**Existing "Gen-AI" action (actionid: 14):**
- Fires on: severity Average, High, Disaster
- Scoped to: host groups 11045, 11046 (to be expanded)
- Current operation: send email to 2 users
- **Change required:** update operation to HTTP webhook → Lambda URL

No new Zabbix configuration needed beyond changing the action's operation target.

---

## Auto-Remediation Allowlist

EC2/VM restart is **opt-in only**. An instance is eligible only if:
1. Tagged `auto-restart=true`
2. Alert category matches a known auto-resolvable pattern
3. AI confidence ≥ 0.75

Instances without the tag are never touched — ticket created and human notified instead.

---

## Secrets Management

All credentials stored in SSM Parameter Store. Never hardcoded.

| Parameter | Description |
|-----------|-------------|
| `/aeonx/ai-agent/manageengine-api-key` | ManageEngine ServiceDesk Plus API key |
| `/aeonx/ai-agent/gcp-service-account-key` | GCP service account JSON for Vertex AI |
| `/aeonx/ai-agent/zabbix-api-token` | Zabbix API token (read-only) |
| `/aeonx/ai-agent/ses-from-address` | SES verified sender address |
