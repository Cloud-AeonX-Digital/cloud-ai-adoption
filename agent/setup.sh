#!/bin/bash
# EC2 Agent Setup Script
# Run once on a fresh Amazon Linux 2023 / t3.small instance
# Prerequisites: instance has aeonx-ai-agent-role attached

set -e

APP_DIR="/opt/aeonx-agent"
REPO="https://github.com/Cloud-AeonX-Digital/cloud-ai-adoption.git"
GCP_PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID env var}"

echo "=== Installing system dependencies ==="
sudo dnf install -y python3.11 python3.11-pip git

echo "=== Cloning repo ==="
sudo mkdir -p "$APP_DIR"
sudo chown ec2-user:ec2-user "$APP_DIR"
git clone "$REPO" "$APP_DIR/repo"

echo "=== Setting up Python venv ==="
python3.11 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/repo/agent/requirements.txt"

echo "=== Linking app code ==="
ln -sf "$APP_DIR/repo/agent/app" "$APP_DIR/agent"

echo "=== Installing systemd service ==="
sudo cp "$APP_DIR/repo/agent/aeonx-agent.service" /etc/systemd/system/aeonx-agent.service
# Inject GCP project ID
sudo sed -i "s/REPLACE_WITH_GCP_PROJECT_ID/$GCP_PROJECT_ID/" /etc/systemd/system/aeonx-agent.service

sudo systemctl daemon-reload
sudo systemctl enable aeonx-agent
sudo systemctl start aeonx-agent

echo ""
echo "=== Verifying ==="
sleep 3
sudo systemctl status aeonx-agent --no-pager
curl -sf http://localhost:8000/health && echo "✅ Agent is healthy"
