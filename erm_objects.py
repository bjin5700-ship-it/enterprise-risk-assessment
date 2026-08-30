# -*- coding: utf-8 -*-
"""E2 对象存储：MinIO 为主，未配置时写本地 exports。"""
from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Optional, Tuple

from erm_store import data_dir, insert_evidence


def _endpoint() -> str:
    return (os.environ.get("ERM_MINIO_ENDPOINT") or os.environ.get("MINIO_ENDPOINT") or "").strip()


def _access() -> str:
    return (os.environ.get("ERM_MINIO_ACCESS_KEY") or os.environ.get("MINIO_ACCESS_KEY") or "").strip()


def _secret() -> str:
    return (os.environ.get("ERM_MINIO_SECRET_KEY") or os.environ.get("MINIO_SECRET_KEY") or "").strip()


def _bucket() -> str:
    return (os.environ.get("ERM_MINIO_BUCKET") or os.environ.get("MINIO_BUCKET") or "erm").strip() or "erm"


def _secure() -> bool:
    return (os.environ.get("ERM_MINIO_SECURE") or "").strip().lower() in ("1", "true", "yes")


def using_minio() -> bool:
    return bool(_endpoint() and _access() and _secret())


def _client():
    from minio import Minio
    ep = _endpoint().replace("http://", "").replace("https://", "")
    return Minio(ep, access_key=_access(), secret_key=_secret(), secure=_secure())


def ensure_bucket() -> None:
    if not using_minio():
        return
    client = _client()
    name = _bucket()
    if not client.bucket_exists(name):
        client.make_bucket(name)


def object_store_status() -> dict:
    if not using_minio():
        return {"backend": "local", "connected": False, "note": "未配置 ERM_MINIO_ENDPOINT"}
    try:
        ensure_bucket()
        return {"backend": "minio", "connected": True, "bucket": _bucket(), "endpoint": _endpoint()}
    except Exception as exc:
        return {"backend": "minio", "connected": False, "note": str(exc), "bucket": _bucket()}


def _safe_part(text: str) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", str(text or "file"))
    return s.strip("._")[:80] or "file"


def put_file(
    local_path: str,
    *,
    kind: str = "export",
    content_type: str = "application/octet-stream",
    assessment_id: str = "",
    company_name: str = "",
) -> dict:
    if not local_path or not os.path.isfile(local_path):
        raise FileNotFoundError(local_path)
    filename = os.path.basename(local_path)
    size = os.path.getsize(local_path)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    key = f"{kind}/{_safe_part(company_name) or 'general'}/{stamp}_{_safe_part(filename)}"
    storage = "local"
    object_key = local_path
    if using_minio():
        try:
            ensure_bucket()
            _client().fput_object(_bucket(), key, local_path, content_type=content_type)
            storage = "minio"
            object_key = key
        except Exception:
            storage = "local"
            object_key = local_path
    rec = insert_evidence(
        assessment_id=assessment_id,
        kind=kind,
        filename=filename,
        content_type=content_type,
        storage=storage,
        object_key=object_key,
        size_bytes=size,
    )
    rec["local_path"] = local_path
    return rec


def open_object(record: dict) -> Tuple[str, Optional[bytes]]:
    """返回 (path_or_empty, bytes_or_none)。MinIO 读入内存；本地返回路径。"""
    storage = (record or {}).get("storage") or "local"
    key = (record or {}).get("object_key") or ""
    if storage == "minio" and using_minio() and key:
        resp = _client().get_object(_bucket(), key)
        try:
            data = resp.read()
        finally:
            resp.close()
            resp.release_conn()
        return "", data
    if key and os.path.isfile(key):
        return key, None
    fallback = os.path.join(data_dir(), "exports", os.path.basename(key))
    if os.path.isfile(fallback):
        return fallback, None
    raise FileNotFoundError(key or "object")
