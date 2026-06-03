"""
ManageEngine ServiceDesk Plus integration.

Lifecycle (AeonX Life Cycle):
  Open → Assigned → In Progress → Resolved → Closed

Field IDs (from live API):
  category:     601 = AWS Support
  subcategory:  313 = Monitoring & Logging
  request_type: 303 = AWS Support Incident
  group:        615 = AWS Support Internal
  priority:       1 = High, 2 = Medium, 3 = Low, 4 = Urgent
  udf_pick_307:   "Other" (mandatory)
  udf_pick_302:   required on Assigned→In Progress transition
"""

import json
import os
import logging
import urllib.request
import urllib.parse
import urllib.error
import boto3

from .models import AlertPayload, AIDecision

log = logging.getLogger(__name__)

_BASE = os.environ.get("MANAGEENGINE_URL", "https://customer.aeonx.support")
_SSM_KEY = "/aeonx/ai-agent/manageengine-api-key"
_REQUESTER_EMAIL = "aws.automation@aeonx.digital"

# Field IDs discovered from live API
_CATEGORY_ID = "601"       # AWS Support
_SUBCATEGORY_ID = "313"    # Monitoring & Logging
_REQUEST_TYPE_ID = "303"   # AWS Support Incident
_GROUP_ID = "615"          # AWS Support Internal

_PRIORITY_MAP = {
    "low": "3",
    "medium": "2",
    "high": "1",
    "critical": "4",
}

_api_key: str | None = None


def _get_api_key() -> str:
    global _api_key
    if _api_key:
        return _api_key
    ssm = boto3.client("ssm", region_name="ap-south-1")
    param = ssm.get_parameter(Name=_SSM_KEY, WithDecryption=True)
    _api_key = param["Parameter"]["Value"]
    return _api_key


def _request(method: str, path: str, payload: dict | None = None) -> dict:
    key = _get_api_key()
    url = f"{_BASE}/api/v3/{path}"
    data = None
    if payload is not None:
        data = urllib.parse.urlencode({"input_data": json.dumps(payload)}).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={
            "authtoken": key,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


def find_open_ticket(incident: AlertPayload) -> str | None:
    """Return ticket ID if an open ticket for same host+alert exists (Gap #11 fix)."""
    search = {
        "list_info": {
            "row_count": 5,
            "search_fields": {"subject": f"[AI Agent] {incident.alert.name}"},
        }
    }
    path = f"requests?input_data={urllib.parse.quote(json.dumps(search))}"
    result = _request("GET", path)
    for ticket in result.get("requests", []):
        if (
            ticket.get("status", {}).get("name") not in ("Resolved", "Closed")
            and incident.host.name in ticket.get("subject", "")
        ):
            return ticket["id"]
    return None


def create_ticket(incident: AlertPayload, decision: AIDecision) -> str | None:
    """Create a new ticket. Returns ticket ID or None on failure."""
    priority_id = _PRIORITY_MAP.get(decision.severity, "2")
    subject = f"[AI Agent] {incident.alert.name} — {incident.host.name}"
    description = (
        f"<b>Incident ID:</b> {incident.incident_id}<br>"
        f"<b>Host:</b> {incident.host.name} ({incident.host.ip})<br>"
        f"<b>Client:</b> {incident.client.name or 'N/A'}<br>"
        f"<b>Alert:</b> {incident.alert.name}<br>"
        f"<b>Severity:</b> {incident.alert.severity.upper()}<br>"
        f"<b>Value:</b> {incident.alert.item_value or 'N/A'}<br><br>"
        f"<b>AI Summary:</b> {decision.summary}<br>"
        f"<b>Suggested Action:</b> {decision.suggested_action or 'N/A'}<br>"
        f"<b>AI Confidence:</b> {decision.confidence:.0%}"
    )
    payload = {
        "request": {
            "subject": subject,
            "description": description,
            "requester": {"email_id": _REQUESTER_EMAIL},
            "priority": {"id": priority_id},
            "category": {"id": _CATEGORY_ID},
            "subcategory": {"id": _SUBCATEGORY_ID},
            "request_type": {"id": _REQUEST_TYPE_ID},
            "group": {"id": _GROUP_ID},
            "udf_fields": {"udf_pick_307": "Other"},
        }
    }
    result = _request("POST", "requests", payload)
    if result.get("response_status", {}).get("status") == "success":
        ticket_id = result["request"]["id"]
        log.info("Ticket created: %s for incident %s", ticket_id, incident.incident_id)
        return ticket_id
    log.error("Ticket creation failed: %s", result.get("response_status"))
    return None


def resolve_ticket(ticket_id: str, resolution: str) -> bool:
    """
    Move ticket through lifecycle to Resolved.
    Flow: Open → Assigned → In Progress → Resolved
    """
    ai_technician_id = os.environ.get("ME_TECHNICIAN_ID", "4511")  # aws.automation user ID

    # Step 1: Assign
    r = _request("PUT", f"requests/{ticket_id}", {
        "request": {
            "status": {"name": "Assigned"},
            "technician": {"id": ai_technician_id},
            "group": {"id": _GROUP_ID},
            "subcategory": {"id": _SUBCATEGORY_ID},
            "status_change_comments": "Assigned to AI agent for auto-remediation.",
        }
    })
    if r.get("response_status", {}).get("status") != "success":
        log.warning("Assign step failed for ticket %s: %s", ticket_id, r.get("response_status"))
        return False

    # Step 2: In Progress (requires udf_pick_302 = "No" — confirmed from live tickets)
    r = _request("PUT", f"requests/{ticket_id}", {
        "request": {
            "status": {"name": "In Progress"},
            "udf_fields": {"udf_pick_302": "No"},
            "status_change_comments": "AI agent started auto-remediation.",
        }
    })
    if r.get("response_status", {}).get("status") != "success":
        log.warning("In Progress step failed for ticket %s: %s", ticket_id, r.get("response_status"))
        return False

    # Step 3: Add worklog (required before Resolved transition)
    _request("POST", f"requests/{ticket_id}/worklogs", {
        "worklog": {
            "description": resolution,
            "technician": {"id": ai_technician_id},
        }
    })

    # Step 4: Resolved (requires resolution.content — worklog already added above)
    r = _request("PUT", f"requests/{ticket_id}", {
        "request": {
            "status": {"name": "Resolved"},
            "resolution": {"content": f"<div>{resolution}</div>"},
            "status_change_comments": "Issue resolved by AeonX AI Ops Agent.",
        }
    })
    if r.get("response_status", {}).get("status") != "success":
        log.error("Resolve step failed for ticket %s: %s", ticket_id, r.get("response_status"))
        return False

    # Step 5: Closed
    r = _request("PUT", f"requests/{ticket_id}", {
        "request": {
            "status": {"name": "Closed"},
            "status_change_comments": "Closed after resolution confirmed.",
        }
    })
    if r.get("response_status", {}).get("status") == "success":
        log.info("Ticket %s closed", ticket_id)
        return True

    log.error("Close step failed for ticket %s: %s", ticket_id, r.get("response_status"))
    return False


def add_note(ticket_id: str, note: str) -> None:
    """Add a work note to an existing ticket."""
    _request("POST", f"requests/{ticket_id}/worklogs", {
        "worklog": {
            "description": note,
            "technician": {"email_id": _REQUESTER_EMAIL},
        }
    })
