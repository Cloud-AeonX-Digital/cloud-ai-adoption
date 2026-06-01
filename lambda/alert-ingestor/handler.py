import json
import uuid
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone


AGENT_URL = os.environ["AGENT_URL"]  # e.g. http://10.0.1.x:8000/alert

SEVERITY_MAP = {
    "not classified": "not_classified",
    "information": "info",
    "warning": "warning",
    "average": "average",
    "high": "high",
    "disaster": "disaster",
}


def normalize(payload: dict) -> dict:
    severity_raw = payload.get("trigger_severity", "").lower()
    status_raw = payload.get("trigger_status", "").upper()

    return {
        "incident_id": str(uuid.uuid4()),
        "source": "zabbix",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "client": {
            "name": payload.get("host_name", ""),
            "aws_account": payload.get("aws_account", ""),
            "host_group_id": payload.get("host_group_id", ""),
        },
        "host": {
            "name": payload.get("host_name", ""),
            "ip": payload.get("host_ip", ""),
            "zabbix_host_id": payload.get("host_id", ""),
            "cloud": "aws",
            "instance_id": payload.get("instance_id", ""),
        },
        "alert": {
            "name": payload.get("trigger_name", ""),
            "severity": SEVERITY_MAP.get(severity_raw, severity_raw),
            "status": "problem" if status_raw == "PROBLEM" else "resolved",
            "trigger_id": payload.get("trigger_id", ""),
            "event_id": payload.get("event_id", ""),
            "item_value": payload.get("item_value", ""),
        },
        "raw": payload,
    }


def forward(incident: dict) -> None:
    body = json.dumps(incident).encode()
    req = urllib.request.Request(
        AGENT_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        status = resp.status
        if status not in (200, 202):
            raise RuntimeError(f"Agent returned HTTP {status}")


def lambda_handler(event, context):
    try:
        body = event.get("body", "")
        if isinstance(body, str):
            payload = json.loads(body)
        else:
            payload = body or {}

        incident = normalize(payload)
        forward(incident)

        return {"statusCode": 200, "body": json.dumps({"incident_id": incident["incident_id"]})}

    except (json.JSONDecodeError, KeyError) as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}
    except urllib.error.URLError as e:
        # Agent unreachable — log and return 502 so Zabbix can retry
        print(f"ERROR forwarding to agent: {e}")
        return {"statusCode": 502, "body": json.dumps({"error": "agent unreachable"})}
