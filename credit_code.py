"""统一社会信用代码（GB 32100-2015）校验。"""
from __future__ import annotations

import re
from typing import Tuple

_CODES = "0123456789ABCDEFGHJKLMNPQRTUWXY"
_WEIGHTS = (1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28)
_PATTERN = re.compile(r"^[0-9A-Z]{18}$")


def normalize_credit_code(code: str) -> str:
    return re.sub(r"[\s\-]", "", (code or "")).upper()


def validate_credit_code(code: str) -> Tuple[bool, str]:
    """返回 (ok, message)。空字符串视为未填写（ok=True, message=''）。"""
    raw = normalize_credit_code(code)
    if not raw:
        return True, ""
    if len(raw) != 18 or not _PATTERN.match(raw):
        return False, "统一社会信用代码应为 18 位字母或数字"
    try:
        total = sum(_CODES.index(raw[i]) * _WEIGHTS[i] for i in range(17))
    except ValueError:
        return False, "统一社会信用代码含非法字符"
    checksum = 31 - (total % 31)
    if checksum == 31:
        checksum = 0
    expected = _CODES[checksum]
    if raw[17] != expected:
        return False, f"统一社会信用代码校验位不正确（应为 {expected}）"
    return True, raw


def make_credit_code(body17: str) -> str:
    """测试辅助：由 17 位主体生成带校验位的代码。"""
    body = normalize_credit_code(body17)
    if len(body) != 17:
        raise ValueError("body must be 17 chars")
    total = sum(_CODES.index(body[i]) * _WEIGHTS[i] for i in range(17))
    checksum = 31 - (total % 31)
    if checksum == 31:
        checksum = 0
    return body + _CODES[checksum]
