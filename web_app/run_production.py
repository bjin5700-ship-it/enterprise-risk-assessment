# -*- coding: utf-8 -*-
"""生产环境启动 — Waitress (Windows/Linux 通用)"""

from __future__ import annotations

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, os.pardir))
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, BASE_DIR)

os.environ.setdefault("ERM_ENV", "production")

from bootstrap import init_server
from server_config import get_host, get_port, get_public_base_url, is_production


def main():
    init_server()
    host = get_host()
    port = get_port()
    public = get_public_base_url()

    print("=" * 60)
    print("  企业风险动态评估系统 — 生产模式")
    print("=" * 60)
    print(f"  监听: {host}:{port}")
    print(f"  公网访问地址 (ERM_PUBLIC_URL): {public}")
    if is_production() and "0.0.0.0" in public:
        print("  [警告] 请设置环境变量 ERM_PUBLIC_URL=https://您的域名")
    print("=" * 60)

    try:
        from waitress import serve
        from wsgi import application
        serve(application, host=host, port=port, threads=int(os.environ.get("ERM_THREADS", "8")))
    except ImportError:
        print("[错误] 未安装 waitress，请运行: py -3 -m pip install waitress")
        sys.exit(1)


if __name__ == "__main__":
    main()
