#!/usr/bin/env bash
# Run system_audit against local ERM (port 8091) with admin token from .env
set -eu
ROOT="${1:-/opt/enterprise-risk-assessment}"
cd "$ROOT/web_app"
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi
export ERM_AUDIT_URL="${ERM_AUDIT_URL:-http://127.0.0.1:8091}"
export ERM_AUDIT_TOKEN="${ERM_AUDIT_TOKEN:-${ERM_ADMIN_TOKEN:-}}"
exec "$ROOT/.venv/bin/python" "$ROOT/system_audit.py"
