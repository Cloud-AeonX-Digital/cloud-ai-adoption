#!/bin/bash
# Deploy Lambda 1 — alert ingestor
# Usage: ./deploy.sh
# Prerequisites: AWS CLI configured, aeonx-ai-agent-role created, EC2 agent running

set -e

FUNCTION_NAME="aeonx-ai-agent-alert-ingestor"
REGION="ap-south-1"
ROLE_ARN="arn:aws:iam::761685920937:role/aeonx-ai-agent-role"
AGENT_URL="${AGENT_URL:?Set AGENT_URL env var to EC2 agent private URL, e.g. http://10.0.1.x:8000/alert}"
SUBNET_ID="${SUBNET_ID:?Set SUBNET_ID env var}"
SG_ID="${SG_ID:?Set SG_ID env var}"

cd "$(dirname "$0")"

# Package
zip -q function.zip handler.py

# Create or update
if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" &>/dev/null; then
  echo "Updating $FUNCTION_NAME..."
  aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file fileb://function.zip \
    --region "$REGION"

  aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --environment "Variables={AGENT_URL=$AGENT_URL}" \
    --region "$REGION"
else
  echo "Creating $FUNCTION_NAME..."
  aws lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --runtime python3.12 \
    --role "$ROLE_ARN" \
    --handler handler.lambda_handler \
    --zip-file fileb://function.zip \
    --timeout 15 \
    --memory-size 128 \
    --environment "Variables={AGENT_URL=$AGENT_URL}" \
    --vpc-config "SubnetIds=$SUBNET_ID,SecurityGroupIds=$SG_ID" \
    --region "$REGION" \
    --tags "Project=aeonx-ai-agent"
fi

# Add function URL (so Zabbix can POST to it)
aws lambda add-permission \
  --function-name "$FUNCTION_NAME" \
  --statement-id allow-zabbix-invoke \
  --action lambda:InvokeFunctionUrl \
  --principal "*" \
  --function-url-auth-type NONE \
  --region "$REGION" 2>/dev/null || true

FUNCTION_URL=$(aws lambda create-function-url-config \
  --function-name "$FUNCTION_NAME" \
  --auth-type NONE \
  --region "$REGION" \
  --query 'FunctionUrl' --output text 2>/dev/null || \
  aws lambda get-function-url-config \
  --function-name "$FUNCTION_NAME" \
  --region "$REGION" \
  --query 'FunctionUrl' --output text)

rm -f function.zip

echo ""
echo "✅ Deployed: $FUNCTION_NAME"
echo "🔗 Webhook URL (set this in Zabbix Gen-AI action):"
echo "   $FUNCTION_URL"
