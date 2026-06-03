from fastapi import FastAPI, HTTPException, Request
import logging

from .models import AlertPayload, IncidentResponse
from .dedup import is_duplicate, mark_seen
from .classifier import classify
from .notifier import send_email
from .logger import log_incident
from .ticketing import find_open_ticket, create_ticket, add_note

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="AeonX AI Ops Agent")


@app.post("/alert", response_model=IncidentResponse)
async def handle_alert(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    incident = AlertPayload(**payload)
    log.info("Received alert: %s | %s | %s", incident.incident_id, incident.alert.severity, incident.alert.name)

    # Deduplication — skip if same trigger+host seen in last 30 min
    if is_duplicate(incident):
        log.info("Duplicate suppressed: %s / %s", incident.alert.trigger_id, incident.host.name)
        return IncidentResponse(incident_id=incident.incident_id, action_taken="deduplicated", ticket_id=None)

    mark_seen(incident)

    # AI classification
    decision = classify(incident)
    log.info("Decision: action=%s severity=%s confidence=%.2f", decision.action, decision.severity, decision.confidence)

    # Ticketing — check for existing open ticket first (Gap #11)
    ticket_id = None
    try:
        existing = find_open_ticket(incident)
        if existing:
            add_note(existing, f"Duplicate alert received. AI decision: {decision.action} (confidence: {decision.confidence:.0%}). {decision.summary}")
            ticket_id = existing
            log.info("Updated existing ticket %s", existing)
        elif decision.action in ("create-ticket", "escalate"):
            ticket_id = create_ticket(incident, decision)
    except Exception as e:
        log.error("Ticketing failed for %s: %s", incident.incident_id, e)

    # Always send SES email summary
    send_email(incident, decision)

    # Log to S3
    log_incident(incident, decision)

    return IncidentResponse(
        incident_id=incident.incident_id,
        action_taken=decision.action,
        ticket_id=ticket_id,
    )


@app.get("/health")
def health():
    return {"status": "ok"}
