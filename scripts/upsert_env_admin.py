# -*- coding: utf-8 -*-
"""把 users.json 中的管理员写入 web_app/.env（不打印口令）。"""
from __future__ import annotations

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USERS = os.path.join(ROOT, "web_app", "data", "users.json")
ENV = os.path.join(ROOT, "web_app", ".env")


def _upsert(text: str, key: str, value: str) -> str:
    line = f"{key}={value}"
    pat = re.compile(rf"^{re.escape(key)}=.*$", re.M)
    if pat.search(text):
        return pat.sub(line, text)
    if text and not text.endswith("\n"):
        text += "\n"
    return text + line + "\n"


def main():
    rows = json.loads(open(USERS, encoding="utf-8").read())
    users = rows.get("users") if isinstance(rows, dict) else rows
    admin = next((u for u in users if str(u.get("role")) == "admin"), users[0])
    name = str(admin["username"])
    pwd = str(admin.get("password") or "")
    text = open(ENV, encoding="utf-8").read() if os.path.isfile(ENV) else ""
    text = _upsert(text, "ERM_ADMIN_USER", name)
    text = _upsert(text, "ERM_ADMIN_PASSWORD", pwd)
    with open(ENV, "w", encoding="utf-8") as f:
        f.write(text)
    print("admin user updated:", name)


if __name__ == "__main__":
    main()
