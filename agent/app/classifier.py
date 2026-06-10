"""
Production classifier — KB-first + Bedrock gpt-oss-120b fallback.
Identical logic to dev_env/classifier_dev.py.
"""
import json
import os
import re
import logging
import boto3

from .models import AlertPayload, AIDecision

log = logging.getLogger(__name__)

_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "openai.gpt-oss-120b-1:0")
_REGION = os.environ.get("AWS_REGION", "ap-south-1")
_CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.75"))

_client = None


def _get_client():
    global _client
    if _client:
        return _client
    _client = boto3.client("bedrock-runtime", region_name=_REGION)
    return _client


def _kb_path() -> str:
    return os.environ.get(
        "SOLUTIONS_KB_PATH",
        os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "known-solutions.json"))
    )


def _load_kb() -> list:
    with open(_kb_path()) as f:
        return json.load(f)["solutions"]


def _match_kb(alert_name: str) -> dict | None:
    name_lower = alert_name.lower()
    for entry in _load_kb():
        pattern = entry["pattern"].lower()
        if entry.get("match_type") == "contains" and pattern in name_lower:
            return entry
    return None


def _build_prompt(incident: AlertPayload) -> str:
    return f"""You are an expert SRE analyzing a cloud infrastructure alert with no defined solution in the knowledge base.

Alert: {incident.alert.name}
Severity: {incident.alert.severity}
Host: {incident.host.name} (IP: {incident.host.ip})
Value: {incident.alert.item_value}

Respond ONLY with valid JSON:
{{
  "action": "escalate",
  "severity": "<critical|high|medium|low>",
  "category": "<best guess category>",
  "summary": "<one sentence: what happened and likely cause>",
  "confidence": <0.0-1.0>,
  "suggested_action": "<what a human should investigate>"
}}"""


def _llm_classify(incident: AlertPayload) -> AIDecision:
    try:
        response = _get_client().invoke_model(
            modelId=_MODEL_ID,
            body=json.dumps({
                "messages": [{"role": "user", "content": _build_prompt(incident)}],
                "max_tokens": 300, "temperature": 0.1,
            }),
            contentType="application/json", accept="application/json",
        )
        text = json.loads(response["body"].read())["choices"][0]["message"]["content"].strip()
        if "<reasoning>" in text:
            text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL).strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"): text = text[4:]
        data = json.loads(text.strip())
        return AIDecision(
            actionable=False, action="escalate",
            severity=data.get("severity", "high"),
            category=data.get("category", "unknown"),
            summary=data.get("summary", "Unknown alert — manual review required."),
            confidence=data.get("confidence", 0.5),
            suggested_action=data.get("suggested_action", "Review manually."),
            solution_id=None, solution_steps=[],
        )
    except Exception as e:
        log.error("LLM classification failed: %s", e)
        return AIDecision(
            actionable=False, action="escalate", severity="high",
            category="unknown", summary="Classification failed — manual review required.",
            confidence=0.0, suggested_action="Review alert manually.",
            solution_id=None, solution_steps=[],
        )


def classify(incident: AlertPayload) -> AIDecision:
    match = _match_kb(incident.alert.name)
    if match:
        actionable = match["actionable"]
        kb_action = match.get("action", "")
        if actionable or kb_action == "human_approval_then_expand":
            action = "human-approval-required"
        elif match.get("category") in ("ec2-terminated", "unknown"):
            action = "escalate"
        else:
            action = "create-ticket"

        log.info("KB match: %s → actionable=%s action=%s", match["id"], actionable, action)
        return AIDecision(
            actionable=actionable, action=action,
            severity=match["severity"], category=match["category"],
            summary=f"Known pattern matched ({match['id']}): {incident.alert.name}",
            confidence=0.99,
            suggested_action=match["steps"][0] if match["steps"] else "",
            solution_id=match["id"], solution_steps=match["steps"],
        )

    log.info("No KB match for '%s' — LLM fallback", incident.alert.name)
    return _llm_classify(incident)
