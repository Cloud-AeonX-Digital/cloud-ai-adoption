"""
Tool registry — defines all tools the agent can call.
Each tool: a Bedrock-compatible spec + a Python handler.
"""
import json, os, logging
from typing import Any

log = logging.getLogger(__name__)

# ── Tool specs (Bedrock Converse format) ────────────────────────────────────

TOOL_SPECS = [
    {
        "toolSpec": {
            "name": "search_runbook",
            "description": "Search the knowledge base for known solutions to this alert. Returns the solution ID, recommended action, steps, and whether auto-remediation is possible.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {
                    "alert_name": {"type": "string", "description": "The exact alert/trigger name from monitoring system"}
                },
                "required": ["alert_name"]
            }}
        }
    },
    {
        "toolSpec": {
            "name": "get_service_status",
            "description": "Check if a systemd service is currently running on a remote host via SSM. Use this to confirm the service is actually down before recommending a restart.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {
                    "instance_id": {"type": "string", "description": "EC2 instance ID"},
                    "service_name": {"type": "string", "description": "systemd service name, e.g. cmt-backend, postgresql, nginx"}
                },
                "required": ["instance_id", "service_name"]
            }}
        }
    },
    {
        "toolSpec": {
            "name": "get_ec2_info",
            "description": "Get EC2 instance metadata: state, instance type, tags, launch time, and auto-restart eligibility.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {
                    "instance_id": {"type": "string", "description": "EC2 instance ID"}
                },
                "required": ["instance_id"]
            }}
        }
    },
    {
        "toolSpec": {
            "name": "query_cloudwatch_metric",
            "description": "Fetch the last N minutes of a CloudWatch metric (e.g. CPUUtilization, FreeStorageSpace, NetworkIn). Use to confirm anomaly before acting.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string", "description": "CloudWatch namespace, e.g. AWS/EC2"},
                    "metric_name": {"type": "string", "description": "Metric name, e.g. CPUUtilization"},
                    "instance_id": {"type": "string", "description": "EC2 instance ID"},
                    "minutes": {"type": "integer", "description": "Lookback window in minutes (default: 30)", "default": 30}
                },
                "required": ["namespace", "metric_name", "instance_id"]
            }}
        }
    },
    {
        "toolSpec": {
            "name": "get_recent_alerts",
            "description": "Fetch recent alerts for the same host from incident history. Use to detect recurring patterns or ongoing incidents.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {
                    "host_name": {"type": "string", "description": "Zabbix host name"},
                    "hours": {"type": "integer", "description": "Look back N hours (default: 24)", "default": 24}
                },
                "required": ["host_name"]
            }}
        }
    },
    {
        "toolSpec": {
            "name": "request_human_approval",
            "description": "Submit a proposed remediation action for human approval. Call this ONLY after gathering enough context. The action will NOT execute until a human approves it in the UI or via email.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {
                    "action_type": {"type": "string", "enum": ["service_restart", "ec2_restart", "disk_expand", "notify_client", "create_ticket", "escalate"], "description": "Type of action to execute after approval"},
                    "target_service": {"type": "string", "description": "Service name or resource identifier (e.g. cmt-backend, i-0abc123)"},
                    "reason": {"type": "string", "description": "Why this action is recommended — shown to the approver"},
                    "commands": {"type": "array", "items": {"type": "string"}, "description": "Exact commands that will run post-approval"},
                    "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                    "confidence": {"type": "number", "description": "Agent confidence 0.0-1.0"}
                },
                "required": ["action_type", "reason", "severity", "confidence"]
            }}
        }
    },
]


# ── Tool handlers ───────────────────────────────────────────────────────────

def _handle_search_runbook(args: dict) -> dict:
    alert_name = args["alert_name"]
    kb_path = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "known-solutions.json"
    ))
    with open(kb_path) as f:
        solutions = json.load(f)["solutions"]
    name_lower = alert_name.lower()
    for entry in solutions:
        if entry["pattern"].lower() in name_lower:
            return {
                "found": True,
                "solution_id": entry["id"],
                "category": entry["category"],
                "severity": entry["severity"],
                "actionable": entry["actionable"],
                "recommended_action": entry.get("action", ""),
                "steps": entry.get("steps", []),
                "notes": f"KB pattern '{entry['pattern']}' matched with high confidence."
            }
    return {"found": False, "notes": "No known solution. Use LLM reasoning to determine best action."}


def _handle_get_service_status(args: dict) -> dict:
    import boto3
    instance_id = args["instance_id"]
    service = args["service_name"]
    try:
        ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "ap-south-1"))
        resp = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": [f"systemctl is-active {service}"]}
        )
        cmd_id = resp["Command"]["CommandId"]
        import time; time.sleep(4)
        out = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=instance_id)
        status = out["StandardOutputContent"].strip()
        return {"service": service, "status": status, "is_running": status == "active"}
    except Exception as e:
        return {"service": service, "status": "unknown", "error": str(e)}


def _handle_get_ec2_info(args: dict) -> dict:
    import boto3
    instance_id = args["instance_id"]
    try:
        ec2 = boto3.client("ec2", region_name=os.environ.get("AWS_REGION", "ap-south-1"))
        r = ec2.describe_instances(InstanceIds=[instance_id])
        inst = r["Reservations"][0]["Instances"][0]
        tags = {t["Key"]: t["Value"] for t in inst.get("Tags", [])}
        return {
            "instance_id": instance_id,
            "state": inst["State"]["Name"],
            "instance_type": inst["InstanceType"],
            "launch_time": str(inst["LaunchTime"]),
            "auto_restart_eligible": tags.get("auto-restart", "false").lower() == "true",
            "name": tags.get("Name", ""),
            "env": tags.get("env", ""),
        }
    except Exception as e:
        return {"instance_id": instance_id, "error": str(e)}


def _handle_query_cloudwatch_metric(args: dict) -> dict:
    import boto3
    from datetime import datetime, timezone, timedelta
    try:
        cw = boto3.client("cloudwatch", region_name=os.environ.get("AWS_REGION", "ap-south-1"))
        minutes = args.get("minutes", 30)
        resp = cw.get_metric_statistics(
            Namespace=args["namespace"],
            MetricName=args["metric_name"],
            Dimensions=[{"Name": "InstanceId", "Value": args["instance_id"]}],
            StartTime=datetime.now(timezone.utc) - timedelta(minutes=minutes),
            EndTime=datetime.now(timezone.utc),
            Period=300, Statistics=["Average", "Maximum"],
        )
        points = sorted(resp["Datapoints"], key=lambda x: x["Timestamp"])
        if not points:
            return {"metric": args["metric_name"], "datapoints": [], "summary": "No data in window"}
        latest = points[-1]
        return {
            "metric": args["metric_name"],
            "latest_avg": round(latest.get("Average", 0), 2),
            "latest_max": round(latest.get("Maximum", 0), 2),
            "unit": latest.get("Unit", ""),
            "datapoints": len(points),
            "summary": f"{args['metric_name']}: avg={latest.get('Average',0):.1f}, max={latest.get('Maximum',0):.1f} {latest.get('Unit','')} over last {minutes}m"
        }
    except Exception as e:
        return {"metric": args["metric_name"], "error": str(e)}


def _handle_get_recent_alerts(args: dict) -> dict:
    """Query Express backend for recent alerts on this host."""
    import urllib.request
    host = args["host_name"]
    hours = args.get("hours", 24)
    try:
        url = f"http://localhost:3001/incidents?host={urllib.request.quote(host)}&hours={hours}&limit=10"
        with urllib.request.urlopen(url, timeout=5) as r:
            incidents = json.loads(r.read())
        return {
            "host": host,
            "count": len(incidents),
            "recent": [{"name": i.get("alert_name",""), "severity": i.get("severity",""), "ts": i.get("created_at","")} for i in incidents[:5]],
            "recurring": len(incidents) > 3,
        }
    except Exception as e:
        return {"host": host, "count": 0, "error": str(e)}


def _handle_request_human_approval(args: dict) -> dict:
    # This is a sentinel — the agent_loop intercepts this and converts it to an ApprovalRequest
    # Returning the args lets agent_loop extract and create the actual approval
    return {"status": "approval_requested", **args}


# ── Dispatch ────────────────────────────────────────────────────────────────

_HANDLERS = {
    "search_runbook": _handle_search_runbook,
    "get_service_status": _handle_get_service_status,
    "get_ec2_info": _handle_get_ec2_info,
    "query_cloudwatch_metric": _handle_query_cloudwatch_metric,
    "get_recent_alerts": _handle_get_recent_alerts,
    "request_human_approval": _handle_request_human_approval,
}


def execute_tool(name: str, args: dict) -> Any:
    handler = _HANDLERS.get(name)
    if not handler:
        return {"error": f"Unknown tool: {name}"}
    log.info("[TOOL] %s(%s)", name, {k: v for k, v in args.items() if k != "commands"})
    result = handler(args)
    log.info("[TOOL] %s → %s", name, str(result)[:120])
    return result
