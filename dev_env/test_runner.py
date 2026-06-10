"""
Test runner for dev environment.
Sends real Zabbix-style alert payloads to the local dev agent.
Run: python dev-env/test_runner.py

Prerequisites:
  - Dev agent running: uvicorn dev_env.dev_app:app --port 8000
"""
import json
import os
import uuid
import urllib.request
import urllib.error
from datetime import datetime, timezone

AGENT_URL = os.environ.get("AGENT_URL", "http://172.25.29.253:8000/alert")

# Real alert patterns from live Zabbix (fetched 2026-06-04)
TEST_CASES = [
    {
        "name": "Website Down — high confidence auto-remediate",
        "payload": {
            "trigger_id": "12001",
            "trigger_name": "This Website is Down",
            "trigger_severity": "High",
            "trigger_status": "PROBLEM",
            "host_name": "Biostadt - Website SAP PRD",
            "host_ip": "10.0.1.50",
            "host_id": "11819",
            "event_id": "7868001",
            "event_time": "10:00:00",
            "event_date": "2026.06.04",
            "item_value": "Connection refused",
        }
    },
    {
        "name": "High Memory Linux >90% — auto-remediate",
        "payload": {
            "trigger_id": "41654",
            "trigger_name": "Linux: High memory utilization (>90% for 5m)",
            "trigger_severity": "Average",
            "trigger_status": "PROBLEM",
            "host_name": "BioStadt - SAP PRD APP 1",
            "host_ip": "10.0.2.10",
            "host_id": "11820",
            "event_id": "7868002",
            "event_time": "10:05:00",
            "event_date": "2026.06.04",
            "item_value": "94.2 %",
        }
    },
    {
        "name": "Windows CPU queue high — create ticket",
        "payload": {
            "trigger_id": "49299",
            "trigger_name": "Windows: CPU queue length is too high",
            "trigger_severity": "Warning",
            "trigger_status": "PROBLEM",
            "host_name": "Kairish - PROD SAP Router DMZ (Jump Server)",
            "host_ip": "10.0.3.20",
            "host_id": "15001",
            "event_id": "7868003",
            "event_time": "10:10:00",
            "event_date": "2026.06.04",
            "item_value": "12 items/sec",
        }
    },
    {
        "name": "AWS Replication Service not running — auto-remediate",
        "payload": {
            "trigger_id": "38900",
            "trigger_name": 'Windows: "AwsReplicationVolumeUpdaterService" is not running',
            "trigger_severity": "Average",
            "trigger_status": "PROBLEM",
            "host_name": "Ashapura - SAP PROD APP",
            "host_ip": "10.0.4.5",
            "host_id": "12345",
            "event_id": "7868004",
            "event_time": "10:15:00",
            "event_date": "2026.06.04",
            "item_value": "stopped",
        }
    },
    {
        "name": "EC2 terminated — escalate",
        "payload": {
            "trigger_id": "101612",
            "trigger_name": "AWS EC2: ECS Instance - Microservice-Nexus-UAT is terminated",
            "trigger_severity": "Disaster",
            "trigger_status": "PROBLEM",
            "host_name": "ECS Instance - Microservice-Nexus-UAT",
            "host_ip": "10.0.5.100",
            "host_id": "20001",
            "event_id": "7868005",
            "event_time": "10:20:00",
            "event_date": "2026.06.04",
            "item_value": "terminated",
        }
    },
    {
        "name": "Zabbix agent not available — agent-unavailable",
        "payload": {
            "trigger_id": "55001",
            "trigger_name": "Linux: Zabbix agent is not available (or nodata for 30m)",
            "trigger_severity": "Average",
            "trigger_status": "PROBLEM",
            "host_name": "Rahman - Web App Server",
            "host_ip": "10.0.6.15",
            "host_id": "13001",
            "event_id": "7868006",
            "event_time": "10:25:00",
            "event_date": "2026.06.04",
            "item_value": "",
        }
    },
    {
        "name": "DEDUP TEST — same as test 1 (should be suppressed)",
        "payload": {
            "trigger_id": "12001",  # same trigger_id as test 1
            "trigger_name": "This Website is Down",
            "trigger_severity": "High",
            "trigger_status": "PROBLEM",
            "host_name": "Biostadt - Website SAP PRD",  # same host
            "host_ip": "10.0.1.50",
            "host_id": "11819",
            "event_id": "7868099",  # different event
            "event_time": "10:30:00",
            "event_date": "2026.06.04",
            "item_value": "Connection refused",
        }
    },
]


def normalize(raw: dict) -> dict:
    """Replicate Lambda 1 normalization locally."""
    sev_map = {
        "not classified": "not_classified", "information": "info",
        "warning": "warning", "average": "average",
        "high": "high", "disaster": "disaster",
    }
    sev = sev_map.get(raw.get("trigger_severity", "").lower(), "average")
    return {
        "incident_id": str(uuid.uuid4()),
        "source": "zabbix",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "client": {"name": raw.get("host_name", ""), "aws_account": "", "host_group_id": ""},
        "host": {
            "name": raw.get("host_name", ""),
            "ip": raw.get("host_ip", ""),
            "zabbix_host_id": raw.get("host_id", ""),
            "cloud": "aws",
            "instance_id": "",
        },
        "alert": {
            "name": raw.get("trigger_name", ""),
            "severity": sev,
            "status": "problem" if raw.get("trigger_status", "").upper() == "PROBLEM" else "resolved",
            "trigger_id": raw.get("trigger_id", ""),
            "event_id": raw.get("event_id", ""),
            "item_value": raw.get("item_value", ""),
        },
        "raw": raw,
    }


def send(incident: dict) -> dict:
    body = json.dumps(incident).encode()
    req = urllib.request.Request(
        AGENT_URL, data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()}
    except Exception as e:
        return {"error": str(e)}


def run():
    print(f"\n{'='*60}")
    print("AeonX AI Ops Agent — Dev Test Runner")
    print(f"Target: {AGENT_URL}")
    print(f"{'='*60}\n")

    # Health check first
    try:
        with urllib.request.urlopen(f"{AGENT_URL.replace('/alert','')}/health", timeout=5) as r:
            health = json.loads(r.read())
            print(f"✅ Agent healthy — model: {health.get('model', '?')}\n")
    except Exception as e:
        print(f"❌ Agent not reachable: {e}")
        print("Start the agent first: uvicorn dev_env.dev_app:app --port 8000\n")
        return

    results = []
    for i, tc in enumerate(TEST_CASES, 1):
        print(f"[{i}/{len(TEST_CASES)}] {tc['name']}")
        incident = normalize(tc["payload"])
        response = send(incident)

        action = response.get("action_taken", response.get("error", "?"))
        ticket = response.get("ticket_id")
        inc_id = response.get("incident_id", "?")[:8]

        status = "✅" if "error" not in response else "❌"
        print(f"  {status} action={action} | ticket={ticket or 'none'} | id={inc_id}...")
        results.append({"test": tc["name"], "action": action, "ticket": ticket})
        print()

    print(f"{'='*60}")
    print(f"RESULTS: {sum(1 for r in results if r['action'] not in ['?',None])}/{len(results)} processed")
    print(f"\nOutputs written to:")
    print(f"  ./output/emails.log     — email summaries")
    print(f"  ./output/incidents/     — S3 incident JSON records")
    print(f"  ./output/agent.log      — full agent logs")
    print(f"  ManageEngine            — real tickets created for escalate/create-ticket actions")


if __name__ == "__main__":
    run()


# ── Aivex Chat Test Suite ────────────────────────────────────────────────────

CHAT_URL = os.environ.get("CHAT_URL", "http://localhost:3001/chat")
CHAT_CONTEXT = {
    "host": "Cloud Monitoring Tool",
    "instance_id": "i-00902943a502495a5",
    "account_id": "719395381450",
    "client_name": "Aeonx Sandbox",
}

CHAT_TESTS = [
    # (test_id, question, expect_tools, expect_approval)
    ("C1", "Is cmt-backend running on Cloud Monitoring Tool?",         ["get_service_status"],   False),
    ("C2", "What recent incidents happened on Cloud Monitoring Tool?", ["get_recent_alerts"],    False),
    ("C3", "Show me disk usage on this server",                        ["get_server_info"],      False),
    ("C4", "How much memory is available?",                            ["get_server_info"],      False),
    ("C5", "What is the CPU utilization in the last 30 minutes?",      ["query_cloudwatch_metric"], False),
    ("C6", "Please restart cmt-backend on this server",               ["request_human_approval"], True),
    ("C7", "Increase /var by 20GB",                                   ["get_server_info", "describe_aws_resource", "request_human_approval"], True),
    ("C8", "What AWS volumes are attached to this instance?",         ["describe_aws_resource"], False),
]


def run_chat_tests():
    print("\n" + "="*60)
    print("AIVEX CHAT TEST SUITE")
    print("="*60)
    print(f"Target: {CHAT_URL}\n")

    results = []
    for test_id, question, expect_tools, expect_approval in CHAT_TESTS:
        print(f"[{test_id}] {question[:60]}")
        try:
            body = json.dumps({"question": question, "context": CHAT_CONTEXT}).encode()
            req = urllib.request.Request(CHAT_URL, data=body,
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=60) as r:
                resp = json.loads(r.read())

            got_tools = resp.get("tools_used", [])
            got_approval = bool(resp.get("approval_id"))
            answer = resp.get("answer", "")[:80]

            tool_ok = any(t in got_tools for t in expect_tools)
            approval_ok = (got_approval == expect_approval)
            ok = tool_ok and approval_ok

            print(f"  {'✅' if ok else '❌'} tools={got_tools} approval={got_approval}")
            print(f"     answer: {answer}")
            if not tool_ok:
                print(f"     ⚠️  expected one of {expect_tools}")
            results.append({"id": test_id, "ok": ok})
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            results.append({"id": test_id, "ok": False})
        print()

    passed = sum(1 for r in results if r["ok"])
    print(f"CHAT RESULTS: {passed}/{len(results)} passed")
    return results


if __name__ == "__main__" and "--chat" in __import__("sys").argv:
    run_chat_tests()
