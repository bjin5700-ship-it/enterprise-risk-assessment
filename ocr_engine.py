"""扫描件 OCR：优先 RapidOCR（PP-OCR ONNX），可选 PaddleOCR。懒加载。"""
from __future__ import annotations

import io
import os
from typing import Any, Dict, List

_MAX_PAGES = 3
_engine_name = ""
_engine = None


def ocr_status() -> Dict[str, Any]:
    paddle = _can_import("paddleocr")
    rapid = _can_import("rapidocr_onnxruntime") or _can_import("rapidocr")
    pdfium = _can_import("pypdfium2")
    pypdf = _can_import("pypdf") or _can_import("PyPDF2")
    docx = _can_import("docx")
    return {
        "paddleocr": paddle,
        "rapidocr": rapid,
        "pdfium": pdfium,
        "pypdf": pypdf,
        "python_docx": docx,
        "ready": paddle or rapid,
        "active": _engine_name or ("paddleocr" if paddle else ("rapidocr" if rapid else "")),
    }


def _can_import(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def ocr_images(images: List[bytes]) -> Dict[str, Any]:
    if not images:
        return {"ok": False, "backend": "none", "text": "", "detail": "无图像"}
    text, backend, err = _run_ocr(images[:_MAX_PAGES])
    compact = "\n".join(line.strip() for line in (text or "").splitlines() if line.strip())
    if compact:
        return {
            "ok": True,
            "backend": backend,
            "text": compact[:50000],
            "detail": f"OCR {backend} 识别 {len(compact)} 字（最多 {_MAX_PAGES} 页）",
        }
    return {
        "ok": False,
        "backend": backend or "none",
        "text": "",
        "detail": err or "OCR 未识别到文字",
    }


def render_pdf_pages(data: bytes, *, max_pages: int = _MAX_PAGES) -> List[bytes]:
    try:
        import pypdfium2 as pdfium  # type: ignore
    except Exception:
        return []
    try:
        doc = pdfium.PdfDocument(data)
        out: List[bytes] = []
        n = min(len(doc), max_pages)
        for i in range(n):
            page = doc[i]
            bitmap = page.render(scale=1.8)
            pil = bitmap.to_pil()
            buf = io.BytesIO()
            pil.convert("RGB").save(buf, format="PNG")
            out.append(buf.getvalue())
        return out
    except Exception:
        return []


def _run_ocr(images: List[bytes]) -> tuple[str, str, str]:
    global _engine, _engine_name
    prefer = (os.getenv("ERM_OCR_ENGINE") or "").strip().lower()
    order = ["rapidocr", "paddleocr"]
    if prefer in order:
        order = [prefer] + [x for x in order if x != prefer]
    errors: List[str] = []
    for name in order:
        try:
            text = _ocr_paddle(images) if name == "paddleocr" else _ocr_rapid(images)
            if text.strip():
                return text, name, ""
            errors.append(f"{name}: empty")
        except Exception as e:
            errors.append(f"{name}: {e}")
    return "", _engine_name or "", "; ".join(errors)[:300]


def _ocr_paddle(images: List[bytes]) -> str:
    global _engine, _engine_name
    from paddleocr import PaddleOCR  # type: ignore

    if _engine_name != "paddleocr" or _engine is None:
        kwargs = {"lang": "ch", "show_log": False}
        try:
            _engine = PaddleOCR(use_angle_cls=True, **kwargs)
        except TypeError:
            _engine = PaddleOCR(lang="ch")
        _engine_name = "paddleocr"
    lines: List[str] = []
    for raw in images:
        img = _to_ndarray(raw)
        result = _engine.ocr(img, cls=True) if hasattr(_engine, "ocr") else _engine.predict(img)
        lines.extend(_parse_paddle_result(result))
    return "\n".join(lines)


def _ocr_rapid(images: List[bytes]) -> str:
    global _engine, _engine_name
    RapidOCR = None
    try:
        from rapidocr_onnxruntime import RapidOCR  # type: ignore
    except Exception:
        from rapidocr import RapidOCR  # type: ignore

    if _engine_name != "rapidocr" or _engine is None:
        _engine = RapidOCR()
        _engine_name = "rapidocr"
    lines: List[str] = []
    for raw in images:
        img = _to_ndarray(raw)
        result = _engine(img)
        payload = result[0] if isinstance(result, tuple) else result
        if not payload:
            continue
        for item in payload:
            if isinstance(item, dict):
                t = str(item.get("text") or item.get("rec_txt") or "").strip()
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                t = str(item[1]).strip()
            else:
                t = ""
            if t:
                lines.append(t)
    return "\n".join(lines)


def _to_ndarray(raw: bytes):
    import numpy as np  # type: ignore
    from PIL import Image  # type: ignore

    img = Image.open(io.BytesIO(raw)).convert("RGB")
    return np.array(img)


def _parse_paddle_result(result: Any) -> List[str]:
    lines: List[str] = []
    if result is None:
        return lines
    pages = result if isinstance(result, list) else [result]
    for page in pages:
        if not page:
            continue
        if isinstance(page, dict):
            recs = page.get("rec_texts") or page.get("text") or []
            if isinstance(recs, str):
                lines.append(recs)
            else:
                lines.extend(str(x) for x in recs if str(x).strip())
            continue
        for item in page:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                rec = item[1]
                if isinstance(rec, (list, tuple)) and rec:
                    lines.append(str(rec[0]))
                else:
                    lines.append(str(rec))
    return [x.strip() for x in lines if str(x).strip()]
