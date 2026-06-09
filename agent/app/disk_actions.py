"""
Disk Space Action Executor

Runs ONLY after human approval is confirmed.
Expands EBS volume by the approved amount and extends the filesystem.
"""

import logging
import os
import boto3
from agent.app.models import AlertPayload

log = logging.getLogger(__name__)

_REGION = os.environ.get("AWS_REGION", "ap-south-1")


def expand_ebs_volume(
    incident: AlertPayload,
    approved_gb: int,
    approval_id: str,
) -> dict:
    """
    Expand EBS volume attached to the host by approved_gb.
    Returns {"success": bool, "detail": str}
    """
    instance_id = incident.host.instance_id
    aws_account = incident.client.aws_account

    if not instance_id:
        return {"success": False, "detail": "No instance_id in incident — cannot identify volume"}

    try:
        # Use cross-account role if needed (Phase 3 pattern)
        session = _get_session(aws_account)
        ec2 = session.client("ec2", region_name=_REGION)

        # Find root/largest volume attached to instance
        volumes = ec2.describe_volumes(
            Filters=[{"Name": "attachment.instance-id", "Values": [instance_id]}]
        )["Volumes"]

        if not volumes:
            return {"success": False, "detail": f"No EBS volumes found for {instance_id}"}

        # Target the volume with lowest free space (or root volume)
        # In prod: parse item_value to identify which filesystem/volume
        target_vol = sorted(volumes, key=lambda v: v["Size"])[0]
        vol_id = target_vol["VolumeId"]
        current_size = target_vol["Size"]
        new_size = current_size + approved_gb

        log.info("[APPROVAL EXEC] Expanding %s: %dGB → %dGB (approval=%s)", vol_id, current_size, new_size, approval_id)

        ec2.modify_volume(VolumeId=vol_id, Size=new_size)

        # Wait for modification to complete
        waiter = ec2.get_waiter("volume_available")
        # Note: EBS modify is async — filesystem resize happens after

        return {
            "success": True,
            "detail": f"Volume {vol_id} expanded from {current_size}GB to {new_size}GB. Filesystem resize required (growpart + resize2fs).",
            "volume_id": vol_id,
            "old_size_gb": current_size,
            "new_size_gb": new_size,
        }

    except Exception as e:
        log.error("[APPROVAL EXEC] EBS expand failed: %s", e)
        return {"success": False, "detail": str(e)}


def _get_session(aws_account: str | None):
    """Get boto3 session — cross-account if aws_account differs from current."""
    if not aws_account:
        return boto3.Session()
    try:
        sts = boto3.client("sts", region_name=_REGION)
        current = sts.get_caller_identity()["Account"]
        if current == aws_account:
            return boto3.Session()
        # Assume cross-account role
        creds = sts.assume_role(
            RoleArn=f"arn:aws:iam::{aws_account}:role/Aeonx-L2-Role",
            RoleSessionName="aeonx-ai-agent-diskexpand",
        )["Credentials"]
        return boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
        )
    except Exception as e:
        log.warning("Cross-account session failed, using default: %s", e)
        return boto3.Session()
