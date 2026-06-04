"""
Dev SES mock — writes emails to a local log file instead of sending via AWS SES.
"""
import os
import logging
from datetime import datetime, timezone
from agent.app.models import AlertPayload, AIDecision
from agent.app.notifier import _SEVERITY_EMOJI, _ACTION_LABEL

log = logging.getLogger(__name__)

_LOG_FILE = os.environ.get("DEV_SES_LOG", "./output/emails.log")


def send_email(incident: AlertPayload, decision: AIDecision) -> None:
    os.makedirs(os.path.dirname(_LOG_FILE), exist_ok=True)

    emoji = _SEVERITY_EMOJI.get(decision.severity, "⚪")
    action_label = _ACTION_LABEL.get(decision.action, decision.action)
    subject = f"{emoji} [{decision.severity.upper()}] {incident.alert.name} — {incident.host.name}"

    body = f"""
{'='*60}
[DEV] EMAIL — {datetime.now(timezone.utc).isoformat()}
TO: awsalerts@aeonx.digital
SUBJECT: {subject}

INCIDENT ID : {incident.incident_id}
HOST        : {incident.host.name} ({incident.host.ip})
CLIENT      : {incident.client.name or 'N/A'}
ALERT       : {incident.alert.name}
SEVERITY    : {incident.alert.severity.upper()}
VALUE       : {incident.alert.item_value or 'N/A'}

AI CATEGORY : {decision.category}
AI SEVERITY : {decision.severity.upper()}
CONFIDENCE  : {decision.confidence:.0%}
ACTION      : {action_label}

SUMMARY:
{decision.summary}

SUGGESTED:
{decision.suggested_action or 'N/A'}
{'='*60}
"""
    with open(_LOG_FILE, "a") as f:
        f.write(body)

    log.info("[DEV] Email logged to %s | subject: %s", _LOG_FILE, subject)
