"""
Human Approval Manager

Handles alerts that require human approval before the agent acts.
Currently used for: S008 (disk space expansion)

Flow:
  1. Alert comes in → classifier returns action="human-approval-required"
  2. approval_manager.request_approval() called → stores pending approval + sends email with approve/reject links
  3. Human clicks approve link → POST /approvals/{id}/approve
  4. Agent executes the approved action (e.g. expand EBS volume)
  5. Sends resolution email + logs to S3
"""

import json
import os
import threading
import uuid
import logging
from datetime import datetime, timezone, timedelta
from enum import Enum

log = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTED = "executed"


# In-memory store (survives restarts via S3/file in prod)
_store: dict[str, dict] = {}
_lock = threading.Lock()

# Approval expiry (24 hours)
_TTL_HOURS = 24

# Base URL for approval links — set via env var
_BASE_URL = os.environ.get("AGENT_BASE_URL", "http://172.25.29.253:8000")


def request_approval(
    incident_id: str,
    approval_type: str,
    description: str,
    proposed_action: str,
    metadata: dict,
) -> str:
    """
    Store a pending approval and return the approval ID.
    Caller is responsible for sending the notification email.
    """
    approval_id = str(uuid.uuid4())
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=_TTL_HOURS)).isoformat()

    with _lock:
        _store[approval_id] = {
            "approval_id": approval_id,
            "incident_id": incident_id,
            "type": approval_type,
            "description": description,
            "proposed_action": proposed_action,
            "metadata": metadata,
            "status": ApprovalStatus.PENDING,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at,
            "decided_at": None,
            "decided_by": None,
            "decision_note": None,
            "approve_url": f"{_BASE_URL}/approvals/{approval_id}/approve",
            "reject_url": f"{_BASE_URL}/approvals/{approval_id}/reject",
        }

    log.info("Approval requested: %s | type=%s | incident=%s", approval_id, approval_type, incident_id)
    return approval_id


def get_approval(approval_id: str) -> dict | None:
    with _lock:
        entry = _store.get(approval_id)
        if not entry:
            return None
        # Check expiry
        if entry["status"] == ApprovalStatus.PENDING:
            expires = datetime.fromisoformat(entry["expires_at"])
            if datetime.now(timezone.utc) > expires:
                entry["status"] = ApprovalStatus.EXPIRED
        return dict(entry)


def decide(approval_id: str, decision: str, decided_by: str = "human", note: str = "") -> dict | None:
    """decision: 'approve' or 'reject'"""
    with _lock:
        entry = _store.get(approval_id)
        if not entry:
            return None
        if entry["status"] != ApprovalStatus.PENDING:
            return entry  # already decided
        entry["status"] = ApprovalStatus.APPROVED if decision == "approve" else ApprovalStatus.REJECTED
        entry["decided_at"] = datetime.now(timezone.utc).isoformat()
        entry["decided_by"] = decided_by
        entry["decision_note"] = note
    log.info("Approval %s: %s by %s", approval_id, decision.upper(), decided_by)
    return dict(entry)


def mark_executed(approval_id: str) -> None:
    with _lock:
        if approval_id in _store:
            _store[approval_id]["status"] = ApprovalStatus.EXECUTED


def list_pending() -> list:
    now = datetime.now(timezone.utc)
    with _lock:
        result = []
        for entry in _store.values():
            e = dict(entry)
            if e["status"] == ApprovalStatus.PENDING:
                if datetime.fromisoformat(e["expires_at"]) < now:
                    e["status"] = ApprovalStatus.EXPIRED
                    _store[e["approval_id"]]["status"] = ApprovalStatus.EXPIRED
                else:
                    result.append(e)
        return result


def list_all() -> list:
    with _lock:
        return [dict(e) for e in _store.values()]
