"""
Dev S3 mock — writes incident JSON to local filesystem instead of AWS S3.
"""
import json
import os
import logging
from datetime import datetime, timezone
from agent.app.models import AlertPayload, AIDecision

log = logging.getLogger(__name__)

_OUTPUT_DIR = os.environ.get("DEV_S3_DIR", "./output/incidents")


def log_incident(incident: AlertPayload, decision: AIDecision) -> None:
    date = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    out_dir = os.path.join(_OUTPUT_DIR, date)
    os.makedirs(out_dir, exist_ok=True)

    record = {
        "incident_id": incident.incident_id,
        "source": incident.source,
        "timestamp": incident.timestamp,
        "client": incident.client.model_dump(),
        "host": incident.host.model_dump(),
        "alert": incident.alert.model_dump(),
        "decision": decision.model_dump(),
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }

    path = os.path.join(out_dir, f"{incident.incident_id}.json")
    with open(path, "w") as f:
        json.dump(record, f, indent=2)

    log.info("[DEV] Incident logged to %s", path)
