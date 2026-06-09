"""
Dev classifier — knowledge-base-first classification with LLM fallback.

Flow:
1. Match alert name against known-solutions.json
2. If match found: use KB entry (actionable/non-actionable, severity, solution)
3. If no match: call Bedrock gpt-oss-120b for best-effort classification (non-actionable by default)
"""
import json
import os
import re
import logging
import boto3
from pathlib import Path

from agent.app.models import AlertPayload, AIDecision

log = logging.getLogger(__name__)

_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "openai.gpt-oss-120b-1:0")
_REGION = os.environ.get("AWS_REGION", "ap-south-1")
_KB_PATH = os.environ.get("SOLUTIONS_KB_PATH",
    str(Path(__file__).parent.parent / "agent" / "known-solutions.json"))

_kb: list | None = None
_client = None


def _load_kb() -> list:
    global _kb
    if _kb is None:
        with open(_KB_PATH) as f:
            _kb = json.load(f)["solutions"]
    return _kb


def _get_client():
    global _client
    if _client:
        return _client
    profile = os.environ.get("AWS_PROFILE")
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    _client = session.client("bedrock-runtime", region_name=_REGION)
    return _client


def _match_kb(alert_name: str) -> dict | None:
    """Return the first KB entry whose pattern matches the alert name."""
    name_lower = alert_name.lower()
    for entry in _load_kb():
        pattern = entry["pattern"].lower()
        if entry.get("match_type") == "contains" and pattern in name_lower:
            return entry
    return None


def _llm_classify(incident: AlertPayload) -> AIDecision:
    """LLM fallback for unknown alerts — always non-actionable."""
    prompt = f"""You are an SRE analyzing an unknown cloud alert that has NO defined solution.

Alert: {incident.alert.name}
Severity: {incident.alert.severity}
Host: {incident.host.name}
Value: {incident.alert.item_value}

Classify this alert. Since no automated solution exists, action must be "escalate".

Respond ONLY with valid JSON:
{{
  "actionable": false,
  "severity": "<critical|high|medium|low>",
  "category": "<best guess category>",
  "summary": "<one sentence: what happened and likely cause>",
  "confidence": <0.0-1.0>,
  "suggested_action": "<what a human should investigate>"
}}"""

    try:
        response = _get_client().invoke_model(
            modelId=_MODEL_ID,
            body=json.dumps({"messages": [{"role": "user", "content": prompt}],
                             "max_tokens": 300, "temperature": 0.1}),
            contentType="application/json", accept="application/json",
        )
        text = json.loads(response["body"].read())["choices"][0]["message"]["content"]
        if "<reasoning>" in text:
            text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL)
        if text.strip().startswith("```"):
            text = text.strip().split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text.strip())
        return AIDecision(
            actionable=False,
            action="escalate",
            severity=data.get("severity", "medium"),
            category=data.get("category", "unknown"),
            summary=data.get("summary", "Unknown alert — manual review required."),
            confidence=data.get("confidence", 0.5),
            suggested_action=data.get("suggested_action", "Investigate manually."),
            solution_id=None,
            solution_steps=[],
        )
    except Exception as e:
        log.error("[DEV] LLM fallback failed: %s", e)
        return AIDecision(
            actionable=False, action="escalate", severity="high",
            category="unknown",
            summary="Classification failed — manual review required.",
            confidence=0.0, suggested_action="Review alert manually.",
            solution_id=None, solution_steps=[],
        )


def classify(incident: AlertPayload) -> AIDecision:
    alert_name = incident.alert.name

    # Step 1: Knowledge base lookup
    match = _match_kb(alert_name)

    if match:
        actionable = match["actionable"]
        action = "auto-remediate" if actionable else "create-ticket"
        # escalate only for critical non-actionable (ec2-terminated, unknown)
        if not actionable and match.get("category") in ("ec2-terminated", "unknown"):
            action = "escalate"

        log.info("[DEV] KB match: %s → actionable=%s severity=%s [%s]",
                 match["id"], actionable, match["severity"], match["category"])

        return AIDecision(
            actionable=actionable,
            action=action,
            severity=match["severity"],
            category=match["category"],
            summary=f"Known pattern matched ({match['id']}): {alert_name}",
            confidence=0.99,
            suggested_action=match["steps"][0] if match["steps"] else "",
            solution_id=match["id"],
            solution_steps=match["steps"],
        )

    # Step 2: Unknown alert — LLM fallback (always non-actionable)
    log.info("[DEV] No KB match for '%s' — using LLM fallback", alert_name)
    return _llm_classify(incident)
