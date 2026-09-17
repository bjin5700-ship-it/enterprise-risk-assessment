"""ERA Assessment Bridge — Chinese risk assessment + real Word/HTML reports.

Mounts `/opt/enterprise-risk-assessment` (or ASSESSMENT_ROOT) and exposes:
  POST /api/v1/assessment/run
  GET  /api/v1/assessment/files/{file_id}
  GET  /health
"""

from __future__ import annotations

import hmac
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

ASSESSMENT_ROOT = Path(os.getenv("ASSESSMENT_ROOT", "/opt/enterprise-risk-assessment"))
REPORT_DIR = Path(os.getenv("REPORT_OUTPUT_DIR", "/opt/era-backups/reports"))
BRIDGE_TOKEN = (os.getenv("ERA_BRIDGE_TOKEN") or os.getenv("ERM_ADMIN_TOKEN") or "").strip()
sys.path.insert(0, str(ASSESSMENT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from assess_profile import assess_from_profile, result_to_chinese_dict  # noqa: E402

app = FastAPI(title="ERA Assessment Bridge", version="0.2.0")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# file_id -> absolute path
_FILE_INDEX: dict[str, str] = {}


def _bridge_auth_ok(request: Request) -> bool:
    if not BRIDGE_TOKEN:
        return os.environ.get("ERM_ENV", "").lower() not in ("production", "prod")
    got = (request.headers.get("X-ERA-Token") or request.headers.get("X-ERM-Token") or "").strip()
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        got = got or auth[7:].strip()
    return bool(got and hmac.compare_digest(got, BRIDGE_TOKEN))


@app.middleware("http")
async def require_bridge_token(request: Request, call_next):
    path = request.url.path or ""
    if path in ("/health", "/openapi.json", "/docs", "/redoc"):
        return await call_next(request)
    if not _bridge_auth_ok(request):
        return JSONResponse(status_code=401, content={"detail": "valid X-ERA-Token required"})
    return await call_next(request)


class AssessmentRequest(BaseModel):
    name: str = Field(..., min_length=1)
    industry: str | None = None
    city: str | None = None
    country: str | None = None
    employee_count: int | None = None
    annual_revenue: float | None = None
    credit_score: int | None = None
    description: str | None = None
    excel_path: str | None = Field(
        default=None,
        description="Optional path to 企业风险信息搜集表 .xlsx under ASSESSMENT_ROOT",
    )
    formats: list[str] = Field(default_factory=lambda: ["html", "docx"])
    sheet_overrides: dict[str, dict[str, Any]] | None = None

    @field_validator("excel_path")
    @classmethod
    def _excel_under_root(cls, v: str | None) -> str | None:
        if not v:
            return v
        raw = Path(v)
        if raw.is_absolute():
            resolved = raw.resolve()
        else:
            resolved = (ASSESSMENT_ROOT / raw).resolve()
        root = ASSESSMENT_ROOT.resolve()
        if root not in resolved.parents and resolved != root:
            raise ValueError("excel_path must stay under ASSESSMENT_ROOT")
        if resolved.suffix.lower() not in (".xlsx", ".xls"):
            raise ValueError("excel_path must be an Excel workbook")
        return str(resolved)


def _safe_name(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in " _-()（）").strip() or "enterprise"


def _register(path: str) -> str:
    fid = uuid.uuid4().hex
    _FILE_INDEX[fid] = path
    # persist for process restart / multi-worker (best-effort)
    try:
        index_path = REPORT_DIR / ".file_index.json"
        existing: dict[str, str] = {}
        if index_path.exists():
            existing = json.loads(index_path.read_text(encoding="utf-8") or "{}")
        existing[fid] = path
        index_path.write_text(json.dumps(existing, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return fid


def _lookup(file_id: str) -> str | None:
    if file_id in _FILE_INDEX:
        return _FILE_INDEX[file_id]
    try:
        index_path = REPORT_DIR / ".file_index.json"
        if index_path.exists():
            data = json.loads(index_path.read_text(encoding="utf-8") or "{}")
            path = data.get(file_id)
            if path:
                _FILE_INDEX[file_id] = path
                return path
    except Exception:
        return None
    return None


def _run_engine(payload: dict[str, Any]):
    excel = payload.get("excel_path")
    if excel:
        path = Path(excel)
        if not path.exists():
            raise HTTPException(status_code=400, detail=f"excel_not_found: {path}")
        from risk_engine import run_assessment

        return run_assessment(str(path), payload.get("name") or "")
    return assess_from_profile(payload)


def _generate_files(result, formats: list[str]) -> list[dict[str, str]]:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    company = _safe_name(result.company_name)
    out: list[dict[str, str]] = []
    wanted = {f.lower() for f in formats}

    if "html" in wanted:
        from report_html import HTMLReportGenerator

        path = str(REPORT_DIR / f"企业风险评估报告_{company}_{ts}.html")
        HTMLReportGenerator(result, output_path=path).generate()
        fid = _register(path)
        out.append(
            {
                "format": "html",
                "file_id": fid,
                "filename": Path(path).name,
                "download_path": f"/api/v1/assessment/files/{fid}",
            }
        )
    if "docx" in wanted or "word" in wanted:
        from report_word import WordReportGenerator

        path = str(REPORT_DIR / f"企业风险评估报告_{company}_{ts}.docx")
        WordReportGenerator(result, output_path=path).generate()
        fid = _register(path)
        out.append(
            {
                "format": "docx",
                "file_id": fid,
                "filename": Path(path).name,
                "download_path": f"/api/v1/assessment/files/{fid}",
            }
        )

    if "pdf" in wanted:
        try:
            from report_pdf import PDFReportGenerator

            path = str(REPORT_DIR / f"企业风险评估报告_{company}_{ts}.pdf")
            PDFReportGenerator(result, output_path=path).generate()
            fid = _register(path)
            out.append(
                {
                    "format": "pdf",
                    "file_id": fid,
                    "filename": Path(path).name,
                    "download_path": f"/api/v1/assessment/files/{fid}",
                }
            )
        except Exception as exc:  # noqa: BLE001
            out.append({"format": "pdf", "error": str(exc)})

    return out


@app.get("/api/v1/assessment/latest")
def latest_assessment() -> dict[str, Any]:
    path = ASSESSMENT_ROOT / "web_app" / "data" / "latest_assessment.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="no_latest_assessment")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"latest_unreadable: {exc}") from exc
    return {"ok": True, "assessment": data}


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "service": "assessment-bridge",
        "assessment_root": str(ASSESSMENT_ROOT),
        "auth_required": bool(BRIDGE_TOKEN),
    }


@app.post("/api/v1/assessment/run")
def run_assessment_api(body: AssessmentRequest) -> dict[str, Any]:
    payload = body.model_dump()
    try:
        result = _run_engine(payload)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"assessment_failed: {exc}") from exc

    chinese = result_to_chinese_dict(result)
    try:
        files = _generate_files(result, body.formats or ["html", "docx"])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"report_generate_failed: {exc}") from exc

    return {
        "ok": True,
        "assessment": chinese,
        "files": files,
    }


@app.get("/api/v1/assessment/files/{file_id}")
def download_file(file_id: str):
    if not file_id or len(file_id) > 64 or not all(c in "0123456789abcdef" for c in file_id.lower()):
        raise HTTPException(status_code=400, detail="invalid_file_id")
    path = _lookup(file_id)
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="file_not_found")
    resolved = Path(path).resolve()
    if REPORT_DIR.resolve() not in resolved.parents:
        raise HTTPException(status_code=403, detail="file_forbidden")
    return FileResponse(
        str(resolved),
        filename=resolved.name,
        media_type="application/octet-stream",
    )
