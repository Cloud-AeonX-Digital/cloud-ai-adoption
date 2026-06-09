"""
Dev S3 mock — writes full workflow timeline to local filesystem.
Each incident record tracks every step from alert → resolution.
Also posts to Express backend for React UI.
"""
import json
import os
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone
from agent.app.models import AlertPayload, AIDecision

_EXPRESS_URL = os.environ.get("EXPRESS_API_URL", "http://localhost:3001")

log = logging.getLogger(__name__)

_OUTPUT_DIR = os.environ.get("DEV_S3_DIR", "./output/incidents")


def log_incident(incident: AlertPayload, decision: AIDecision,
                 ticket_id: str | None = None,
                 workflow_steps: list | None = None) -> str:
    """Write full incident workflow record. Returns file path."""
    date = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    out_dir = os.path.join(_OUTPUT_DIR, date)
    os.makedirs(out_dir, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()

    record = {
        "incident_id": incident.incident_id,
        "source": incident.source,
        "alert_triggered_at": incident.timestamp,
        "logged_at": now,

        # Signal
        "alert": incident.alert.model_dump(),
        "host": incident.host.model_dump(),
        "client": incident.client.model_dump(),

        # AI decision
        "classification": {
            "actionable": decision.actionable,
            "severity": decision.severity,
            "category": decision.category,
            "action": decision.action,
            "confidence": decision.confidence,
            "solution_id": decision.solution_id,
            "summary": decision.summary,
        },

        # Outcome
        "ticket_id": ticket_id,
        "resolution_steps": decision.solution_steps,

        # Full workflow timeline
        "workflow": workflow_steps or [
            {"step": "alert_received",    "ts": incident.timestamp, "detail": f"Zabbix alert: {incident.alert.name}"},
            {"step": "ai_classified",     "ts": now, "detail": f"{'Actionable' if decision.actionable else 'Non-actionable'} | {decision.severity.upper()} | {decision.category}"},
            {"step": "action_decided",    "ts": now, "detail": f"Action: {decision.action} | Confidence: {decision.confidence:.0%}"},
            {"step": "ticket_created",    "ts": now, "detail": f"Ticket: {ticket_id}" if ticket_id else "No ticket created"},
            {"step": "email_sent",        "ts": now, "detail": "Summary email sent to awsalerts@aeonx.digital"},
        ],
    }

    path = os.path.join(out_dir, f"{incident.incident_id}.json")
    with open(path, "w") as f:
        json.dump(record, f, indent=2)

    log.info("[DEV] Incident logged to %s", path)

    # Also post to Express backend for React UI
    try:
        body = json.dumps(record).encode()
        req = urllib.request.Request(
            f"{_EXPRESS_URL}/incidents", data=body,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception as e:
        log.debug("[DEV] Express incident post skipped: %s", e)

    return path


def sync_approval_to_express(approval: dict) -> None:
    """Sync approval state to Express so React UI can display it."""
    try:
        body = json.dumps(approval).encode()
        req = urllib.request.Request(
            f"{_EXPRESS_URL}/approvals", data=body,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception as e:
        log.debug("[DEV] Express approval sync skipped: %s", e)
