# -*- coding: utf-8 -*-
"""E1: unauthenticated writes 401; SMTP password not on page; roles."""
import hashlib
import hmac
import json
import os
import sys
import base64

ROOT = r"D:\_Work\01_Projects\enterprise-risk-assessment"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

os.environ["ERM_AUTH_MODE"] = "on"
os.environ["ERM_ENV"] = "development"
os.environ["ERM_ADMIN_USER"] = "admin"
os.environ["ERM_ADMIN_PASSWORD"] = "e1-admin-pass"
os.environ["ERM_DIRECTOR_USER"] = "board"
os.environ["ERM_DIRECTOR_PASSWORD"] = "e1-board-pass"
os.environ["ERM_JWT_SECRET"] = "e1-jwt-secret-must-be-at-least-32ch"
os.environ.pop("ERM_ADMIN_TOKEN", None)

from erm_auth import is_demo_record, filter_history, decode_hs256_jwt, user_from_jwt
from web_app.app import app


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _jwt(payload: dict) -> str:
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64url(json.dumps(payload).encode())
    secret = os.environ["ERM_JWT_SECRET"]
    sig = hmac.new(secret.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    return f"{header}.{body}.{_b64url(sig)}"


def main() -> None:
    html = open(os.path.join(ROOT, "web_app", "templates", "data_entry.html"), encoding="utf-8").read()
    assert "notifySmtpPass" not in html
    assert "id=\"ermAdminToken\"" not in html
    assert "id=\"oauthClientSecret\"" not in html
    assert "id=\"mobileFcmKey\"" not in html
    assert "SMTP 密码" not in html

    recs = [
        {"id": "demo-mfg", "company_name": "DEMO-江东精密制造"},
        {"id": "real-1", "company_name": "万得集团"},
    ]
    assert filter_history(recs, None) == [recs[0]]
    assert is_demo_record(recs[0])

    token = _jwt({"sub": "u1", "email": "a@corp.com", "roles": ["assessor"], "type": "access"})
    assert decode_hs256_jwt(token, os.environ["ERM_JWT_SECRET"])["email"] == "a@corp.com"
    u = user_from_jwt(token)
    assert u and u.role == "assessor"

    app.config["TESTING"] = True
    app.config["SESSION_COOKIE_SECURE"] = False
    c = app.test_client()

    r = c.post("/api/assess", json={"企业基本信息": {"企业名称": "X"}})
    assert r.status_code == 401, r.get_json()

    r = c.get("/data-entry")
    assert r.status_code in (302, 301)
    loc = r.headers.get("Location") or ""
    assert "login" in loc

    r = c.get("/report")
    assert r.status_code == 200
    r = c.get("/login")
    assert r.status_code == 200
    page = r.get_data(as_text=True)
    assert "SMTP" in page or "登录" in page
    assert "type=\"password\"" in page  # login password, not SMTP

    r = c.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401

    r = c.post("/api/auth/login", json={"username": "admin", "password": "e1-admin-pass"})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["user"]["role"] == "admin"

    r = c.post("/api/assess", json={"企业基本信息": {"企业名称": "X"}})
    assert r.status_code != 401, r.get_json()

    c.post("/api/auth/logout")
    r = c.post("/api/auth/login", json={"username": "board", "password": "e1-board-pass"})
    assert r.status_code == 200
    assert r.get_json()["user"]["role"] == "director"
    r = c.post("/api/assess", json={"企业基本信息": {"企业名称": "X"}})
    assert r.status_code == 403, r.get_json()
    r = c.get("/data-entry")
    assert r.status_code in (302, 301)

    c.post("/api/auth/logout")
    jwt = _jwt({"sub": "u2", "email": "assessor@corp.com", "roles": ["assessor"], "type": "access"})
    r = c.post("/api/assess", headers={"Authorization": f"Bearer {jwt}"}, json={"企业基本信息": {"企业名称": "X"}})
    assert r.status_code != 401, r.get_json()
    assert r.status_code != 403, r.get_json()

    print("OK e1-auth")


if __name__ == "__main__":
    main()
