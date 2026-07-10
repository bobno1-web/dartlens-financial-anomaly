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


def resolve_by_name(records: list[dict], name: str) -> dict:
    """정확 회사명 → 상장사 레코드. 유사매칭(fuzzy) 없이 **정확일치만**(safety-rules §3).

    0건/복수건이면 추측하지 않고 ResolveError(STOP). corpCode master의 corp_name 기준이며,
    회사 하드코딩이 아니라 입력값을 데이터에서 조회한다(CLAUDE.md 규칙#1).
    """
    name = (name or "").strip()
    hits = [r for r in listed_companies(records) if r["corp_name"] == name]
    if not hits:
        raise ResolveError(
            f"회사명 '{name}' 에 해당하는 상장사를 찾지 못했습니다. "
            f"정확한 회사명 또는 6자리 종목코드를 입력하세요. (STOP)")
    if len(hits) > 1:
        codes = ", ".join(f"{h['corp_name']}({h['stock_code']})" for h in hits)
        raise ResolveError(
            f"회사명 '{name}' 이 여러 상장사에 매칭됩니다({codes}). 6자리 종목코드로 입력하세요. (STOP)")
    return hits[0]
