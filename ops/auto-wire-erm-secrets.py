#!/usr/bin/env python3
"""Wire ERM admin/bridge tokens + Tianyancha from co-located secrets (VPS only)."""
from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path("/opt/enterprise-risk-assessment")
sys.path.insert(0, str(ROOT))
ERM_ENV = ROOT / "web_app" / ".env"
CIRI_ENV = Path("/opt/ciri-secrets/ciri-channels.env")
ERA_PROD = Path("/opt/era-secrets/era-prod.env")


def parse_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def upsert(text: str, key: str, val: str) -> str:
    line = f"{key}={val}"
    if re.search(rf"^{re.escape(key)}=", text, flags=re.M):
        return re.sub(rf"^{re.escape(key)}=.*$", line, text, count=1, flags=re.M)
    if text and not text.endswith("\n"):
        text += "\n"
    return text + line + "\n"


def write_env(path: Path, pairs: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    for k, v in pairs.items():
        if v:
            text = upsert(text, k, v)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o600)


def main() -> int:
    ciri = parse_env(CIRI_ENV)
    era = parse_env(ERA_PROD)
    erm = parse_env(ERM_ENV)

    tyc = (
        ciri.get("TIANYANCHA_TOKEN")
        or ciri.get("TIANYANCHA_API_KEY")
        or era.get("TIANYANCHA_API_KEY")
        or era.get("TIANYANCHA_TOKEN")
        or erm.get("TIANYANCHA_TOKEN")
        or ""
    ).strip()
    tyc_base = (
        ciri.get("TIANYANCHA_BASE_URL")
        or era.get("TIANYANCHA_BASE_URL")
        or "https://open.api.tianyancha.com"
    ).strip()

    admin = (erm.get("ERM_ADMIN_TOKEN") or era.get("ERM_ADMIN_TOKEN") or "").strip()
    if not admin:
        admin = secrets.token_urlsafe(48)

    bridge = admin
    erm_updates = {
        "ERM_ADMIN_TOKEN": admin,
        "ERA_BRIDGE_TOKEN": bridge,
        "ERM_ENV": erm.get("ERM_ENV") or "production",
    }
    if tyc:
        erm_updates["TIANYANCHA_TOKEN"] = tyc
        erm_updates["TIANYANCHA_BASE_URL"] = tyc_base
        erm_updates["ERM_EXTERNAL_RISK_PROVIDER"] = "tianyancha"
        erm_updates["ERM_EXTERNAL_RISK_URL"] = ""
    else:
        erm_updates.setdefault("ERM_EXTERNAL_RISK_PROVIDER", "demo_fixture")
    ERM_ENV.parent.mkdir(parents=True, exist_ok=True)
    write_env(ERM_ENV, erm_updates)
    for k, v in {**parse_env(ERM_ENV), **erm_updates}.items():
        if v:
            os.environ[k] = v

    if CIRI_ENV.is_file():
        ctext = CIRI_ENV.read_text(encoding="utf-8")
        ctext = upsert(ctext, "CIRI_ERA_BRIDGE_TOKEN", bridge)
        ctext = upsert(ctext, "CIRI_RISK_ECOSYSTEM_ERM_BRIDGE_URL", "http://host.docker.internal:18088")
        if tyc and "TIANYANCHA_TOKEN=" not in ctext and "TIANYANCHA_API_KEY=" in ctext:
            pass  # CIRI already has API key
        CIRI_ENV.write_text(ctext, encoding="utf-8")
        CIRI_ENV.chmod(0o600)

    subprocess.run(["systemctl", "restart", "era-assessment-bridge.service"], check=False)
    subprocess.run(["systemctl", "restart", "erm-assessment.service"], check=False)
    time.sleep(4)

    # Recreate CIRI API to pick up env_file changes
    subprocess.run(
        [
            "docker-compose",
            "-f",
            "/opt/ciri-ai-os/docker-compose.host.yml",
            "--env-file",
            str(CIRI_ENV),
            "up",
            "-d",
            "--no-build",
            "api",
        ],
        cwd="/opt/ciri-ai-os",
        check=False,
    )

    report = {
        "erm_env": str(ERM_ENV),
        "admin_token_set": bool(admin),
        "bridge_token_set": bool(bridge),
        "tianyancha_configured": bool(tyc),
        "external_provider": "tianyancha" if tyc else erm.get("ERM_EXTERNAL_RISK_PROVIDER", "none"),
    }
    try:
        req = urllib.request.Request("http://127.0.0.1:18088/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            report["bridge_health"] = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        report["bridge_health_error"] = str(exc)[:120]

    try:
        from data_external_risk import provider_status

        report["external_risk_status"] = provider_status()
    except Exception as exc:  # noqa: BLE001
        report["external_risk_status"] = {"error": str(exc)[:120]}

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
