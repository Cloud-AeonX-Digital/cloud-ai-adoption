#!/bin/bash
# Dev environment setup — run once from repo root
# Usage: bash dev-env/setup.sh

set -e
cd "$(git rev-parse --show-toplevel)"

echo "=== AeonX AI Agent — Dev Setup ==="

# Create venv
python3 -m venv dev-env/.venv
source dev-env/.venv/bin/activate

# Install deps
pip install -q --upgrade pip
pip install -q -r dev-env/requirements.txt

# Create .env from example if not exists
if [ ! -f dev-env/.env ]; then
  cp dev-env/.env.example dev-env/.env
  echo "Created dev-env/.env — fill in AWS_PROFILE and BEDROCK_MODEL_ID"
fi

# Create output dirs
mkdir -p dev-env/output/incidents

echo ""
echo "✅ Setup complete."
echo ""
echo "⏳ PENDING before running tests:"
echo "  1. Configure AWS credentials: aws configure --profile aeonx-dev"
echo "  2. Enable gpt-oss-120b in Bedrock console (ap-south-1) and set BEDROCK_MODEL_ID in dev-env/.env"
echo ""
echo "To start the dev agent:"
echo "  source dev-env/.venv/bin/activate"
echo "  uvicorn dev_env.dev_app:app --port 8000 --reload"
echo ""
echo "To run tests (in a second terminal):"
echo "  source dev-env/.venv/bin/activate"
echo "  python dev-env/test_runner.py"
