# -*- coding: utf-8 -*-
"""服务器部署配置 — 公网地址、生产模式"""

from __future__ import annotations

import os


def is_production() -> bool:
    return os.environ.get("ERM_ENV", "").lower() in ("production", "prod")


def get_port() -> int:
    return int(os.environ.get("ERM_PORT", "8088"))


def get_host() -> str:
    return os.environ.get("ERM_HOST", "0.0.0.0")


def get_public_base_url() -> str:
    """客户访问的根 URL，用于 OAuth 回调、文档说明等。优先 ERM_PUBLIC_URL。"""
    explicit = (os.environ.get("ERM_PUBLIC_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit
    if is_production():
        # 生产环境务必配置 ERM_PUBLIC_URL=https://your-domain.com
        port = get_port()
        return f"http://0.0.0.0:{port}"
    port = get_port()
    return f"http://127.0.0.1:{port}"


def get_oauth_redirect_uri() -> str:
    return f"{get_public_base_url()}/api/integrations/oauth/callback"
