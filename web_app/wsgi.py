# -*- coding: utf-8 -*-
"""WSGI 入口 — Linux Gunicorn / Windows Waitress 生产部署"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, os.pardir))
for p in (ROOT_DIR, BASE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from app import app  # noqa: E402
from bootstrap import init_server  # noqa: E402

init_server()
application = app

# Serve correctly behind nginx location /erm/ (X-Forwarded-Prefix)
import os as _os
from werkzeug.middleware.proxy_fix import ProxyFix


class _PrefixMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        prefix = (environ.get("HTTP_X_FORWARDED_PREFIX") or _os.environ.get("ERM_URL_PREFIX") or "").rstrip("/")
        if prefix:
            environ["SCRIPT_NAME"] = prefix
        return self.app(environ, start_response)


application = _PrefixMiddleware(ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1))
