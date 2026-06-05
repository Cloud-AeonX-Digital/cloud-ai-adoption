"""
Dev FastAPI app — identical to production main.py but uses local mocks
for SES and S3. Classifier uses Bedrock gpt-oss-120b instead of Vertex AI.

Run: uvicorn dev_app:app --reload --port 8000
"""
import sys
import os

# Add project root to path so agent.app imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from fastapi import FastAPI, HTTPException, Request
import logging

from agent.app.models import AlertPayload, IncidentResponse
from agent.app.dedup import is_duplicate, mark_seen
from agent.app.ticketing import find_open_ticket, create_ticket, add_note

# Dev mocks — swap in place of production modules
from dev_env.classifier_dev import classify
from dev_env.notifier_dev import send_email
from dev_env.logger_dev import log_incident

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("./output/agent.log"),
    ]
)
log = logging.getLogger(__name__)
os.makedirs("./output", exist_ok=True)

app = FastAPI(title="AeonX AI Ops Agent [DEV]")


@app.post("/alert", response_model=IncidentResponse)
async def handle_alert(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    incident = AlertPayload(**payload)
    log.info(">>> ALERT: %s | %s | %s", incident.incident_id, incident.alert.severity, incident.alert.name)

    if is_duplicate(incident):
        log.info("DEDUP: suppressed %s / %s", incident.alert.trigger_id, incident.host.name)
        return IncidentResponse(incident_id=incident.incident_id, action_taken="deduplicated", ticket_id=None)

    mark_seen(incident)

    # AI classification via Bedrock gpt-oss-120b
    decision = classify(incident)
    log.info("DECISION: action=%s severity=%s confidence=%.2f", decision.action, decision.severity, decision.confidence)

    # Ticketing (real ManageEngine)
    ticket_id = None
    try:
        existing = find_open_ticket(incident)
        if existing:
            add_note(existing, f"Duplicate alert. AI: {decision.action} ({decision.confidence:.0%}). {decision.summary}")
            ticket_id = existing
            log.info("TICKET: updated existing %s", existing)
        elif decision.action in ("create-ticket", "escalate"):
            ticket_id = create_ticket(incident, decision)
            log.info("TICKET: created %s", ticket_id)
    except Exception as e:
        log.error("TICKET ERROR: %s", e)

    # Email mock (writes to output/emails.log)
    send_email(incident, decision)

    # S3 mock (writes to output/incidents/)
    log_incident(incident, decision)

    return IncidentResponse(
        incident_id=incident.incident_id,
        action_taken=decision.action,
        ticket_id=ticket_id,
    )


@app.get("/health")
def health():
    return {"status": "ok", "mode": "dev", "model": os.environ.get("BEDROCK_MODEL_ID", "not set")}
