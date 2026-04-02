#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/icms_sergipe"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

if [ -f "venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  . venv/bin/activate
fi

python main.py --acao download --headless true >> "$LOG_DIR/cron.log" 2>&1
