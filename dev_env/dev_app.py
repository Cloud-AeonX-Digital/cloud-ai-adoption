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
from fastapi.responses import HTMLResponse
import logging, os

from agent.app.models import AlertPayload, IncidentResponse
from agent.app.dedup import is_duplicate, mark_seen
from agent.app.ticketing import find_open_ticket, create_ticket, add_note
from agent.app.approval_manager import (
    request_approval, get_approval, decide, mark_executed,
    list_pending, list_all, ApprovalStatus
)
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
    approval_id = None

    # Human approval required — handle before ticketing block
    if decision.action == "human-approval-required":
        approval_id = request_approval(
            incident_id=incident.incident_id,
            approval_type=decision.category,
            description=decision.summary,
            proposed_action=decision.suggested_action,
            metadata={"host": incident.host.model_dump(), "client": incident.client.model_dump(), "alert": incident.alert.model_dump()}
        )
        log.info("APPROVAL REQUIRED: %s", approval_id)
        try:
            ticket_id = create_ticket(incident, decision)
        except Exception as e:
            log.error("TICKET ERROR: %s", e)
    else:
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

    send_email(incident, decision, approval_id=approval_id)
    log_incident(incident, decision, ticket_id=ticket_id)

    return IncidentResponse(
        incident_id=incident.incident_id,
        action_taken=decision.action,
        ticket_id=ticket_id,
        approval_id=approval_id,
    )


@app.get("/approvals")
def get_approvals_list(): return list_all()

@app.get("/approvals/pending")
def get_pending(): return list_pending()

@app.get("/approvals/{approval_id}")
def get_approval_by_id(approval_id: str):
    a = get_approval(approval_id)
    if not a: raise HTTPException(404, "Not found")
    return a

@app.post("/approvals/{approval_id}/approve")
async def approve_action(approval_id: str, request: Request):
    body = {}
    try: body = await request.json()
    except Exception: pass
    a = decide(approval_id, "approve", decided_by=body.get("decided_by","human"), note=body.get("note",""))
    if not a: raise HTTPException(404, "Not found")
    if a["status"] == ApprovalStatus.APPROVED:
        log.info("[DEV] Approved %s — action: %s", approval_id, a.get("proposed_action","")[:60])
        mark_executed(approval_id)
    return a

@app.post("/approvals/{approval_id}/reject")
async def reject_action(approval_id: str, request: Request):
    body = {}
    try: body = await request.json()
    except Exception: pass
    a = decide(approval_id, "reject", decided_by=body.get("decided_by","human"), note=body.get("note",""))
    if not a: raise HTTPException(404, "Not found")
    return a

@app.get("/approvals/{approval_id}/approve", response_class=HTMLResponse)
def approve_via_email(approval_id: str):
    a = decide(approval_id, "approve", decided_by="email-link")
    if not a: return HTMLResponse("<h2>Not found or expired</h2>", status_code=404)
    if a["status"] == ApprovalStatus.APPROVED: mark_executed(approval_id)
    color = "#22c55e" if a["status"] == ApprovalStatus.APPROVED else "#6b7280"
    msg = "✅ Approved — action queued for execution." if a["status"] == ApprovalStatus.APPROVED else f"Already {a['status']}"
    return HTMLResponse(f"""<html><body style="font-family:system-ui;background:#0b0e1a;color:#e8eaf6;display:flex;align-items:center;justify-content:center;height:100vh;margin:0"><div style="text-align:center;background:#141828;border:1px solid #252a45;border-radius:16px;padding:40px;max-width:400px"><h1 style="color:{color}">{msg}</h1><p style="color:#565b80;font-size:12px;margin-top:16px">ID: {approval_id}</p></div></body></html>""")

@app.get("/approvals/{approval_id}/reject", response_class=HTMLResponse)
def reject_via_email(approval_id: str):
    a = decide(approval_id, "reject", decided_by="email-link")
    if not a: return HTMLResponse("<h2>Not found or expired</h2>", status_code=404)
    return HTMLResponse(f"""<html><body style="font-family:system-ui;background:#0b0e1a;color:#e8eaf6;display:flex;align-items:center;justify-content:center;height:100vh;margin:0"><div style="text-align:center;background:#141828;border:1px solid #252a45;border-radius:16px;padding:40px;max-width:400px"><h1 style="color:#ef4444">❌ Rejected</h1><p>Action has been rejected. Ticket remains open for manual review.</p><p style="color:#565b80;font-size:12px;margin-top:16px">ID: {approval_id}</p></div></body></html>""")


@app.get("/health")
def health():
    return {"status": "ok", "mode": "dev", "model": os.environ.get("BEDROCK_MODEL_ID", "not set")}
