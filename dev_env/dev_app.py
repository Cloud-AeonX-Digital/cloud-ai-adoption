"""
Dev FastAPI app — identical logic to production but uses local mocks.
Run: uvicorn dev_env.dev_app:app --reload --port 8000
UI:  http://localhost:8000/ui
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

os.makedirs("./dev_env/output/incidents", exist_ok=True)
os.makedirs("./dev_env/output", exist_ok=True)

from fastapi import FastAPI, HTTPException, Request
import logging

from agent.app.models import AlertPayload, IncidentResponse
from agent.app.dedup import is_duplicate, mark_seen
from agent.app.ticketing import find_open_ticket, create_ticket, add_note
from dev_env.classifier_dev import classify
from dev_env.notifier_dev import send_email
from dev_env.logger_dev import log_incident
from dev_env.ui import router as ui_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("./dev_env/output/agent.log")],
)
log = logging.getLogger(__name__)

app = FastAPI(title="AeonX AI Ops Agent [DEV]")
app.include_router(ui_router)


@app.post("/alert", response_model=IncidentResponse)
async def handle_alert(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    incident = AlertPayload(**payload)
    log.info("ALERT: %s | %s | %s", incident.incident_id[:8], incident.alert.severity, incident.alert.name)

    if is_duplicate(incident):
        log.info("DEDUP: suppressed %s", incident.alert.trigger_id)
        return IncidentResponse(incident_id=incident.incident_id, action_taken="deduplicated", ticket_id=None)

    mark_seen(incident)

    decision = classify(incident)
    log.info("DECISION: actionable=%s action=%s sev=%s conf=%.0f%%",
             decision.actionable, decision.action, decision.severity, decision.confidence * 100)

    ticket_id = None
    try:
        existing = find_open_ticket(incident)
        if existing:
            add_note(existing, f"Duplicate alert. AI: {decision.action} ({decision.confidence:.0%}). {decision.summary}")
            ticket_id = existing
        elif decision.action in ("create-ticket", "escalate"):
            ticket_id = create_ticket(incident, decision)
            if ticket_id:
                log.info("TICKET: created %s", ticket_id)
    except Exception as e:
        log.error("TICKET ERROR: %s", e)

    send_email(incident, decision)
    log_incident(incident, decision, ticket_id=ticket_id)

    return IncidentResponse(
        incident_id=incident.incident_id,
        action_taken=decision.action,
        ticket_id=ticket_id,
    )


@app.get("/health")
def health():
    return {"status": "ok", "mode": "dev", "model": os.environ.get("BEDROCK_MODEL_ID", "not set")}
