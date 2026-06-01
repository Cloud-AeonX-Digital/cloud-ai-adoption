import json
import os
import boto3
import logging
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleRequest
import urllib.request

from .models import AlertPayload, AIDecision

log = logging.getLogger(__name__)

# SSM parameter path for GCP service account key
_SSM_GCP_KEY = "/aeonx/ai-agent/gcp-service-account-key"
_GCP_PROJECT = os.environ.get("GCP_PROJECT_ID", "")
_GCP_LOCATION = os.environ.get("GCP_LOCATION", "us-central1")
_GEMINI_MODEL = "gemini-1.5-flash"
_CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.75"))

_credentials = None  # cached


def _get_credentials():
    global _credentials
    if _credentials and _credentials.valid:
        return _credentials

    if _credentials and _credentials.expired and _credentials.refresh_token:
        _credentials.refresh(GoogleRequest())
        return _credentials

    ssm = boto3.client("ssm", region_name="ap-south-1")
    param = ssm.get_parameter(Name=_SSM_GCP_KEY, WithDecryption=True)
    key_data = json.loads(param["Parameter"]["Value"])

    _credentials = service_account.Credentials.from_service_account_info(
        key_data,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    _credentials.refresh(GoogleRequest())
    return _credentials


def _build_prompt(incident: AlertPayload) -> str:
    return f"""You are an expert SRE analyzing a cloud infrastructure alert.

Alert details:
- Alert name: {incident.alert.name}
- Severity: {incident.alert.severity}
- Status: {incident.alert.status}
- Host: {incident.host.name} (IP: {incident.host.ip})
- Client: {incident.client.name}
- Metric value: {incident.alert.item_value}

Respond ONLY with a valid JSON object in this exact format:
{{
  "action": "<auto-remediate|create-ticket|escalate>",
  "severity": "<low|medium|high|critical>",
  "category": "<website-down|high-memory|service-down|agent-unavailable|unknown>",
  "summary": "<one sentence describing what happened and likely cause>",
  "confidence": <0.0 to 1.0>,
  "suggested_action": "<what should be done>"
}}

Rules:
- Use "auto-remediate" only for website-down, high-memory, service-down, agent-unavailable with confidence >= {_CONFIDENCE_THRESHOLD}
- Use "escalate" for unknown categories or confidence < {_CONFIDENCE_THRESHOLD}
- Use "create-ticket" when human review is needed but not urgent"""


def classify(incident: AlertPayload) -> AIDecision:
    try:
        creds = _get_credentials()
        prompt = _build_prompt(incident)

        url = (
            f"https://{_GCP_LOCATION}-aiplatform.googleapis.com/v1/projects/{_GCP_PROJECT}"
            f"/locations/{_GCP_LOCATION}/publishers/google/models/{_GEMINI_MODEL}:generateContent"
        )

        body = json.dumps({
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 512},
        }).encode()

        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {creds.token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())

        text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        decision_data = json.loads(text)

        # Enforce confidence threshold
        if decision_data.get("confidence", 0) < _CONFIDENCE_THRESHOLD:
            decision_data["action"] = "escalate"

        return AIDecision(**decision_data)

    except Exception as e:
        log.error("Gemini classification failed: %s", e)
        # Safe fallback — always escalate on error
        return AIDecision(
            action="escalate",
            severity="high",
            category="unknown",
            summary=f"AI classification failed: {e}. Manual review required.",
            confidence=0.0,
            suggested_action="Review alert manually.",
        )
