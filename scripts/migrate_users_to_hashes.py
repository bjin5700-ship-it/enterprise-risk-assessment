#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Migrate web_app/data/users.json plaintext passwords to werkzeug hashes."""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
USERS = os.path.join(ROOT, "web_app", "data", "users.json")


def main() -> int:
    from werkzeug.security import generate_password_hash

    if not os.path.isfile(USERS):
        print("missing", USERS)
        return 1
    with open(USERS, "r", encoding="utf-8") as f:
        data = json.load(f)
    users = data.get("users") if isinstance(data, dict) else data
    if not isinstance(users, list):
        print("invalid users file")
        return 1
    changed = 0
    for row in users:
        if not isinstance(row, dict):
            continue
        if row.get("password_hash"):
            row.pop("password", None)
            continue
        plain = str(row.pop("password", "") or "").strip()
        if not plain:
            continue
        row["password_hash"] = generate_password_hash(plain)
        changed += 1
    with open(USERS, "w", encoding="utf-8") as f:
        json.dump({"users": users}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"migrated {changed} user(s) -> password_hash")
    return 0


if __name__ == "__main__":
    sys.exit(main())
