#!/usr/bin/env python3
"""Finish ERM .env when provision_e2_store fails on MinIO."""
import os
import re
import secrets
import subprocess
from pathlib import Path

ROOT = Path("/opt/enterprise-risk-assessment")
ENV = ROOT / "web_app" / ".env"


def run(cmd):
    return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT).strip()


def upsert(text, key, val):
    line = f"{key}={val}"
    if re.search(rf"^{re.escape(key)}=", text, re.M):
        return re.sub(rf"^{re.escape(key)}=.*$", line, text, count=1, flags=re.M)
    if text and not text.endswith("\n"):
        text += "\n"
    return text + line + "\n"


def main():
    text = ENV.read_text(encoding="utf-8") if ENV.is_file() else ""
    url = ""
    m = re.search(r"^ERM_DATABASE_URL=(.*)$", text, re.M)
    if m:
        url = m.group(1).strip().strip('"').strip("'")
    if not url:
        m2 = re.search(r"^DATABASE_URL=(.*)$", text, re.M)
        if m2:
            url = m2.group(1).strip().strip('"').strip("'")
    if not url:
        pwd = secrets.token_urlsafe(20)
        run(["sudo", "-u", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-c",
             f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='erm') THEN CREATE ROLE erm LOGIN PASSWORD '{pwd}'; END IF; END $$;"])
        run(["sudo", "-u", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-c",
             f"ALTER ROLE erm WITH PASSWORD '{pwd}';"])
        dbs = run(["sudo", "-u", "postgres", "psql", "-tAc", "SELECT 1 FROM pg_database WHERE datname='erm'"])
        if dbs.strip() != "1":
            run(["sudo", "-u", "postgres", "psql", "-c", "CREATE DATABASE erm OWNER erm;"])
        url = f"postgresql://erm:{pwd}@127.0.0.1:5432/erm"
        text = upsert(text, "ERM_DATABASE_URL", url)
        text = upsert(text, "DATABASE_URL", url)
        print("postgres_url: written")

    if "ERM_MINIO_ENDPOINT=" not in text or not re.search(r"^ERM_MINIO_ENDPOINT=\s*$", text, re.M):
        for cname in ("eagos-minio", "enterprise-risk-ai-minio-1", "minio"):
            try:
                user = run(["docker", "exec", cname, "printenv", "MINIO_ROOT_USER"])
                secret = run(["docker", "exec", cname, "printenv", "MINIO_ROOT_PASSWORD"])
                port = run(["docker", "inspect", "-f", "{{(index (index .NetworkSettings.Ports \"9000/tcp\") 0).HostPort}}", cname])
                if user and secret:
                    text = upsert(text, "ERM_MINIO_ENDPOINT", f"127.0.0.1:{port or '9100'}")
                    text = upsert(text, "ERM_MINIO_ACCESS_KEY", user)
                    text = upsert(text, "ERM_MINIO_SECRET_KEY", secret)
                    text = upsert(text, "ERM_MINIO_BUCKET", "erm")
                    text = upsert(text, "ERM_MINIO_SECURE", "0")
                    print(f"minio: {cname}")
                    break
            except subprocess.CalledProcessError:
                continue

    tyc = ""
    for line in text.splitlines():
        if line.strip().startswith("TIANYANCHA_TOKEN="):
            tyc = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
    if not tyc:
        text = upsert(text, "ERM_EXTERNAL_RISK_PROVIDER", "demo")
        text = upsert(text, "ERM_EXTERNAL_RISK_URL", "http://127.0.0.1:8091/api/external-risk/demo-feed")
    else:
        text = upsert(text, "ERM_EXTERNAL_RISK_PROVIDER", "tianyancha")
    text = upsert(text, "ERM_AUTH_MODE", "on")
    ENV.write_text(text, encoding="utf-8")
    os.chmod(ENV, 0o600)
    print("env: ok")


if __name__ == "__main__":
    main()
