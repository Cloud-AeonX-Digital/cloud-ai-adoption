# ManageEngine ServiceDesk Plus — Integration Reference

> Live integration tested on 2026-06-03.
> Base URL: https://customer.aeonx.support
> API version: v3

---

## Authentication

- Header: `authtoken: <API_KEY>`
- API key stored in SSM: `/aeonx/ai-agent/manageengine-api-key`
- API user: `aws.automation@aeonx.digital` (user id: `4511`)

### Permission levels confirmed:
| Operation | aws.automation | Full Technician |
|-----------|---------------|-----------------|
| List/read tickets | ✅ | ✅ |
| Create ticket | ✅ | ✅ |
| Update ticket fields | ✅ | ✅ |
| Assign ticket | ✅ | ✅ |
| Move to In Progress | ✅ | ✅ |
| Resolve ticket | ❌ needs upgrade | ✅ |
| Close ticket | ❌ needs upgrade | ✅ |
| Add worklog | ❌ needs upgrade | ✅ |

**Action required:** Upgrade `aws.automation@aeonx.digital` to full Technician in ManageEngine Admin → Users → Technicians to enable resolve/close operations.

---

## Ticket Field IDs (confirmed from live API)

| Field | ID / Value |
|-------|-----------|
| Category | `601` = AWS Support |
| Subcategory | `313` = Monitoring & Logging |
| Subcategory (alt) | `309` = AWS-Cloud Service |
| Request Type | `303` = AWS Support Incident |
| Group | `615` = AWS Support Internal |
| Priority High | `1` |
| Priority Medium | `2` |
| Priority Low | `3` |
| Priority Urgent | `4` |
| `udf_pick_307` | `"Other"` (mandatory on create) |
| `udf_pick_302` | `"No"` (mandatory on Assigned→In Progress) |

---

## AeonX Lifecycle (id: 2)

```
[Start]
   │
   ▼
 Open  ──────────────────────────────────────────────────────────────────┐
   │                                                                      │
   │ Assign (mandatory: technician, group, subcategory)                  │ Hold
   ▼                                                                      ▼
Assigned                                                               Onhold
   │                                                                      │
   │ Start work (mandatory: udf_pick_302 = "No")                         │ Resume / Open
   ▼                                                                      │
In Progress ◄──────────────────────────────────────────────────────────-─┘
   │       │
   │       │ Hold → Onhold
   │       │ Customer Action → Customer Action status
   │
   │ Resolve (mandatory: resolution.content + worklog)
   ▼
Resolved
   │
   │ Close
   ▼
Closed ──► [End]
```

### Transition mandatory fields:

| Transition | From → To | Mandatory Fields |
|-----------|-----------|-----------------|
| Assign | Open → Assigned | `technician`, `group`, `subcategory` |
| Start work | Assigned → In Progress | `udf_fields.udf_pick_302` = `"No"` |
| Resolve | In Progress → Resolved | `resolution.content`, `worklog` (separate API call) |
| Close | Resolved → Closed | `status_change_comments` |

---

## API Endpoints Used

### Create ticket
```
POST /api/v3/requests
Content-Type: application/x-www-form-urlencoded
Body: input_data=<JSON>

Minimal payload:
{
  "request": {
    "subject": "[AI Agent] <alert_name> — <host_name>",
    "description": "<html_description>",
    "requester": {"email_id": "aws.automation@aeonx.digital"},
    "priority": {"id": "1|2|3|4"},
    "category": {"id": "601"},
    "subcategory": {"id": "313"},
    "request_type": {"id": "303"},
    "group": {"id": "615"},
    "udf_fields": {"udf_pick_307": "Other"}
  }
}
```

### Update ticket
```
PUT /api/v3/requests/{ticket_id}
```

### Add worklog (required before Resolve)
```
POST /api/v3/requests/{ticket_id}/worklogs
{
  "worklog": {
    "description": "<what was done>",
    "technician": {"id": "<technician_id>"}
  }
}
```

### Duplicate check (Gap #11)
```
GET /api/v3/requests?input_data={"list_info":{"search_fields":{"subject":"[AI Agent] <alert_name>"}}}
→ check if any open ticket matches host name in subject
```

---

## Reference Ticket: #78458 (Cloud/AWS use case)

Used as the template for AI agent tickets.

| Field | Value |
|-------|-------|
| Subject | Server to be restart |
| Category | AWS Support (601) |
| Subcategory | AWS-Cloud Service (309) |
| Request Type | AWS Support Incident (303) |
| Group | Client-specific group |
| Technician | mrinal.jani@aeonx.digital (id: 3906) |
| udf_pick_307 | Other |
| udf_pick_302 | No |
| Resolution | "work done." |
| Final Status | Closed |

---

## Lifecycle Test (ticket #84471)

| Step | Result |
|------|--------|
| Create (Open) | ✅ |
| Open → Assigned | ✅ |
| Assigned → In Progress (udf_pick_302="No") | ✅ |
| In Progress → Resolved | ❌ Needs Technician permission on aws.automation |
| Resolved → Closed | ❌ Blocked by above |

**Blocker:** `aws.automation` needs Technician role upgrade to complete resolve/close.
