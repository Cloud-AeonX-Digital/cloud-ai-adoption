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


_SYSTEM = """You are Aivex — AeonX's infrastructure AI assistant for the ops/dev team.
You answer questions about infrastructure state, incidents, metrics, and can propose actions.

Available tools:
- search_runbook: look up known solutions for alert patterns
- get_service_status: check if a systemd service is running RIGHT NOW
- get_ec2_info: get instance metadata (state, type, tags, auto-restart eligibility)
- query_cloudwatch_metric: fetch recent metrics (CPU, memory, NetworkIn, etc.)
- get_recent_alerts: search incident history for a host or keyword
- get_disk_usage: get live disk usage and mount point details via SSM df -h
- get_server_info: retrieve ANY live server diagnostic — disk (df -h), memory (free -m), processes, logs, network, uptime
- describe_aws_resource: query AWS for EBS volumes, RDS, ECS services, ALB target health
- get_secrets_rotation_status: find secrets/parameters not rotated recently
- request_human_approval: propose an action that needs human sign-off before executing

RULES:
- Use tools to get REAL live data — never guess or say you can't retrieve something
- "Is X running?" → get_service_status if instance_id known, else get_recent_alerts(host_name=X)
- "What happened / recent incidents / alerts?" → get_recent_alerts — use host name from question as host_name, or use alert_query with keywords
- "Disk / df / storage?" → get_server_info(query="disk usage")
- "CPU / memory?" → query_cloudwatch_metric or get_server_info(query="memory usage")
- "Logs / processes / uptime?" → get_server_info immediately
- "AWS volumes / RDS / ECS?" → describe_aws_resource
- "Cost / billing / spend?" → get_cost_breakdown + get_cost_anomalies
- "Idle resources?" → flag_idle_resources
- "Security / public buckets / open ports?" → get_security_findings
- "Expand disk / restart / any change?" → gather info first, then request_human_approval
- "Secrets / credentials rotation?" → get_secrets_rotation_status

NEVER ask the user for clarification. If instance_id is missing:
  - Use host_name or any keyword from the question in get_recent_alerts
  - Try get_recent_alerts(host_name="", alert_query="<keywords from question>") to search all history
  - If still no data, say "I couldn't find data for that — try including the host name or instance ID"

EXAMPLES:
- "show me df -h" → get_server_info(instance_id=..., query="disk usage")
- "what happened on my app server?" → get_recent_alerts(host_name="app server")
- "increase /var by 20GB" → get_server_info → describe_aws_resource(ebs_volumes) → request_human_approval"""


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

    # Pre-flight: for known server-diagnostic questions, fetch data eagerly and inject as context
    # This bypasses the model's reluctance to call get_server_info
    eager_data = ""
    q_lower = question.lower()
    instance_id = context.get("instance_id", "")
    if instance_id and any(kw in q_lower for kw in ["df", "disk", "mount", "storage", "free", "memory", "ram", "process", "ps aux", "uptime", "load"]):
        if any(kw in q_lower for kw in ["disk", "df", "mount", "storage"]):
            result = execute_tool("get_server_info", {"instance_id": instance_id, "query": "disk usage"})
        elif any(kw in q_lower for kw in ["memory", "ram", "free"]):
            result = execute_tool("get_server_info", {"instance_id": instance_id, "query": "memory usage"})
        elif any(kw in q_lower for kw in ["process", "ps aux", "cpu"]):
            result = execute_tool("get_server_info", {"instance_id": instance_id, "query": "running processes"})
        else:
            result = execute_tool("get_server_info", {"instance_id": instance_id, "query": question})
        if result.get("output") and "error" not in result.get("output", "").lower()[:20]:
            eager_data = f"\n\nLIVE SERVER DATA (just fetched):\n```\n{result['output'][:1500]}\n```\nAnswer the user's question using this data."
        log.info("[CHAT] pre-flight get_server_info fetched for '%s'", question[:50])

    messages = [{"role": "user", "content": [{"text": question + ctx_hint + eager_data}]}]
    tools_used = []
    approval_id = None
    iterations = 0
    if eager_data:
        tools_used.append("get_server_info")

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
                        "host": {"name": context.get("host",""), "ip": context.get("host_ip",""), "instance_id": context.get("instance_id","")},
                        "client": {"name": context.get("client_name",""), "aws_account": context.get("account_id","")},
                        "alert": {"name": args.get("reason", question), "item_value": ""},
                        "chat_question": question,
                        "action_type": args.get("action_type"),
                        "ai_action_type": args.get("action_type"),
                        "agent_target_service": args.get("target_service",""),
                        "solution_steps": args.get("commands",[]),
                        "severity": args.get("severity","medium"),
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
