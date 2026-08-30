# -*- coding: utf-8 -*-
"""VPS 一次性：创建 erm 库、写入 .env 中的 DATABASE_URL / MinIO（不打印密钥）。"""
from __future__ import annotations

import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path("/opt/enterprise-risk-assessment")
ENV_PATH = ROOT / "web_app" / ".env"


def _env_get(text: str, key: str) -> str:
    m = re.search(rf"^{re.escape(key)}=(.*)$", text, re.M)
    return (m.group(1).strip().strip('"').strip("'") if m else "")


def _upsert_env(text: str, key: str, value: str) -> str:
    line = f"{key}={value}"
    if re.search(rf"^{re.escape(key)}=", text, re.M):
        if _env_get(text, key):
            return text
        return re.sub(rf"^{re.escape(key)}=.*$", line, text, count=1, flags=re.M)
    if text and not text.endswith("\n"):
        text += "\n"
    return text + line + "\n"


def _run(cmd: list[str], input_text: str | None = None) -> str:
    p = subprocess.run(cmd, input=input_text, text=True, capture_output=True, check=False)
    if p.returncode != 0:
        raise RuntimeError(p.stderr or p.stdout or f"fail {' '.join(cmd)}")
    return p.stdout


def main() -> None:
    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.is_file() else ""

    url = _env_get(text, "ERM_DATABASE_URL") or _env_get(text, "DATABASE_URL")
    if not url:
        password = secrets.token_urlsafe(24)
        sql = f"""
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'erm') THEN
    CREATE ROLE erm LOGIN PASSWORD '{password}';
  END IF;
END
$$;
SELECT 'ok';
"""
        _run(["sudo", "-u", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-c", sql])
        _run(["sudo", "-u", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-c",
              f"ALTER ROLE erm WITH PASSWORD '{password}';"])
        dbs = _run(["sudo", "-u", "postgres", "psql", "-tAc", "SELECT 1 FROM pg_database WHERE datname='erm'"]).strip()
        if dbs != "1":
            _run(["sudo", "-u", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-c", "CREATE DATABASE erm OWNER erm;"])
        else:
            _run(["sudo", "-u", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-c", "GRANT ALL PRIVILEGES ON DATABASE erm TO erm;"])
        url = f"postgresql://erm:{password}@127.0.0.1:5432/erm"
        text = _upsert_env(text, "ERM_DATABASE_URL", url)
        text = _upsert_env(text, "DATABASE_URL", url)
        print("postgres: created_or_ready")
    else:
        print("postgres: already_configured")

    endpoint = _env_get(text, "ERM_MINIO_ENDPOINT")
    if not endpoint:
        user = subprocess.check_output(["docker", "exec", "eagos-minio", "printenv", "MINIO_ROOT_USER"], text=True).strip()
        secret = subprocess.check_output(["docker", "exec", "eagos-minio", "printenv", "MINIO_ROOT_PASSWORD"], text=True).strip()
        if not user or not secret:
            raise RuntimeError("minio credentials missing")
        text = _upsert_env(text, "ERM_MINIO_ENDPOINT", "127.0.0.1:9100")
        text = _upsert_env(text, "ERM_MINIO_ACCESS_KEY", user)
        text = _upsert_env(text, "ERM_MINIO_SECRET_KEY", secret)
        text = _upsert_env(text, "ERM_MINIO_BUCKET", "erm")
        text = _upsert_env(text, "ERM_MINIO_SECURE", "0")
        print("minio: env_written")
    else:
        print("minio: already_configured")

    ENV_PATH.write_text(text, encoding="utf-8")
    os.chmod(ENV_PATH, 0o600)
    print("env: updated", str(ENV_PATH))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("FAIL", type(exc).__name__, file=sys.stderr)
        sys.exit(1)
