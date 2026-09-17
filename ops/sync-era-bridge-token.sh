#!/usr/bin/env bash
# Mirror ERM_ADMIN_TOKEN -> ERA_BRIDGE_TOKEN in web_app/.env (idempotent).
set -euo pipefail
ROOT="${1:-/opt/enterprise-risk-assessment}"
ENV_FILE="$ROOT/web_app/.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "missing $ENV_FILE"
  exit 1
fi
TOK="$(grep -E '^ERM_ADMIN_TOKEN=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
if [ -z "$TOK" ]; then
  echo "ERM_ADMIN_TOKEN not set in $ENV_FILE — set it before enabling bridge auth"
  exit 2
fi
if grep -q '^ERA_BRIDGE_TOKEN=' "$ENV_FILE"; then
  sed -i "s|^ERA_BRIDGE_TOKEN=.*|ERA_BRIDGE_TOKEN=$TOK|" "$ENV_FILE"
else
  echo "ERA_BRIDGE_TOKEN=$TOK" >> "$ENV_FILE"
fi
chmod 600 "$ENV_FILE" 2>/dev/null || true
echo "ERA_BRIDGE_TOKEN synced (value redacted)"
systemctl restart era-assessment-bridge.service 2>/dev/null || true
sleep 1
curl -sS "http://127.0.0.1:18088/health" | head -c 200
echo
