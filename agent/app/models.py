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
    action: str          # "auto-remediate" | "create-ticket" | "escalate"
    severity: str        # "low" | "medium" | "high" | "critical"
    category: str        # "website-down" | "high-memory" | "service-down" | "agent-unavailable" | "unknown"
    summary: str
    confidence: float
    suggested_action: str = ""


class IncidentResponse(BaseModel):
    incident_id: str
    action_taken: str
    ticket_id: Optional[str]
