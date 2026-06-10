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

from agent.app.models import AlertPayload, IncidentResponse, AIDecision
from agent.app.dedup import is_duplicate, mark_seen
from agent.app.ticketing import find_open_ticket, create_ticket, add_note
from agent.app.approval_manager import (
    request_approval, get_approval, decide, mark_executed,
    list_pending, list_all, ApprovalStatus
)
from agent.app.memory import init_db, write_incident
from dev_env.classifier_dev import classify as kb_classify
from dev_env.notifier_dev import send_email
from dev_env.logger_dev import log_incident
from dev_env.ui import router as ui_router

# Phase C: set USE_AGENT_LOOP=false to fall back to KB-only classifier
_USE_AGENT_LOOP = os.environ.get("USE_AGENT_LOOP", "true").lower() == "true"

if _USE_AGENT_LOOP:
    from agent.app.agent_loop import run as _agent_run
    classify = _agent_run
else:
    classify = kb_classify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("./dev_env/output/agent.log")],
)
log = logging.getLogger(__name__)

app = FastAPI(title="AeonX AI Ops Agent [DEV]")
app.include_router(ui_router)
init_db()  # Phase D: initialise FTS5 memory store


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

    # Skip approval flow for resolved alerts — just log them
    if incident.alert.status == "resolved":
        log.info("RESOLVED: %s | %s", incident.incident_id[:8], incident.alert.name)
        log_incident(incident, AIDecision(
            actionable=False, action="resolved", severity=incident.alert.severity,
            category="resolved", summary=f"Alert resolved: {incident.alert.name}",
            confidence=1.0, solution_id=None, solution_steps=[]
        ))
        return IncidentResponse(incident_id=incident.incident_id, action_taken="resolved", ticket_id=None, approval_id=None)

    decision = classify(incident)
    log.info("DECISION: actionable=%s action=%s sev=%s conf=%.0f%%",
             decision.actionable, decision.action, decision.severity, decision.confidence * 100)

    ticket_id = None
    approval_id = None

    # Every action requires human approval before execution
    if decision.action in ("human-approval-required", "auto-remediate", "create-ticket", "escalate"):
        approval_id = request_approval(
            incident_id=incident.incident_id,
            approval_type=decision.category,
            description=decision.summary,
            proposed_action=f"[{decision.action.upper()}] {decision.suggested_action or (decision.solution_steps[0] if decision.solution_steps else '')}",
            metadata={
                "host": incident.host.model_dump(),
                "client": incident.client.model_dump(),
                "alert": incident.alert.model_dump(),
                "solution_id": decision.solution_id,
                "solution_steps": decision.solution_steps,
                "ai_action": decision.action,
                "action_type": next((s.get("action","") for s in __import__('json').load(open("agent/known-solutions.json"))["solutions"] if s["id"]==decision.solution_id), "") if decision.solution_id else "",
                "ai_action_type": decision.agent_action_type,
                "agent_target_service": decision.agent_target_service,
                "severity": decision.severity,
                "confidence": decision.confidence,
            }
        )
        log.info("APPROVAL PENDING: %s | action=%s | %s", approval_id[:8], decision.action, incident.alert.name)
        # Sync to Express for React UI
        try:
            from dev_env.logger_dev import sync_approval_to_express
            from agent.app.approval_manager import get_approval
            sync_approval_to_express(get_approval(approval_id))
        except Exception as e:
            log.debug("Express approval sync: %s", e)
        try:
            ticket_id = create_ticket(incident, decision)
        except Exception as e:
            log.error("TICKET ERROR: %s", e)

    send_email(incident, decision, approval_id=approval_id)
    log_incident(incident, decision, ticket_id=ticket_id)

    # Phase D: write high-signal incidents to FTS5 memory (skip low/medium noise)
    _MEMORY_CATEGORIES = {"website-down", "service-down", "disk-space", "ec2-terminated", "agent-unavailable"}
    _MEMORY_SEVERITIES = {"critical", "high"}
    is_fp = (decision.action == "create_ticket" and decision.actionable)
    if decision.severity in _MEMORY_SEVERITIES or decision.category in _MEMORY_CATEGORIES:
        write_incident(
            incident_id=incident.incident_id,
            host=incident.host.name,
            client=incident.client.name,
            alert_name=incident.alert.name,
            category=decision.category,
            severity=decision.severity,
            action=decision.action,
            solution_id=decision.solution_id or "",
            confidence=decision.confidence,
            false_positive=is_fp,
        )

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
        log.info("[DEV] Approved %s — executing action", approval_id)
        _execute_action_async(a)
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
    if a["status"] == ApprovalStatus.APPROVED:
        _execute_action_async(a)
    color = "#22c55e" if a["status"] == ApprovalStatus.APPROVED else "#6b7280"
    msg = "✅ Approved — action executing now." if a["status"] == ApprovalStatus.APPROVED else f"Already {a['status']}"
    return HTMLResponse(f"""<html><body style="font-family:system-ui;background:#0b0e1a;color:#e8eaf6;display:flex;align-items:center;justify-content:center;height:100vh;margin:0"><div style="text-align:center;background:#141828;border:1px solid #252a45;border-radius:16px;padding:40px;max-width:400px"><h1 style="color:{color}">{msg}</h1><p style="color:#565b80;font-size:12px;margin-top:16px">ID: {approval_id}</p></div></body></html>""")


def _execute_action_async(approval: dict):
    """Execute the approved action in a background thread."""
    import threading
    def run():
        try:
            from agent.app.ssm_executor import execute_approved_action
            result = execute_approved_action(approval)
            if result["success"]:
                log.info("✅ Action executed: %s | %s", approval["approval_id"][:8], result.get("output","").strip()[:80])
            else:
                log.error("❌ Action failed: %s | %s", approval["approval_id"][:8], result.get("error",""))
            mark_executed(approval["approval_id"])
            # Sync updated approval to Express
            try:
                from dev_env.logger_dev import sync_approval_to_express
                from agent.app.approval_manager import get_approval
                sync_approval_to_express(get_approval(approval["approval_id"]))
            except Exception: pass
        except Exception as e:
            log.error("Execution error: %s", e)
    threading.Thread(target=run, daemon=True).start()

@app.get("/approvals/{approval_id}/reject", response_class=HTMLResponse)
def reject_via_email(approval_id: str):
    a = decide(approval_id, "reject", decided_by="email-link")
    if not a: return HTMLResponse("<h2>Not found or expired</h2>", status_code=404)
    return HTMLResponse(f"""<html><body style="font-family:system-ui;background:#0b0e1a;color:#e8eaf6;display:flex;align-items:center;justify-content:center;height:100vh;margin:0"><div style="text-align:center;background:#141828;border:1px solid #252a45;border-radius:16px;padding:40px;max-width:400px"><h1 style="color:#ef4444">❌ Rejected</h1><p>Action has been rejected. Ticket remains open for manual review.</p><p style="color:#565b80;font-size:12px;margin-top:16px">ID: {approval_id}</p></div></body></html>""")


@app.get("/health")
def health():
    return {"status": "ok", "mode": "dev", "model": os.environ.get("BEDROCK_MODEL_ID", "not set")}
