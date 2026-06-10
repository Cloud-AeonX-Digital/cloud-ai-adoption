"""
Agent loop — Bedrock Converse API with tool-calling.

Flow:
  1. Prime the LLM with alert context + available tools
  2. LLM calls tools iteratively to gather evidence
  3. LLM calls request_human_approval with a decision
  4. Loop exits → returns AgentDecision (mirrors AIDecision schema)

Max iterations: 6 (tool calls before forcing a decision)
"""
import json
import os
import logging
import boto3
from dataclasses import dataclass, field

from agent.tools.registry import TOOL_SPECS, execute_tool
from agent.app.models import AlertPayload, AIDecision

log = logging.getLogger(__name__)

_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "openai.gpt-oss-120b-1:0")
_REGION = os.environ.get("AWS_REGION", "ap-south-1")
_MAX_ITER = 6

_bedrock = None


def _client():
    global _bedrock
    if not _bedrock:
        _bedrock = boto3.client("bedrock-runtime", region_name=_REGION)
    return _bedrock


_SYSTEM = """You are an expert SRE AI agent for AeonX Digital Technology.
You monitor cloud infrastructure and respond to alerts across many client accounts.

Your job when receiving an alert:
1. ALWAYS call search_runbook first — check if a known solution exists
2. Optionally call get_service_status to confirm the service is actually down
3. Optionally call get_recent_alerts to detect recurring patterns
4. Once you have enough context, call request_human_approval with your recommendation

Rules:
- NEVER execute actions directly — always use request_human_approval
- If search_runbook returns a known solution, use it (high confidence)
- If no known solution, use your SRE expertise to diagnose
- Be concise in your reasoning field — one sentence max
- Always set confidence: 0.95+ for known KB matches, 0.6-0.8 for LLM inference"""


def _system_prompt(incident: AlertPayload) -> str:
    return (f"{_SYSTEM}\n\n"
            f"ALERT CONTEXT:\n"
            f"  Alert: {incident.alert.name}\n"
            f"  Severity: {incident.alert.severity}\n"
            f"  Status: {incident.alert.status}\n"
            f"  Host: {incident.host.name} ({incident.host.ip})\n"
            f"  Instance: {incident.host.instance_id or 'unknown'}\n"
            f"  Value: {incident.alert.item_value}\n"
            f"  Client: {incident.client.name} (account: {incident.client.aws_account or 'unknown'})\n"
            f"\nStart by calling search_runbook.")


def run(incident: AlertPayload) -> AIDecision:
    """
    Run the agent loop for a single alert.
    Returns an AIDecision compatible with the existing approval pipeline.
    """
    messages = [{"role": "user", "content": [{"text": _system_prompt(incident)}]}]
    approval_args = None
    iterations = 0

    while iterations < _MAX_ITER:
        iterations += 1
        log.info("[AGENT] iteration %d", iterations)

        try:
            resp = _client().converse(
                modelId=_MODEL_ID,
                system=[{"text": _SYSTEM}],
                messages=messages,
                toolConfig={"tools": TOOL_SPECS},
                inferenceConfig={"maxTokens": 1024, "temperature": 0.1},
            )
        except Exception as e:
            log.error("[AGENT] Bedrock error: %s", e)
            return _fallback_decision(incident, str(e))

        stop_reason = resp["stopReason"]
        response_msg = resp["output"]["message"]
        messages.append(response_msg)

        if stop_reason == "end_turn":
            log.warning("[AGENT] LLM ended without approval call — escalating")
            break

        if stop_reason != "tool_use":
            log.warning("[AGENT] Unexpected stop reason: %s", stop_reason)
            break

        # Process all tool calls in this turn
        tool_results = []
        for block in response_msg["content"]:
            # Converse API returns {"toolUse": {...}} not {"type": "toolUse", ...}
            tool_use = block.get("toolUse")
            if not tool_use:
                continue

            tool_name = tool_use["name"]
            tool_args = tool_use["input"]
            tool_use_id = tool_use["toolUseId"]

            result = execute_tool(tool_name, tool_args)

            if tool_name == "request_human_approval":
                approval_args = {**tool_args, "_tool_use_id": tool_use_id}
                tool_results.append({
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"json": {"status": "approval_queued"}}],
                    }
                })
            else:
                tool_results.append({
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"json": result}],
                    }
                })

        messages.append({"role": "user", "content": tool_results})

        if approval_args:
            break

    if not approval_args:
        log.warning("[AGENT] No approval decision after %d iterations — escalating", iterations)
        return _fallback_decision(incident)

    return _approval_args_to_decision(approval_args, incident)


def _approval_args_to_decision(args: dict, incident: AlertPayload) -> AIDecision:
    action_type = args.get("action_type", "escalate")
    severity = args.get("severity", incident.alert.severity)
    confidence = float(args.get("confidence", 0.7))
    reason = args.get("reason", "Agent recommendation")
    commands = args.get("commands", [])
    target = args.get("target_service", "")

    # Map action_type to our approval pipeline actions
    if action_type in ("service_restart", "ec2_restart", "disk_expand"):
        action = "human-approval-required"
        actionable = True
    elif action_type == "notify_client":
        action = "create-ticket"
        actionable = False
    else:
        action = "escalate"
        actionable = False

    # Derive category from action_type
    category_map = {
        "service_restart": "service-down",
        "ec2_restart": "website-down",
        "disk_expand": "disk-space",
        "notify_client": "client-notify",
        "create_ticket": "unknown",
        "escalate": "unknown",
    }
    category = category_map.get(action_type, "unknown")

    # Build solution_steps from commands (for UI preview)
    steps = commands if commands else ([f"Restart service: {target}"] if target else [reason])

    log.info("[AGENT] Decision: action=%s severity=%s confidence=%.0f%% target=%s",
             action, severity, confidence * 100, target)

    return AIDecision(
        actionable=actionable,
        action=action,
        severity=severity,
        category=category,
        summary=reason,
        confidence=confidence,
        suggested_action=steps[0] if steps else reason,
        solution_id=None,   # agent-derived, not KB
        solution_steps=steps,
        # Store agent-specific fields for executor
        agent_action_type=action_type,
        agent_target_service=target,
    )


def _fallback_decision(incident: AlertPayload, error: str = "") -> AIDecision:
    msg = f"Agent loop failed{': ' + error if error else ''} — manual review required."
    return AIDecision(
        actionable=False, action="escalate",
        severity=incident.alert.severity, category="unknown",
        summary=msg, confidence=0.0,
        suggested_action="Review alert manually.",
        solution_id=None, solution_steps=[],
    )
