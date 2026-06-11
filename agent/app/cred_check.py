"""
AWS credential health check and expiry detection.
Used by the agent to detect expired sessions and return actionable errors.
"""
import boto3
import os
import logging

log = logging.getLogger(__name__)

_EXPIRED_PHRASES = [
    "session has expired",
    "credentials have changed",
    "please reauthenticate",
    "token has expired",
    "tokenrefresherror",
    "expiredtokenexception",
    "authorizationerror",
]


def is_expired_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(p in msg for p in _EXPIRED_PHRASES)


def check_credentials() -> dict:
    """Returns {valid: bool, account: str, error: str}"""
    try:
        sts = boto3.client("sts", region_name=os.environ.get("AWS_REGION", "ap-south-1"))
        identity = sts.get_caller_identity()
        return {"valid": True, "account": identity["Account"], "error": ""}
    except Exception as e:
        if is_expired_error(e):
            return {"valid": False, "account": "", "error": "expired",
                    "message": "AWS session expired. Run `aws login` in your terminal to refresh."}
        return {"valid": False, "account": "", "error": str(e),
                "message": f"AWS credentials error: {e}"}
