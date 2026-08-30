# -*- coding: utf-8 -*-
"""法规/内控条文检索。本地语料为主，可选对接 EnterpriseRiskAI knowledge-service。
LLM 不打分，只提供可点击引用。
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

# 官方公开文本页（可点击）。未覆盖维度回落到 ISO 31000。
CORPUS: List[dict] = [
    {"id": "aqsc", "title": "中华人民共和国安全生产法", "url": "https://www.gov.cn/xinwen/2021-06/11/content_5616918.htm",
     "dimensions": ["安全生产风险", "生产运营风险"], "industries": ["化工", "制造业", "建筑"], "article": "企业须建立全员安全生产责任制"},
    {"id": "hjbh", "title": "中华人民共和国环境保护法", "url": "https://www.gov.cn/zhengce/2014-04/25/content_2666348.htm",
     "dimensions": ["环境风险"], "industries": ["化工", "制造业"], "article": "排放须符合国家和地方标准"},
    {"id": "pipl", "title": "中华人民共和国个人信息保护法", "url": "https://www.gov.cn/xinwen/2021-08/20/content_5632486.htm",
     "dimensions": ["数据隐私合规风险", "技术与信息安全风险"], "industries": ["信息技术", "金融"], "article": "处理个人信息应取得同意并履行告知义务"},
    {"id": "dsl", "title": "中华人民共和国数据安全法", "url": "https://www.gov.cn/xinwen/2021-06/11/content_5616919.htm",
     "dimensions": ["数据隐私合规风险", "技术与信息安全风险"], "industries": ["信息技术", "金融"], "article": "建立数据分类分级与风险监测"},
    {"id": "gsf", "title": "中华人民共和国公司法", "url": "https://www.gov.cn/yaowen/liebiao/202312/content_6921935.htm",
     "dimensions": ["公司治理风险", "法律与合规风险"], "industries": [], "article": "董事、监事、高级管理人员忠实勤勉义务"},
    {"id": "ldf", "title": "中华人民共和国劳动法", "url": "https://www.gov.cn/banshi/2005-05/25/content_905.htm",
     "dimensions": ["人力资源风险", "法律与合规风险"], "industries": [], "article": "劳动合同与劳动保护"},
    {"id": "ssf", "title": "中华人民共和国税收征收管理法", "url": "https://www.gov.cn/banshi/2005-05/26/content_1131.htm",
     "dimensions": ["税务风险", "财务风险"], "industries": [], "article": "依法申报纳税，配合税务检查"},
    {"id": "qysds", "title": "中华人民共和国企业所得税法", "url": "https://www.gov.cn/flfg/2007-03/19/content_554243.htm",
     "dimensions": ["税务风险"], "industries": [], "article": "收入、扣除与转让定价规则"},
    {"id": "iso31000", "title": "ISO 31000:2018 风险管理指南", "url": "https://www.iso.org/standard/65694.html",
     "dimensions": [], "industries": [], "article": "风险识别、分析、评价与处理循环"},
    {"id": "iso45001", "title": "ISO 45001 职业健康安全管理体系", "url": "https://www.iso.org/standard/63787.html",
     "dimensions": ["安全生产风险"], "industries": ["制造业", "建筑", "化工"], "article": "危险源辨识与运行控制"},
    {"id": "iso14001", "title": "ISO 14001 环境管理体系", "url": "https://www.iso.org/standard/60857.html",
     "dimensions": ["环境风险"], "industries": ["化工", "制造业"], "article": "环境因素与合规义务"},
    {"id": "iso27001", "title": "ISO/IEC 27001 信息安全管理", "url": "https://www.iso.org/standard/27001.html",
     "dimensions": ["技术与信息安全风险", "数据隐私合规风险"], "industries": ["信息技术"], "article": "信息安全控制与持续改进"},
    {"id": "coso", "title": "COSO ERM 2017", "url": "https://www.coso.org/erm",
     "dimensions": ["公司治理风险", "财务风险"], "industries": [], "article": "治理与文化、战略与目标设定"},
    {"id": "whp", "title": "危险化学品安全管理条例", "url": "https://www.gov.cn/zhengce/2021-12/21/content_5720426.htm",
     "dimensions": ["安全生产风险", "供应链风险"], "industries": ["化工"], "article": "危化品生产、储存、运输许可"},
]


def _local_lookup(dimension: str = "", industry: str = "", limit: int = 3) -> List[dict]:
    dim = (dimension or "").strip()
    ind = (industry or "").strip()
    scored = []
    for row in CORPUS:
        score = 0
        if dim and dim in (row.get("dimensions") or []):
            score += 3
        if ind and ind in (row.get("industries") or []):
            score += 2
        if dim and dim[:2] in row.get("title", ""):
            score += 1
        if row["id"] in ("iso31000", "coso"):
            score = max(score, 1)
        if score:
            scored.append((score, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    seen = set()
    for _, row in scored:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        out.append({
            "id": row["id"],
            "title": row["title"],
            "url": row["url"],
            "article": row.get("article") or "",
            "source": "local",
        })
        if len(out) >= limit:
            break
    if not out:
        row = next(r for r in CORPUS if r["id"] == "iso31000")
        out.append({"id": row["id"], "title": row["title"], "url": row["url"], "article": row.get("article") or "", "source": "local"})
    return out


def _remote_lookup(query: str, limit: int = 3) -> List[dict]:
    base = (os.environ.get("ERM_KNOWLEDGE_URL") or "").strip().rstrip("/")
    if not base or not query:
        return []
    url = f"{base}?q={query}&limit={limit}"
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError):
        return []
    rows = data.get("items") or data.get("results") or data if isinstance(data, list) else []
    out = []
    for row in rows[:limit]:
        if not isinstance(row, dict):
            continue
        title = row.get("title") or row.get("name") or ""
        link = row.get("url") or row.get("link") or ""
        if title and link:
            out.append({"id": str(row.get("id") or title)[:40], "title": title, "url": link,
                        "article": str(row.get("snippet") or row.get("article") or "")[:160], "source": "knowledge-service"})
    return out


def lookup_citations(dimension: str = "", industry: str = "", limit: int = 3) -> List[dict]:
    remote = _remote_lookup(f"{dimension} {industry}".strip(), limit=limit)
    local = _local_lookup(dimension, industry, limit=limit)
    merged = []
    seen = set()
    for row in remote + local:
        key = row.get("url") or row.get("title")
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)
        if len(merged) >= limit:
            break
    return merged


def attach_citations(items: List[dict], *, dimension_key: str = "dimension", industry: str = "") -> List[dict]:
    for item in items or []:
        if not isinstance(item, dict):
            continue
        dim = str(item.get(dimension_key) or item.get("name") or "")
        cites = lookup_citations(dim, industry, limit=2)
        item["citations"] = cites
        if not item.get("regulatory_refs"):
            item["regulatory_refs"] = [c["title"] for c in cites]
    return items
