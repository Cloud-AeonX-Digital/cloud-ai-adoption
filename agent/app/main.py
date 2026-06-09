from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
import logging

from .models import AlertPayload, IncidentResponse
from .dedup import is_duplicate, mark_seen
from .classifier import classify
from .notifier import send_email
from .logger import log_incident
from .ticketing import find_open_ticket, create_ticket, add_note
from .approval_manager import (
    request_approval, get_approval, decide, mark_executed,
    list_pending, list_all, ApprovalStatus
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="AeonX AI Ops Agent")


# ── Alert ingestion ──────────────────────────────────────────────────────────

@app.post("/alert", response_model=IncidentResponse)
async def handle_alert(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    incident = AlertPayload(**payload)
    log.info("Received alert: %s | %s | %s", incident.incident_id, incident.alert.severity, incident.alert.name)

    if is_duplicate(incident):
        log.info("Duplicate suppressed: %s / %s", incident.alert.trigger_id, incident.host.name)
        return IncidentResponse(incident_id=incident.incident_id, action_taken="deduplicated", ticket_id=None)

    mark_seen(incident)

    decision = classify(incident)
    log.info("Decision: action=%s severity=%s confidence=%.2f", decision.action, decision.severity, decision.confidence)

    ticket_id = None
    approval_id = None

    # ── Human approval required (e.g. disk space expansion) ──────────────────
    if decision.action == "human-approval-required":
        approval_id = request_approval(
            incident_id=incident.incident_id,
            approval_type=decision.category,
            description=decision.summary,
            proposed_action=decision.suggested_action,
            metadata={
                "host": incident.host.model_dump(),
                "client": incident.client.model_dump(),
                "alert": incident.alert.model_dump(),
                "solution_id": decision.solution_id,
            }
        )
        log.info("Approval requested: %s for incident %s", approval_id, incident.incident_id)

        # Create ticket so human has a place to respond
        try:
            ticket_id = create_ticket(incident, decision)
        except Exception as e:
            log.error("Ticketing failed: %s", e)

        # Send email with approve/reject links
        send_email(incident, decision, approval_id=approval_id)

    else:
        # ── Standard ticketing flow ───────────────────────────────────────────
        try:
            existing = find_open_ticket(incident)
            if existing:
                add_note(existing, f"Duplicate alert. AI: {decision.action} ({decision.confidence:.0%}). {decision.summary}")
                ticket_id = existing
            elif decision.action in ("create-ticket", "escalate"):
                ticket_id = create_ticket(incident, decision)
        except Exception as e:
            log.error("Ticketing failed for %s: %s", incident.incident_id, e)

        send_email(incident, decision)

    log_incident(incident, decision)

    return IncidentResponse(
        incident_id=incident.incident_id,
        action_taken=decision.action,
        ticket_id=ticket_id,
        approval_id=approval_id,
    )


# ── Approval endpoints ───────────────────────────────────────────────────────

@app.get("/approvals")
def get_approvals(status: str = None):
    """List all approvals, optionally filtered by status."""
    items = list_all()
    if status:
        items = [a for a in items if a["status"] == status]
    return items


@app.get("/approvals/pending")
def get_pending_approvals():
    return list_pending()


@app.get("/approvals/{approval_id}")
def get_approval_detail(approval_id: str):
    a = get_approval(approval_id)
    if not a:
        raise HTTPException(status_code=404, detail="Approval not found")
    return a


@app.post("/approvals/{approval_id}/approve")
async def approve(approval_id: str, request: Request):
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    a = decide(approval_id, "approve",
               decided_by=body.get("decided_by", "human"),
               note=body.get("note", ""))
    if not a:
        raise HTTPException(status_code=404, detail="Approval not found")
    if a["status"] == ApprovalStatus.APPROVED:
        # Trigger the approved action asynchronously
        _execute_approved_action(a)
    return a


@app.post("/approvals/{approval_id}/reject")
async def reject(approval_id: str, request: Request):
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    a = decide(approval_id, "reject",
               decided_by=body.get("decided_by", "human"),
               note=body.get("note", ""))
    if not a:
        raise HTTPException(status_code=404, detail="Approval not found")
    log.info("Approval %s REJECTED", approval_id)
    return a


# Browser-friendly approve/reject via GET (for email links)
@app.get("/approvals/{approval_id}/approve", response_class=HTMLResponse)
def approve_via_link(approval_id: str, by: str = "email-link"):
    a = decide(approval_id, "approve", decided_by=by)
    if not a:
        return HTMLResponse("<h2>Approval not found or expired.</h2>", status_code=404)
    if a["status"] == ApprovalStatus.APPROVED:
        _execute_approved_action(a)
        return HTMLResponse(_approval_page("✅ Approved", a, "Action has been approved and queued for execution.", "#22c55e"))
    return HTMLResponse(_approval_page("Already Decided", a, f"This approval was already {a['status']}.", "#6b7280"))


@app.get("/approvals/{approval_id}/reject", response_class=HTMLResponse)
def reject_via_link(approval_id: str, by: str = "email-link"):
    a = decide(approval_id, "reject", decided_by=by)
    if not a:
        return HTMLResponse("<h2>Approval not found or expired.</h2>", status_code=404)
    return HTMLResponse(_approval_page("❌ Rejected", a, "Action has been rejected. Ticket remains open for manual review.", "#ef4444"))


# ── Internal: execute approved action ───────────────────────────────────────

def _execute_approved_action(approval: dict):
    import threading
    def run():
        try:
            atype = approval.get("type")
            meta = approval.get("metadata", {})
            log.info("Executing approved action: %s (approval=%s)", atype, approval["approval_id"])

            if atype == "disk-space":
                from .disk_actions import expand_ebs_volume
                from .models import AlertPayload, AlertInfo, HostInfo, ClientInfo
                # Reconstruct incident from metadata
                inc = AlertPayload(
                    incident_id=approval["incident_id"],
                    source="zabbix",
                    timestamp=meta.get("alert", {}).get("timestamp", ""),
                    host=HostInfo(**meta.get("host", {})),
                    client=ClientInfo(**meta.get("client", {})),
                    alert=AlertInfo(**meta.get("alert", {})),
                )
                # Default expansion: 20GB — in prod, parse from approval note or email reply
                approved_gb = int(approval.get("decision_note", "20").split()[0]) if approval.get("decision_note") else 20
                result = expand_ebs_volume(inc, approved_gb, approval["approval_id"])
                log.info("Disk expansion result: %s", result)

            mark_executed(approval["approval_id"])

        except Exception as e:
            log.error("Approved action execution failed: %s", e)

    threading.Thread(target=run, daemon=True).start()


# ── HTML page for approval links ─────────────────────────────────────────────

def _approval_page(title: str, approval: dict, message: str, color: str) -> str:
    meta = approval.get("metadata", {})
    host = meta.get("host", {}).get("name", "?")
    client = meta.get("client", {}).get("name", "?")
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>AeonX AI Ops — {title}</title>
<style>body{{font-family:system-ui;background:#0b0e1a;color:#e8eaf6;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}
.card{{background:#141828;border:1px solid #252a45;border-radius:16px;padding:40px;max-width:480px;width:100%;text-align:center}}
h1{{font-size:28px;margin-bottom:8px;color:{color}}}
.badge{{background:{color}22;color:{color};border:1px solid {color};border-radius:8px;padding:6px 16px;display:inline-block;margin:12px 0;font-size:13px}}
.detail{{background:#1a1f35;border-radius:8px;padding:16px;text-align:left;margin:16px 0;font-size:13px;color:#8b90c0}}
</style></head>
<body><div class="card">
  <h1>{title}</h1>
  <div class="badge">{approval.get('type','').upper()} ACTION</div>
  <p style="color:#8b90c0;margin:8px 0">{message}</p>
  <div class="detail">
    <b>Host:</b> {host}<br>
    <b>Client:</b> {client}<br>
    <b>Action:</b> {approval.get('proposed_action','N/A')[:80]}<br>
    <b>Status:</b> {approval.get('status','?').upper()}
  </div>
  <p style="font-size:11px;color:#565b80">Approval ID: {approval.get('approval_id','')}</p>
</div></body></html>"""


@app.get("/health")
def health():
    pending = len(list_pending())
    return {"status": "ok", "pending_approvals": pending}
