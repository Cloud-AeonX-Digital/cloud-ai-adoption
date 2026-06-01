import boto3
import json
import os
import logging
from datetime import datetime, timezone
from .models import AlertPayload, AIDecision

log = logging.getLogger(__name__)

_BUCKET = os.environ.get("S3_INCIDENT_BUCKET", "aeonx-ai-agent-incidents")
_REGION = "ap-south-1"


def log_incident(incident: AlertPayload, decision: AIDecision) -> None:
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

    date = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    key = f"{date}/{incident.incident_id}.json"

    try:
        s3 = boto3.client("s3", region_name=_REGION)
        s3.put_object(
            Bucket=_BUCKET,
            Key=key,
            Body=json.dumps(record, indent=2),
            ContentType="application/json",
        )
        log.info("Incident logged to s3://%s/%s", _BUCKET, key)
    except Exception as e:
        # Non-fatal — alert processing continues even if S3 write fails
        log.error("S3 log failed for %s: %s", incident.incident_id, e)
