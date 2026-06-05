"""
Dev classifier — uses AWS Bedrock gpt-oss-120b instead of GCP Vertex AI.
Drop-in replacement for agent/app/classifier.py in dev environment.
"""
import json
import os
import logging
import boto3

from agent.app.models import AlertPayload, AIDecision

log = logging.getLogger(__name__)

_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "openai.gpt-oss-120b-v1")
_REGION = os.environ.get("AWS_REGION", "ap-south-1")
_CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.75"))

_client = None


def _get_client():
    global _client
    if _client:
        return _client
    profile = os.environ.get("AWS_PROFILE")
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    _client = session.client("bedrock-runtime", region_name=_REGION)
    return _client


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
- Use "auto-remediate" only for: website-down, high-memory, service-down (stopped/not-running), agent-unavailable — AND confidence >= {_CONFIDENCE_THRESHOLD}
- Use "escalate" for: terminated instances, unknown patterns, disaster severity without clear cause, or confidence < {_CONFIDENCE_THRESHOLD}
- Use "create-ticket" when issue needs human review but is not urgent
- "terminated" in item_value or alert name = escalate always (terminated EC2 cannot be restarted)
- Return ONLY the JSON object, no explanation, no reasoning tags"""


def classify(incident: AlertPayload) -> AIDecision:
    try:
        prompt = _build_prompt(incident)
        client = _get_client()

        body = json.dumps({
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 512,
            "temperature": 0.1,
        })

        response = client.invoke_model(
            modelId=_MODEL_ID,
            body=body,
            contentType="application/json",
            accept="application/json",
        )

        result = json.loads(response["body"].read())

        # Extract text from response (OpenAI-compatible format via Bedrock)
        text = result["choices"][0]["message"]["content"].strip()

        # gpt-oss-120b wraps responses in <reasoning>...</reasoning> — strip it
        if "<reasoning>" in text:
            import re
            text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL).strip()

        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        decision_data = json.loads(text)

        # Enforce confidence threshold
        if decision_data.get("confidence", 0) < _CONFIDENCE_THRESHOLD:
            decision_data["action"] = "escalate"

        log.info("[DEV] Classified: action=%s category=%s confidence=%.2f",
                 decision_data.get("action"), decision_data.get("category"),
                 decision_data.get("confidence", 0))

        return AIDecision(**decision_data)

    except Exception as e:
        log.error("[DEV] Bedrock classification failed: %s", e)
        return AIDecision(
            action="escalate",
            severity="high",
            category="unknown",
            summary=f"AI classification failed: {e}. Manual review required.",
            confidence=0.0,
            suggested_action="Review alert manually.",
        )
