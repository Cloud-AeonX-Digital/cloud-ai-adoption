import boto3
import os
import logging
from .models import AlertPayload, AIDecision

log = logging.getLogger(__name__)

_SES_REGION = "ap-south-1"
_FROM = os.environ.get("SES_FROM", "awsalerts@aeonx.digital")
_TO = os.environ.get("SES_TO", "awsalerts@aeonx.digital")

_SEVERITY_EMOJI = {
    "low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴",
}
_ACTION_LABEL = {
    "auto-remediate": "⚙️ Auto-Remediation Triggered",
    "create-ticket": "🎫 Ticket Created",
    "escalate": "🚨 Escalated to Team",
    "deduplicated": "🔁 Duplicate Suppressed",
}


def send_email(incident: AlertPayload, decision: AIDecision, approval_id: str | None = None) -> None:
    emoji = _SEVERITY_EMOJI.get(decision.severity, "⚪")
    action_label = _ACTION_LABEL.get(decision.action, decision.action)

    subject = f"{emoji} [{decision.severity.upper()}] {incident.alert.name} — {incident.host.name}"

    approval_section = ""
    if approval_id:
        base = os.environ.get("AGENT_BASE_URL", "http://172.25.29.253:8000")
        approval_section = f"""
{'=' * 60}
⚠️  HUMAN APPROVAL REQUIRED
{'=' * 60}

This action requires your approval before the agent proceeds.

  ✅ APPROVE: {base}/approvals/{approval_id}/approve
  ❌ REJECT:  {base}/approvals/{approval_id}/reject

Approval expires in 24 hours.
"""

    body = f"""AeonX AI Ops Agent — Incident Report
{'=' * 60}

INCIDENT ID : {incident.incident_id}
TIME        : {incident.timestamp}
SOURCE      : {incident.source.upper()}

HOST        : {incident.host.name}
IP          : {incident.host.ip}
CLIENT      : {incident.client.name or 'N/A'}
AWS ACCOUNT : {incident.client.aws_account or 'N/A'}

ALERT       : {incident.alert.name}
SEVERITY    : {incident.alert.severity.upper()}
STATUS      : {incident.alert.status.upper()}
VALUE       : {incident.alert.item_value or 'N/A'}

{'=' * 60}
AI ASSESSMENT
{'=' * 60}

Category    : {decision.category}
AI Severity : {decision.severity.upper()}
Confidence  : {decision.confidence:.0%}
Action      : {action_label}

Summary:
{decision.summary}

Suggested Action:
{decision.suggested_action or 'N/A'}
{approval_section}
{'=' * 60}
This is an automated message from AeonX AI Ops Agent.
"""

    try:
        ses = boto3.client("ses", region_name=_SES_REGION)
        ses.send_email(
            Source=_FROM,
            Destination={"ToAddresses": [_TO]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )
        log.info("Email sent for incident %s", incident.incident_id)
    except Exception as e:
        # Non-fatal — log and continue
        log.error("SES send failed for %s: %s", incident.incident_id, e)
