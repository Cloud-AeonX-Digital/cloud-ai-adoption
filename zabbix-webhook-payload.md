# Zabbix Webhook Payload — Reference

> This documents the exact payload Lambda 1 will receive from Zabbix.
> Captured from live Zabbix API on 2026-06-01.
> Used to write the Lambda 1 normalizer.

---

## How Zabbix Sends the Webhook

The "Gen-AI" action (actionid: 14) uses `default_msg: 1` — Zabbix's built-in default message.
We will change this to a **custom webhook** operation that POSTs structured JSON to Lambda 1.

The Zabbix webhook media type sends a POST with JSON body built from Zabbix macros.

---

## Webhook Media Type Config (to create in Zabbix)

Create a new **Webhook** media type in Zabbix with this script and parameters:

**Parameters to pass (Zabbix macros → JSON keys):**

| Parameter Name | Zabbix Macro | Example Value |
|---------------|-------------|---------------|
| `trigger_id` | `{TRIGGER.ID}` | `41654` |
| `trigger_name` | `{TRIGGER.NAME}` | `Linux: High memory utilization (>90% for 5m)` |
| `trigger_severity` | `{TRIGGER.SEVERITY}` | `Average` |
| `trigger_status` | `{TRIGGER.STATUS}` | `PROBLEM` |
| `host_name` | `{HOST.NAME}` | `BioStadt - SAP PRD APP 1` |
| `host_ip` | `{HOST.IP}` | `10.0.1.50` |
| `host_id` | `{HOST.ID}` | `11819` |
| `event_id` | `{EVENT.ID}` | `7868744` |
| `event_time` | `{EVENT.TIME}` | `15:30:08` |
| `event_date` | `{EVENT.DATE}` | `2026.06.01` |
| `item_value` | `{ITEM.VALUE}` | `94.2 %` |
| `inventory_tag` | `{INVENTORY.TAG}` | `aws-account-id` |

---

## Sample Payload Lambda 1 Will Receive

```json
{
  "trigger_id": "41654",
  "trigger_name": "Linux: High memory utilization (>90% for 5m)",
  "trigger_severity": "Average",
  "trigger_status": "PROBLEM",
  "host_name": "BioStadt - SAP PRD APP 1",
  "host_ip": "10.0.1.50",
  "host_id": "11819",
  "event_id": "7868744",
  "event_time": "15:30:08",
  "event_date": "2026.06.01",
  "item_value": "94.2 %",
  "inventory_tag": ""
}
```

---

## Normalized Schema Lambda 1 Produces

Lambda 1 maps the above to this standard schema before POSTing to EC2 agent:

```json
{
  "incident_id": "uuid-v4-generated-by-lambda",
  "source": "zabbix",
  "timestamp": "2026-06-01T10:00:08Z",
  "client": {
    "name": "BioStadt - SAP PRD APP 1",
    "aws_account": "",
    "host_group_id": ""
  },
  "host": {
    "name": "BioStadt - SAP PRD APP 1",
    "ip": "10.0.1.50",
    "zabbix_host_id": "11819",
    "cloud": "aws",
    "instance_id": ""
  },
  "alert": {
    "name": "Linux: High memory utilization (>90% for 5m)",
    "severity": "average",
    "status": "problem",
    "trigger_id": "41654",
    "event_id": "7868744",
    "item_value": "94.2 %"
  },
  "raw": {}
}
```

---

## Notes

- `aws_account` and `instance_id` will be populated in Phase 3 by querying Zabbix host inventory or AWS tags
- `cloud` defaults to `aws` — GCP hosts will be identified by host group naming convention
- `incident_id` is generated fresh by Lambda 1 (UUID v4) for deduplication tracking
- `raw` field stores the original Zabbix payload for audit purposes
