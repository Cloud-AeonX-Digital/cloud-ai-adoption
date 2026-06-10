"""
Phase E — Developer Self-Service Chat.
Same Bedrock Converse + tool registry as agent_loop, different system prompt.
Handles natural language questions from developers/ops team.
"""
import json
import os
import logging
import boto3

from agent.tools.registry import TOOL_SPECS, execute_tool

log = logging.getLogger(__name__)

_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "openai.gpt-oss-120b-1:0")
_REGION   = os.environ.get("AWS_REGION", "ap-south-1")
_MAX_ITER = 8

_bedrock = None

def _client():
    global _bedrock
    if not _bedrock:
        _bedrock = boto3.client("bedrock-runtime", region_name=_REGION)
    return _bedrock


_SYSTEM = """You are an expert SRE assistant for AeonX Digital Technology.
You answer questions from the ops/dev team about infrastructure state, recent incidents, and service health.

Available tools let you:
- search_runbook: look up known solutions for alert patterns
- get_service_status: check if a service is running RIGHT NOW on a host
- get_ec2_info: get instance metadata (state, type, tags)
- query_cloudwatch_metric: fetch recent metrics (CPU, memory, disk I/O)
- get_recent_alerts: search incident history for a host or keyword
- request_human_approval: propose an action that needs human sign-off

RULES:
- Use tools to get REAL data before answering — never guess
- If asked "is X running" → call get_service_status
- If asked "what happened to X recently" → call get_recent_alerts
- If asked "what's the CPU on X" → call query_cloudwatch_metric
- If the user asks you to DO something (restart, change config) → call request_human_approval — never act directly
- Keep answers concise: one paragraph max, plain text, no markdown
- If you don't have enough info to answer, say so clearly"""


def chat(question: str, context: dict = None) -> dict:
    """
    Answer a natural language question using tool-calling.
    context: optional dict with {host, instance_id, account_id} to scope tools.

    Returns: {answer: str, tools_used: [str], approval_id: str|None}
    """
    ctx_hint = ""
    if context:
        parts = []
        if context.get("host"):        parts.append(f"host={context['host']}")
        if context.get("instance_id"): parts.append(f"instance={context['instance_id']}")
        if context.get("account_id"):  parts.append(f"account={context['account_id']}")
        if parts: ctx_hint = f"\n\nContext: {', '.join(parts)}"

    messages = [{"role": "user", "content": [{"text": question + ctx_hint}]}]
    tools_used = []
    approval_id = None
    iterations = 0

    while iterations < _MAX_ITER:
        iterations += 1

        try:
            resp = _client().converse(
                modelId=_MODEL_ID,
                system=[{"text": _SYSTEM}],
                messages=messages,
                toolConfig={"tools": TOOL_SPECS},
                inferenceConfig={"maxTokens": 1024, "temperature": 0.2},
            )
        except Exception as e:
            log.error("[CHAT] Bedrock error: %s", e)
            return {"answer": f"Sorry, I couldn't process that: {e}", "tools_used": tools_used, "approval_id": None}

        stop_reason = resp["stopReason"]
        response_msg = resp["output"]["message"]
        messages.append(response_msg)

        if stop_reason == "end_turn":
            # Extract final text answer
            answer = " ".join(
                b["text"] for b in response_msg["content"] if "text" in b
            ).strip()
            return {"answer": answer or "Done.", "tools_used": tools_used, "approval_id": approval_id}

        if stop_reason != "tool_use":
            break

        tool_results = []
        for block in response_msg["content"]:
            tool_use = block.get("toolUse")
            if not tool_use:
                continue

            name     = tool_use["name"]
            args     = tool_use["input"]
            use_id   = tool_use["toolUseId"]
            tools_used.append(name)

            if name == "request_human_approval":
                # Create approval via approval_manager and return its ID
                from agent.app.approval_manager import request_approval
                approval_id = request_approval(
                    incident_id=f"chat-{use_id[:8]}",
                    approval_type=args.get("action_type", "chat-request"),
                    description=args.get("reason", question),
                    proposed_action=args.get("reason", ""),
                    metadata={
                        "chat_question": question,
                        "action_type": args.get("action_type"),
                        "target_service": args.get("target_service", ""),
                        "commands": args.get("commands", []),
                        "severity": args.get("severity", "medium"),
                        "confidence": args.get("confidence", 0.8),
                        "source": "chat",
                    }
                )
                result = {"status": "approval_created", "approval_id": approval_id,
                          "message": "Action queued for human approval. Check the Approvals tab."}
            else:
                result = execute_tool(name, args)

            tool_results.append({
                "toolResult": {
                    "toolUseId": use_id,
                    "content": [{"json": result}],
                }
            })

        messages.append({"role": "user", "content": tool_results})

    return {"answer": "I wasn't able to fully answer that. Please try rephrasing.", "tools_used": tools_used, "approval_id": approval_id}
