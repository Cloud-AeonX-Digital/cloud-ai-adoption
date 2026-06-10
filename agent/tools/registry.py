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
            "description": "Fetch incident history for a host from persistent memory. Returns recurring patterns, false positive count, and whether this alert has fired before. Use alert_query to also search similar incidents across all hosts.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {
                    "host_name": {"type": "string", "description": "Zabbix host name or instance ID"},
                    "hours": {"type": "integer", "description": "Look back N hours (default: 24)", "default": 24},
                    "alert_query": {"type": "string", "description": "Optional: keyword search across all incident history (e.g. 'postgresql', 'health check')"}
                },
                "required": ["host_name"]
            }}
        }
    },
    {
        "toolSpec": {
            "name": "get_disk_usage",
            "description": "Get disk usage and mount point details on a remote host via SSM. Use for disk-space alerts to see which filesystems are full, current usage %, and available space before recommending expansion.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {
                    "instance_id": {"type": "string", "description": "EC2 instance ID"},
                    "mount_point": {"type": "string", "description": "Optional specific mount point to check, e.g. /var or /data. Leave empty for all."}
                },
                "required": ["instance_id"]
            }}
        }
    },
    {
        "toolSpec": {
            "name": "get_server_info",
            "description": "Retrieve live server diagnostics from a remote host: disk usage (df -h), memory (free -m), process list (ps aux), log tails, network connections, or any read-only system information. This is a safe read operation via AWS SSM.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {
                    "instance_id": {"type": "string", "description": "EC2 instance ID"},
                    "query": {"type": "string", "description": "What to retrieve. Examples: 'disk usage', 'memory usage', 'running processes', 'last 50 lines of /var/log/app.log', 'network connections', 'uptime'"},
                    "custom_command": {"type": "string", "description": "Optional specific shell command override, e.g. 'df -h /var' or 'ps aux | head -20'"}
                },
                "required": ["instance_id", "query"]
            }}
        }
    },
    {
        "toolSpec": {
            "name": "describe_aws_resource",
            "description": "Query AWS for resource details: RDS instances, EBS volumes, ALB target health, S3 bucket sizes, security groups, ECS services. Use to answer questions about AWS infrastructure state.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {
                    "resource_type": {
                        "type": "string",
                        "enum": ["ebs_volumes", "rds_instances", "alb_target_health", "ecs_services", "security_groups", "s3_buckets"],
                        "description": "Type of AWS resource to query"
                    },
                    "instance_id": {"type": "string", "description": "EC2 instance ID (for ebs_volumes, security_groups)"},
                    "resource_id": {"type": "string", "description": "Resource ARN or ID (for alb_target_health, ecs_services)"},
                    "region": {"type": "string", "description": "AWS region, default ap-south-1"}
                },
                "required": ["resource_type"]
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
    """Query FTS5 memory store for recent alerts on this host."""
    from agent.app.memory import get_host_history, search_incidents
    host = args["host_name"]
    hours = args.get("hours", 24)
    days = max(1, hours // 24)

    history = get_host_history(host, days=max(days, 1))

    # Also do FTS search for similar alert names across all hosts
    alert_query = args.get("alert_query", "")
    similar = search_incidents(alert_query, limit=3) if alert_query else []

    return {
        "host": host,
        "total_incidents": history["total"],
        "false_positives": history["false_positives"],
        "recurring_alerts": history["recurring"],   # alerts that fired 2+ times
        "is_recurring": len(history["recurring"]) > 0,
        "recent": history["incidents"],
        "similar_on_other_hosts": similar,
    }


def _handle_get_disk_usage(args: dict) -> dict:
    import boto3
    instance_id = args["instance_id"]
    mount = args.get("mount_point", "")
    cmd = f"df -h {mount}" if mount else "df -h"
    result = _ssm_run_simple(instance_id, [cmd, "echo '---'", "lsblk -o NAME,SIZE,MOUNTPOINT,FSTYPE"])
    return {"instance_id": instance_id, "output": result}


def _handle_get_server_info(args: dict) -> dict:
    instance_id = args["instance_id"]
    query = args.get("query", "").lower()
    custom = args.get("custom_command", "")

    # Map natural language queries to safe read-only commands
    if custom:
        command = custom
    elif "disk" in query or "df" in query or "mount" in query or "storage" in query:
        command = "df -h"
    elif "memory" in query or "ram" in query or "free" in query:
        command = "free -m && echo '---' && cat /proc/meminfo | grep -E 'MemTotal|MemFree|MemAvailable'"
    elif "process" in query or "cpu" in query or "top" in query:
        command = "ps aux --sort=-%cpu | head -15"
    elif "log" in query:
        # Extract log path if mentioned
        import re
        path = re.search(r'(/[/\w\.-]+\.log)', query)
        command = f"tail -50 {path.group(1)}" if path else "journalctl -n 50 --no-pager"
    elif "network" in query or "connection" in query or "port" in query:
        command = "ss -tlnp"
    elif "uptime" in query or "load" in query:
        command = "uptime && cat /proc/loadavg"
    else:
        command = f"echo 'Query: {query}' && uptime && df -h && free -m"

    result = _ssm_run_simple(instance_id, [command])
    return {"instance_id": instance_id, "query": query, "command": command, "output": result}


def _handle_describe_aws_resource(args: dict) -> dict:
    import boto3
    region = args.get("region", os.environ.get("AWS_REGION", "ap-south-1"))
    rtype = args["resource_type"]
    instance_id = args.get("instance_id", "")
    resource_id = args.get("resource_id", "")
    try:
        if rtype == "ebs_volumes":
            ec2 = boto3.client("ec2", region_name=region)
            filters = [{"Name": "attachment.instance-id", "Values": [instance_id]}] if instance_id else []
            vols = ec2.describe_volumes(Filters=filters)["Volumes"]
            return {"volumes": [{"id": v["VolumeId"], "size_gb": v["Size"], "type": v["VolumeType"],
                "state": v["State"], "mount": v["Attachments"][0]["Device"] if v["Attachments"] else "detached"} for v in vols]}

        elif rtype == "rds_instances":
            rds = boto3.client("rds", region_name=region)
            dbs = rds.describe_db_instances()["DBInstances"]
            return {"rds_instances": [{"id": d["DBInstanceIdentifier"], "class": d["DBInstanceClass"],
                "engine": d["Engine"] + " " + d["EngineVersion"], "status": d["DBInstanceStatus"],
                "storage_gb": d["AllocatedStorage"]} for d in dbs]}

        elif rtype == "ecs_services":
            ecs = boto3.client("ecs", region_name=region)
            clusters = ecs.list_clusters()["clusterArns"]
            services = []
            for c in clusters[:3]:
                svcs = ecs.list_services(cluster=c)["serviceArns"]
                if svcs:
                    detail = ecs.describe_services(cluster=c, services=svcs[:5])["services"]
                    services += [{"name": s["serviceName"], "desired": s["desiredCount"],
                        "running": s["runningCount"], "status": s["status"]} for s in detail]
            return {"ecs_services": services}

        elif rtype == "alb_target_health":
            elbv2 = boto3.client("elbv2", region_name=region)
            tg_arn = resource_id
            health = elbv2.describe_target_health(TargetGroupArn=tg_arn)["TargetHealthDescriptions"]
            return {"targets": [{"id": t["Target"]["Id"], "port": t["Target"]["Port"],
                "state": t["TargetHealth"]["State"]} for t in health]}

        else:
            return {"error": f"resource_type '{rtype}' not yet implemented"}
    except Exception as e:
        return {"error": str(e)}


def _ssm_run_simple(instance_id: str, commands: list) -> str:
    """Helper: run SSM commands and return stdout as string."""
    import boto3, time
    try:
        ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "ap-south-1"))
        resp = ssm.send_command(InstanceIds=[instance_id], DocumentName="AWS-RunShellScript",
                                Parameters={"commands": commands})
        cmd_id = resp["Command"]["CommandId"]
        for _ in range(12):
            time.sleep(5)
            try:
                inv = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=instance_id)
                if inv["Status"] in ("Success", "Failed", "Cancelled", "TimedOut"):
                    return inv.get("StandardOutputContent", inv.get("StandardErrorContent", ""))[:2000]
            except ssm.exceptions.InvocationDoesNotExist:
                continue
        return "Timed out"
    except Exception as e:
        return str(e)


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
    "get_disk_usage": _handle_get_disk_usage,
    "get_server_info": _handle_get_server_info,
    "describe_aws_resource": _handle_describe_aws_resource,
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
