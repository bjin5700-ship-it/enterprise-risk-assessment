#!/usr/bin/env bash
# Expose ERM health/ping for monitoring & CIRI probes without dropping app auth.
set -euo pipefail
CONF=/etc/nginx/sites-enabled/sentinel
MARK="ERM_PUBLIC_HEALTH"

if grep -q "$MARK" "$CONF" 2>/dev/null; then
  echo "already patched ($MARK)"
  exit 0
fi

TMP=$(mktemp)
awk -v mark="$MARK" '
  /location \/erm\/ \{/ && !done {
    print "    # " mark
    print "    location = /erm/ping { auth_basic off; proxy_pass http://127.0.0.1:8091/ping; }"
    print "    location = /erm/health { auth_basic off; proxy_pass http://127.0.0.1:8091/health; }"
    print "    location = /erm/api/health { auth_basic off; proxy_pass http://127.0.0.1:8091/api/health; }"
    done=1
  }
  { print }
' "$CONF" > "$TMP"
cp "$CONF" "${CONF}.bak.erm-health"
mv "$TMP" "$CONF"
nginx -t
systemctl reload nginx
echo "patched nginx ($MARK)"
