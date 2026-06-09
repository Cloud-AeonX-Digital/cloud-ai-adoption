"""
SSM Action Executor

Runs service restart and EC2 restart actions after human approval.
Called from dev_app.py when an approval is confirmed.
"""
import boto3
import json
import logging
import os
import time

log = logging.getLogger(__name__)

_REGION = os.environ.get("AWS_REGION", "ap-south-1")

# Map service name patterns to systemctl service names
SERVICE_MAP = {
    "cmt-backend":    "cmt-backend",
    "cmt-frontend":   "cmt-frontend",
    "postgresql":     "postgresql",
    "zabbix-agent2":  "zabbix-agent2",
    "nginx":          "nginx",
    "apache2":        "apache2",
    "AwsReplicationVolumeUpdaterService": "AwsReplicationVolumeUpdaterService",
}


def _ssm_run(instance_id: str, commands: list[str], aws_account: str = None, timeout: int = 60) -> dict:
    """Run SSM commands on instance. Returns {success, output, error}"""
    try:
        session = _get_session(aws_account)
        ssm = session.client("ssm", region_name=_REGION)

        resp = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": commands},
            TimeoutSeconds=timeout,
        )
        cmd_id = resp["Command"]["CommandId"]

        # Poll for result (max 60s)
        for _ in range(12):
            time.sleep(5)
            try:
                inv = ssm.get_command_invocation(
                    CommandId=cmd_id, InstanceId=instance_id
                )
                status = inv["Status"]
                if status in ("Success", "Failed", "Cancelled", "TimedOut"):
                    return {
                        "success": status == "Success",
                        "output": inv.get("StandardOutputContent", ""),
                        "error": inv.get("StandardErrorContent", ""),
                        "status": status,
                    }
            except ssm.exceptions.InvocationDoesNotExist:
                continue

        return {"success": False, "output": "", "error": "Timed out waiting for SSM result", "status": "TimedOut"}

    except Exception as e:
        log.error("SSM run failed: %s", e)
        return {"success": False, "output": "", "error": str(e), "status": "Error"}


def restart_service(instance_id: str, service_name: str, aws_account: str = None) -> dict:
    """Restart a Linux systemd service via SSM."""
    svc = SERVICE_MAP.get(service_name, service_name)
    log.info("SSM service restart: %s on %s", svc, instance_id)

    result = _ssm_run(instance_id, [
        f"sudo systemctl restart {svc}",
        "sleep 3",
        f"systemctl is-active {svc}",
        f"echo STATUS=$(systemctl is-active {svc})",
    ], aws_account)

    result["service"] = svc
    if result["success"]:
        log.info("Service %s restarted on %s: %s", svc, instance_id, result["output"].strip())
    else:
        log.error("Service restart failed: %s", result["error"])

    return result


def restart_ec2(instance_id: str, aws_account: str = None) -> dict:
    """Stop and start EC2 instance (requires auto-restart=true tag)."""
    try:
        session = _get_session(aws_account)
        ec2 = session.client("ec2", region_name=_REGION)

        # Verify tag
        tags = ec2.describe_tags(Filters=[
            {"Name": "resource-id", "Values": [instance_id]},
            {"Name": "key", "Values": ["auto-restart"]},
        ])["Tags"]

        if not any(t["Value"] == "true" for t in tags):
            return {"success": False, "error": f"Instance {instance_id} not tagged auto-restart=true"}

        log.info("EC2 restart: %s", instance_id)
        ec2.stop_instances(InstanceIds=[instance_id])

        # Wait until stopped
        waiter = ec2.get_waiter("instance_stopped")
        waiter.wait(InstanceIds=[instance_id], WaiterConfig={"MaxAttempts": 20, "Delay": 10})

        ec2.start_instances(InstanceIds=[instance_id])
        waiter2 = ec2.get_waiter("instance_running")
        waiter2.wait(InstanceIds=[instance_id], WaiterConfig={"MaxAttempts": 20, "Delay": 10})

        return {"success": True, "output": f"Instance {instance_id} restarted", "status": "Success"}

    except Exception as e:
        log.error("EC2 restart failed: %s", e)
        return {"success": False, "error": str(e), "status": "Error"}


def execute_approved_action(approval: dict) -> dict:
    """
    Called after human approves. Determines action from metadata and executes.
    Returns execution result dict.
    """
    meta = approval.get("metadata", {})
    instance_id = meta.get("host", {}).get("instance_id", "")
    aws_account = meta.get("client", {}).get("aws_account", "")
    alert_name = meta.get("alert", {}).get("name", "").lower()
    solution_id = meta.get("solution_id", "")
    action_type = meta.get("action_type", "")  # from KB entry action field

    if not instance_id:
        return {"success": False, "error": "No instance_id in metadata"}

    log.info("Executing approved action: solution=%s action=%s instance=%s", solution_id, action_type, instance_id)

    # Determine what to restart based on alert name and solution
    if solution_id == "S012" or "postgresql" in alert_name:
        result = restart_service(instance_id, "postgresql", aws_account)
        if result["success"]:
            # Also restart backend which depends on DB
            time.sleep(2)
            restart_service(instance_id, "cmt-backend", aws_account)

    elif solution_id in ("S001", "S001b") or "backend" in alert_name or "health check" in alert_name:
        # Try service restart first
        service = "cmt-backend" if "backend" in alert_name else "nginx"
        result = restart_service(instance_id, service, aws_account)
        if not result["success"] and action_type == "service_restart_then_ec2":
            log.info("Service restart failed, trying EC2 restart")
            result = restart_ec2(instance_id, aws_account)

    elif "frontend" in alert_name:
        result = restart_service(instance_id, "cmt-frontend", aws_account)

    elif solution_id in ("S004", "S005") or "zabbix" in alert_name:
        result = restart_service(instance_id, "zabbix-agent2", aws_account)

    elif solution_id == "S003" or "awsreplication" in alert_name.replace(" ", ""):
        result = restart_service(instance_id, "AwsReplicationVolumeUpdaterService", aws_account)

    elif action_type == "ec2_restart" or solution_id == "S005":
        result = restart_ec2(instance_id, aws_account)

    else:
        result = {"success": False, "error": f"No executor defined for solution={solution_id} alert={alert_name}"}

    return result


def _get_session(aws_account: str | None):
    if not aws_account:
        return boto3.Session()
    try:
        sts = boto3.client("sts", region_name=_REGION)
        current = sts.get_caller_identity()["Account"]
        if current == aws_account:
            return boto3.Session()
        creds = sts.assume_role(
            RoleArn=f"arn:aws:iam::{aws_account}:role/Aeonx-L2-Role",
            RoleSessionName="aeonx-agent-ssm",
        )["Credentials"]
        return boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
        )
    except Exception:
        return boto3.Session()
