"""corpCode master parsing and target resolution.

The corpCode master maps corp_code <-> corp_name <-> stock_code, but does NOT
carry induty_code (industry). Industry is fetched per company via company.json
(see collect.py).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET


class ResolveError(RuntimeError):
    """Ambiguous or missing target — a hard stop, not a guess."""


def parse_corp_codes(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    out = []
    for el in root.iter("list"):
        out.append({
            "corp_code": (el.findtext("corp_code") or "").strip(),
            "corp_name": (el.findtext("corp_name") or "").strip(),
            "stock_code": (el.findtext("stock_code") or "").strip(),
            "modify_date": (el.findtext("modify_date") or "").strip(),
        })
    return out


def resolve_by_stock(records: list[dict], stock_code: str) -> dict:
    stock_code = stock_code.strip()
    hits = [r for r in records if r["stock_code"] == stock_code]
    if not hits:
        raise ResolveError(
            f"종목코드 {stock_code} 에 해당하는 corp_code를 찾지 못했습니다. (STOP)")
    if len(hits) > 1:
        names = ", ".join(h["corp_name"] for h in hits)
        raise ResolveError(
            f"종목코드 {stock_code} 가 여러 회사에 매칭됩니다({names}). 자동 선택하지 않습니다. (STOP)")
    return hits[0]


def listed_companies(records: list[dict]) -> list[dict]:
    """Companies with a non-empty 6-digit stock_code (i.e., listed)."""
    return [r for r in records if r["stock_code"] and r["stock_code"].strip()]
