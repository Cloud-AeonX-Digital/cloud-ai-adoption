from pydantic import BaseModel
from typing import Optional


class ClientInfo(BaseModel):
    name: str = ""
    aws_account: str = ""
    host_group_id: str = ""


class HostInfo(BaseModel):
    name: str = ""
    ip: str = ""
    zabbix_host_id: str = ""
    cloud: str = "aws"
    instance_id: str = ""


class AlertInfo(BaseModel):
    name: str
    severity: str
    status: str  # "problem" | "resolved"
    trigger_id: str = ""
    event_id: str = ""
    item_value: str = ""


class AlertPayload(BaseModel):
    incident_id: str
    source: str = "zabbix"
    timestamp: str
    client: ClientInfo = ClientInfo()
    host: HostInfo = HostInfo()
    alert: AlertInfo


class AIDecision(BaseModel):
    actionable: bool                          # True = known pattern with defined solution
    action: str                               # "human-approval-required" | "create-ticket" | "escalate"
    severity: str                             # "critical" | "high" | "medium" | "low"
    category: str                             # "website-down" | "high-memory" | "service-down" | etc.
    summary: str
    confidence: float
    suggested_action: str = ""
    solution_id: Optional[str] = None        # KB entry ID e.g. "S001"
    solution_steps: list[str] = []           # Step-by-step resolution from KB
    # Agent loop fields (set when agent_loop.py drives the decision)
    agent_action_type: Optional[str] = None  # "service_restart" | "ec2_restart" | "disk_expand" | ...
    agent_target_service: Optional[str] = None  # e.g. "cmt-backend", "i-0abc123"


class IncidentResponse(BaseModel):
    incident_id: str
    action_taken: str
    ticket_id: Optional[str]
    approval_id: Optional[str] = None
