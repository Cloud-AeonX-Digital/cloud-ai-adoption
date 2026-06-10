# SSM Parameter Store — Secrets Reference

> All agent secrets stored in AWS SSM Parameter Store (SecureString).
> Account: 761685920937 | Region: ap-south-1
> Path prefix: `/aeonx/ai-agent/`

> **Note:** GCP service account key NOT needed. Production classifier uses AWS Bedrock (gpt-oss-120b-1:0) — IAM auth only.

---

## How to store a secret

```bash
aws ssm put-parameter \
  --name "/aeonx/ai-agent/<parameter-name>" \
  --value "<secret-value>" \
  --type "SecureString" \
  --region "ap-south-1" \
  --overwrite
```

## How to read a secret (CLI)

```bash
aws ssm get-parameter \
  --name "/aeonx/ai-agent/<parameter-name>" \
  --with-decryption \
  --region "ap-south-1" \
  --query "Parameter.Value" \
  --output text
```

---

## Parameters

| Parameter Path | Type | Description | Status |
|---------------|------|-------------|--------|
| `/aeonx/ai-agent/manageengine-api-key` | SecureString | ManageEngine API key for `aws.automation@aeonx.digital` | ⏳ Store manually |
| `/aeonx/ai-agent/gcp-service-account-key` | SecureString | GCP service account JSON (Vertex AI — if used) | ⏳ Pending GCP project |
| `/aeonx/ai-agent/zabbix-api-token` | SecureString | Zabbix read-only API token for `mrinal.jani@aeonx.digital` | ⏳ Store manually |
| `/aeonx/ai-agent/ses-from-address` | String | SES verified sender: `awsalerts@aeonx.digital` | ⏳ Store manually |
| `/aeonx/ai-agent/ec2-agent-url` | String | Internal URL of EC2 agent: `http://<EC2-PRIVATE-IP>:8000` | ⏳ After EC2 launch |

---

## Store commands (run once in account 761685920937)

```bash
# ManageEngine API key
aws ssm put-parameter \
  --name "/aeonx/ai-agent/manageengine-api-key" \
  --value "<MANAGEENGINE-API-KEY>" \
  --type "SecureString" \
  --region "ap-south-1" --overwrite

# Zabbix API token
aws ssm put-parameter \
  --name "/aeonx/ai-agent/zabbix-api-token" \
  --value "<ZABBIX-API-TOKEN>" \
  --type "SecureString" \
  --region "ap-south-1" --overwrite

# SES from address (not a secret but stored for config consistency)
aws ssm put-parameter \
  --name "/aeonx/ai-agent/ses-from-address" \
  --value "awsalerts@aeonx.digital" \
  --type "String" \
  --region "ap-south-1" --overwrite

# EC2 agent URL — fill in after EC2 is launched
aws ssm put-parameter \
  --name "/aeonx/ai-agent/ec2-agent-url" \
  --value "http://<EC2-PRIVATE-IP>:8000" \
  --type "String" \
  --region "ap-south-1" --overwrite

# GCP service account key — fill in after GCP project created
# aws ssm put-parameter \
#   --name "/aeonx/ai-agent/gcp-service-account-key" \
#   --value "$(cat /path/to/service-account-key.json)" \
#   --type "SecureString" \
#   --region "ap-south-1" --overwrite
```

---

## IAM permission required to read secrets

The `aeonx-ai-agent-role` already has this permission:
```json
{
  "Action": ["ssm:GetParameter", "ssm:GetParameters"],
  "Resource": "arn:aws:ssm:ap-south-1:761685920937:parameter/aeonx/ai-agent/*"
}
```

---

## Notes

- Never hardcode secrets in code or environment variables
- The `ec2-agent-url` and `ses-from-address` are also set as environment variables in the systemd service for performance (avoids SSM call on every request)
- Rotate the ManageEngine API key by regenerating in ManageEngine Admin → Technicians → aws.automation → API Key, then updating SSM
