#!/usr/bin/env bash
# P1–P5: PostgreSQL + 外部证据 + ERA Bridge + 角色账号 + 验收
set -euo pipefail
ROOT=/opt/enterprise-risk-assessment
ENV="$ROOT/web_app/.env"
USERS="$ROOT/web_app/data/users.json"

cd "$ROOT"

echo "[1/6] PostgreSQL + MinIO (.env)"
"$ROOT/.venv/bin/python" /tmp/finish-erm-env.py 2>/dev/null || "$ROOT/.venv/bin/python" "$ROOT/scripts/provision_e2_store.py" || true

upsert_env() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "$ENV" 2>/dev/null; then
    if ! grep -q "^${key}=${val}$" "$ENV" 2>/dev/null; then
      sed -i "s|^${key}=.*|${key}=${val}|" "$ENV"
    fi
  else
    echo "${key}=${val}" >> "$ENV"
  fi
}

upsert_env ERM_EXTERNAL_RISK_PROVIDER demo
upsert_env ERM_EXTERNAL_RISK_URL "http://127.0.0.1:8091/api/external-risk/demo-feed"
upsert_env ERM_AUTH_MODE on
chmod 600 "$ENV"

echo "[2/6] RBAC users (assessor / approver / director)"
cat > "$USERS" <<'JSON'
{
  "users": [
    {"username": "红旗", "password": "123456", "role": "admin"},
    {"username": "评估员", "password": "assessor123", "role": "assessor"},
    {"username": "审批人", "password": "approver123", "role": "approver"},
    {"username": "董事", "password": "director123", "role": "director"}
  ]
}
JSON

echo "[3/6] Restart ERM"
systemctl restart erm-assessment.service
sleep 4

echo "[4/6] Enable ERA Assessment Bridge"
mkdir -p /opt/era-backups/reports
systemctl enable era-assessment-bridge.service
systemctl restart era-assessment-bridge.service
sleep 2

echo "[5/6] Smoke tests"
curl -sf http://127.0.0.1:8091/health | head -c 200; echo
curl -sf http://127.0.0.1:8091/api/engines | head -c 400; echo
curl -sf "http://127.0.0.1:8091/api/external-risk?uscc=91320100MA1N5Y7XB&company_name=DEMO-test" | head -c 300; echo
curl -sf http://127.0.0.1:18088/health | head -c 200; echo

echo "[6/6] Store backend"
"$ROOT/.venv/bin/python" -c "
from erm_store import using_postgres, storage_status
print('postgres', using_postgres())
print(storage_status())
"

echo "DONE complete-erm-production"
