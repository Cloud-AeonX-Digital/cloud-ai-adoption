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
                    "host_name": {"type": "string", "description": "Host name to filter by. Pass empty string to search all hosts."},
                    "hours": {"type": "integer", "description": "Look back N hours (default: 24)", "default": 24},
                    "alert_query": {"type": "string", "description": "Keyword search across all incident history (e.g. 'postgresql', 'health check', 'disk')"}
                },
                "required": []
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
            "name": "get_cost_breakdown",
            "description": "Get AWS cost breakdown by service. Use for any cost/billing question. Supports filtering by service name (partial match), specific month (e.g. 'June', '2026-06'), or custom date range.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Number of past days to look back (default: 30 for monthly view)", "default": 30},
                    "month": {"type": "string", "description": "Specific month to query, e.g. '2026-06' or 'June'. If provided, overrides days."},
                    "start_date": {"type": "string", "description": "Start date YYYY-MM-DD (optional, overrides days/month)"},
                    "end_date": {"type": "string", "description": "End date YYYY-MM-DD (optional)"},
                    "service_filter": {"type": "string", "description": "Filter to a specific service by keyword, e.g. 'Bedrock', 'EC2', 'RDS', 'S3'"},
                    "granularity": {"type": "string", "enum": ["DAILY", "MONTHLY"], "default": "MONTHLY"}
                },
                "required": []
            }}
        }
    },
    {
        "toolSpec": {
            "name": "get_cost_anomalies",
            "description": "Get AWS Cost Anomaly Detection alerts — services or accounts with unexpected cost spikes. Use when asked about cost surprises, billing alerts, or unexpected charges.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Look back N days (default: 14)", "default": 14},
                    "min_impact_usd": {"type": "number", "description": "Minimum dollar impact to include (default: 1.0)", "default": 1.0}
                },
                "required": []
            }}
        }
    },
    {
        "toolSpec": {
            "name": "flag_idle_resources",
            "description": "Find idle or orphaned AWS resources that are accruing cost: unattached EBS volumes, unused Elastic IPs, stopped EC2 instances, old snapshots. Use to answer cost optimization questions.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {
                    "resource_types": {"type": "array", "items": {"type": "string"}, "description": "Types to check: ebs_volumes, elastic_ips, stopped_ec2, snapshots. Default: all."}
                },
                "required": []
            }}
        }
    },
    {
        "toolSpec": {
            "name": "get_security_findings",
            "description": "Get security issues: Security Hub findings (if enabled), public S3 buckets, security groups with 0.0.0.0/0 open ports, and IAM users without MFA. Returns actionable findings.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {
                    "check_types": {"type": "array", "items": {"type": "string"}, "description": "Types to check: security_hub, public_s3, open_security_groups, iam_mfa. Default: all available."},
                    "severity": {"type": "string", "enum": ["CRITICAL", "HIGH", "MEDIUM", "ALL"], "default": "HIGH"}
                },
                "required": []
            }}
        }
    },
    {
        "toolSpec": {
            "name": "get_secrets_rotation_status",
            "description": "Check AWS Secrets Manager and SSM Parameter Store for secrets/parameters that haven't been rotated recently.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {
                    "days_threshold": {"type": "integer", "description": "Flag secrets not rotated in this many days (default: 90)", "default": 90}
                },
                "required": []
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
    host = args.get("host_name", "")
    hours = args.get("hours", 24)
    days = max(1, hours // 24)
    alert_query = args.get("alert_query", "")

    history = get_host_history(host, days=max(days, 1)) if host else {"total": 0, "false_positives": 0, "recurring": [], "incidents": []}

    # FTS search — use alert_query if provided, else use host as keyword
    query_term = alert_query or host
    similar = search_incidents(query_term, host=host if host else "", limit=5) if query_term else []

    return {
        "host": host or "all",
        "total_incidents": history["total"],
        "false_positives": history["false_positives"],
        "recurring_alerts": history["recurring"],
        "is_recurring": len(history["recurring"]) > 0,
        "recent": history["incidents"],
        "search_results": similar,
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


def _handle_get_cost_breakdown(args: dict) -> dict:
    import boto3
    from datetime import datetime, timezone, timedelta, date
    import calendar

    granularity = args.get("granularity", "MONTHLY")
    service_filter = args.get("service_filter", "")
    today = datetime.now(timezone.utc).date()

    # Resolve date range — month > start_date/end_date > days
    if args.get("month"):
        m = args["month"].strip()
        # Accept "June", "june", "2026-06", "06"
        month_map = {"january":"01","february":"02","march":"03","april":"04","may":"05","june":"06",
                     "july":"07","august":"08","september":"09","october":"10","november":"11","december":"12"}
        if m.lower() in month_map:
            m = f"{today.year}-{month_map[m.lower()]}"
        try:
            y, mo = int(m[:4]), int(m[5:7])
            start = date(y, mo, 1)
            last_day = calendar.monthrange(y, mo)[1]
            end = min(date(y, mo, last_day) + timedelta(days=1), today + timedelta(days=1))
        except Exception:
            start = today.replace(day=1)
            end = today + timedelta(days=1)
    elif args.get("start_date") and args.get("end_date"):
        start = date.fromisoformat(args["start_date"])
        end = date.fromisoformat(args["end_date"]) + timedelta(days=1)
    else:
        days = args.get("days", 30)
        start = today - timedelta(days=days)
        end = today + timedelta(days=1)

    # Clamp end to today+1 (CE doesn't accept future dates)
    end = min(end, today + timedelta(days=1))

    try:
        ce = boto3.client("ce", region_name="us-east-1")
        params = dict(
            TimePeriod={"Start": str(start), "End": str(end)},
            Granularity=granularity,
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )
        if service_filter:
            # CE SERVICE dimension only supports EQUALS — do client-side filter instead
            params.pop("GroupBy", None)
            params["GroupBy"] = [{"Type": "DIMENSION", "Key": "SERVICE"}]
            # Remove filter from params and apply post-query
            pass

        resp = ce.get_cost_and_usage(**params)

        totals = {}
        for period in resp["ResultsByTime"]:
            for g in period["Groups"]:
                svc = g["Keys"][0]
                amt = float(g["Metrics"]["UnblendedCost"]["Amount"])
                if amt > 0:
                    # Client-side partial match for service_filter
                    if service_filter and service_filter.lower() not in svc.lower():
                        continue
                    totals[svc] = totals.get(svc, 0) + amt

        top = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:15]

        if not top and service_filter:
            return {
                "period": f"{start} to {end - timedelta(days=1)}",
                "service_filter": service_filter,
                "total_usd": 0.0,
                "services": [],
                "note": f"No costs found for '{service_filter}' in this period. It may not be used in this account."
            }

        return {
            "period": f"{start} to {end - timedelta(days=1)}",
            "service_filter": service_filter or "all",
            "total_usd": round(sum(v for _, v in top), 4),
            "services": [{"service": k, "cost_usd": round(v, 4)} for k, v in top],
        }
    except Exception as e:
        return {"error": str(e)}


def _handle_get_cost_anomalies(args: dict) -> dict:
    import boto3
    from datetime import datetime, timezone, timedelta
    days = args.get("days", 14)
    min_impact = args.get("min_impact_usd", 1.0)
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        ce = boto3.client("ce", region_name="us-east-1")
        resp = ce.get_anomalies(
            DateInterval={"StartDate": start, "EndDate": end},
            TotalImpact={"NumericOperator": "GREATER_THAN_OR_EQUAL", "StartValue": min_impact},
        )
        anomalies = []
        for a in resp.get("Anomalies", []):
            impact = a.get("Impact", {})
            anomalies.append({
                "id": a["AnomalyId"][:12],
                "service": a.get("DimensionValue", "unknown"),
                "start_date": a.get("AnomalyStartDate", ""),
                "total_impact_usd": round(float(impact.get("TotalImpact", 0)), 2),
                "expected_spend": round(float(impact.get("TotalExpectedSpend", 0)), 2),
                "actual_spend": round(float(impact.get("TotalActualSpend", 0)), 2),
            })
        return {
            "period": f"{start} to {end}",
            "anomalies_found": len(anomalies),
            "anomalies": anomalies,
        }
    except Exception as e:
        return {"error": str(e)}


def _handle_flag_idle_resources(args: dict) -> dict:
    import boto3
    region = os.environ.get("AWS_REGION", "ap-south-1")
    checks = args.get("resource_types") or ["ebs_volumes", "elastic_ips", "stopped_ec2"]
    results = {}
    try:
        ec2 = boto3.client("ec2", region_name=region)
        if "ebs_volumes" in checks:
            vols = ec2.describe_volumes(Filters=[{"Name": "status", "Values": ["available"]}])["Volumes"]
            results["unattached_ebs"] = [{"id": v["VolumeId"], "size_gb": v["Size"],
                "type": v["VolumeType"], "created": str(v["CreateTime"])[:10]} for v in vols]

        if "elastic_ips" in checks:
            eips = ec2.describe_addresses()["Addresses"]
            results["unused_eips"] = [{"ip": e["PublicIp"], "allocation_id": e.get("AllocationId","")}
                for e in eips if "InstanceId" not in e]

        if "stopped_ec2" in checks:
            stopped = ec2.describe_instances(
                Filters=[{"Name": "instance-state-name", "Values": ["stopped"]}])["Reservations"]
            insts = []
            for r in stopped:
                for i in r["Instances"]:
                    tags = {t["Key"]: t["Value"] for t in i.get("Tags", [])}
                    insts.append({"id": i["InstanceId"], "type": i["InstanceType"],
                        "name": tags.get("Name", ""), "stopped_reason": i.get("StateTransitionReason","")[:50]})
            results["stopped_instances"] = insts

        idle_count = sum(len(v) for v in results.values())
        return {"region": region, "idle_resources_found": idle_count, **results}
    except Exception as e:
        return {"error": str(e)}


def _handle_get_security_findings(args: dict) -> dict:
    import boto3
    region = os.environ.get("AWS_REGION", "ap-south-1")
    checks = args.get("check_types") or ["public_s3", "open_security_groups", "iam_mfa"]
    results = {}
    try:
        # Security Hub (optional — may not be enabled)
        if "security_hub" in checks:
            try:
                sh = boto3.client("securityhub", region_name=region)
                sev = args.get("severity", "HIGH")
                filters = {} if sev == "ALL" else {"SeverityLabel": [{"Value": sev, "Comparison": "EQUALS"}]}
                findings = sh.get_findings(Filters=filters, MaxResults=10)["Findings"]
                results["security_hub"] = [{"title": f["Title"], "severity": f["Severity"]["Label"],
                    "resource": f["Resources"][0]["Id"] if f.get("Resources") else ""} for f in findings]
            except Exception as e:
                results["security_hub"] = {"note": f"Not enabled or no access: {e}"}

        # Public S3 buckets
        if "public_s3" in checks:
            try:
                s3 = boto3.client("s3", region_name=region)
                buckets = s3.list_buckets()["Buckets"]
                public = []
                for b in buckets[:20]:  # limit to avoid throttling
                    try:
                        acl = s3.get_bucket_acl(Bucket=b["Name"])
                        for grant in acl["Grants"]:
                            grantee = grant.get("Grantee", {})
                            if grantee.get("URI", "").endswith("AllUsers") or grantee.get("URI", "").endswith("AuthenticatedUsers"):
                                public.append({"bucket": b["Name"], "permission": grant["Permission"]})
                    except Exception:
                        pass
                results["public_s3_buckets"] = public
            except Exception as e:
                results["public_s3_buckets"] = {"error": str(e)}

        # Security groups with 0.0.0.0/0
        if "open_security_groups" in checks:
            try:
                ec2 = boto3.client("ec2", region_name=region)
                sgs = ec2.describe_security_groups()["SecurityGroups"]
                open_sgs = []
                for sg in sgs:
                    for perm in sg.get("IpPermissions", []):
                        for r in perm.get("IpRanges", []):
                            if r.get("CidrIp") == "0.0.0.0/0":
                                port = perm.get("FromPort", "all")
                                open_sgs.append({"sg_id": sg["GroupId"], "name": sg.get("GroupName",""),
                                    "port": port, "protocol": perm.get("IpProtocol","-1")})
                results["open_security_groups"] = open_sgs[:20]
            except Exception as e:
                results["open_security_groups"] = {"error": str(e)}

        # IAM users without MFA
        if "iam_mfa" in checks:
            try:
                iam = boto3.client("iam", region_name="us-east-1")
                users = iam.list_users()["Users"]
                no_mfa = []
                for u in users:
                    mfa = iam.list_mfa_devices(UserName=u["UserName"])["MFADevices"]
                    if not mfa:
                        no_mfa.append({"user": u["UserName"], "created": str(u["CreateDate"])[:10]})
                results["iam_users_without_mfa"] = no_mfa
            except Exception as e:
                results["iam_users_without_mfa"] = {"error": str(e)}

        total_issues = sum(len(v) if isinstance(v, list) else 0 for v in results.values())
        return {"total_issues": total_issues, **results}
    except Exception as e:
        return {"error": str(e)}


def _handle_get_secrets_rotation_status(args: dict) -> dict:
    import boto3
    from datetime import datetime, timezone, timedelta
    region = os.environ.get("AWS_REGION", "ap-south-1")
    threshold = args.get("days_threshold", 90)
    cutoff = datetime.now(timezone.utc) - timedelta(days=threshold)
    results = {"stale_secrets": [], "threshold_days": threshold}
    try:
        sm = boto3.client("secretsmanager", region_name=region)
        paginator = sm.get_paginator("list_secrets")
        for page in paginator.paginate():
            for s in page["SecretList"]:
                last = s.get("LastRotatedDate") or s.get("LastChangedDate")
                if last and last.replace(tzinfo=timezone.utc) < cutoff:
                    results["stale_secrets"].append({
                        "name": s["Name"],
                        "last_rotated": str(last)[:10],
                        "rotation_enabled": s.get("RotationEnabled", False),
                    })
    except Exception as e:
        results["error"] = str(e)
    results["stale_count"] = len(results["stale_secrets"])
    return results


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
    # Phase F — Cost & Security
    "get_cost_breakdown": _handle_get_cost_breakdown,
    "get_cost_anomalies": _handle_get_cost_anomalies,
    "flag_idle_resources": _handle_flag_idle_resources,
    "get_security_findings": _handle_get_security_findings,
    "get_secrets_rotation_status": _handle_get_secrets_rotation_status,
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
