"""Ratio INPUT preparation (Loop 2).

Computes each company's INDIVIDUAL ratio value (allowed in Loop 2) with strict
NOT_COMPUTABLE guards and full numerator/denominator source references. Does NOT
compute industry benchmark / median / IQR / HIGH-LOW (that is Loop 3).

Reasons: missing_account, invalid_denominator, mapping_not_confident,
invalid_statement_section.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from . import accounts

BORROWINGS = "__borrowings__"
WORKING_CAPITAL = "__working_capital__"

# (비율명, 그룹, 분자 concept, 분모 concept, 산식 표시)
RATIOS = [
    ("영업이익률", "수익성", "영업이익", "매출액", "영업이익 / 매출액"),
    ("순이익률", "수익성", "당기순이익", "매출액", "당기순이익 / 매출액"),
    ("ROA", "수익성", "당기순이익", "자산총계", "당기순이익 / 기말총자산"),
    ("ROE", "수익성", "당기순이익", "자본총계", "당기순이익 / 기말자본"),
    ("부채비율", "안정성", "부채총계", "자본총계", "부채총계 / 자본총계"),
    ("부채비중", "안정성", "부채총계", "자산총계", "부채총계 / 자산총계"),
    ("유동비율", "안정성", "유동자산", "유동부채", "유동자산 / 유동부채"),
    ("차입금의존도", "안정성", BORROWINGS, "자산총계", "이자부차입금 / 자산총계"),
    ("매출채권비율", "운전자본", "매출채권", "매출액", "매출채권 / 매출액"),
    ("재고자산비율", "운전자본", "재고자산", "매출액", "재고자산 / 매출액"),
    ("매입채무비율", "운전자본", "매입채무", "매출원가", "매입채무 / 매출원가"),
    ("운전자본비율", "운전자본", WORKING_CAPITAL, "매출액", "(유동자산 − 유동부채) / 매출액"),
    ("총자산회전율", "회전율", "매출액", "자산총계", "매출액 / 자산총계"),
    ("재고자산회전율", "회전율", "매출원가", "재고자산", "매출원가 / 재고자산"),
    ("매출채권회전율", "회전율", "매출액", "매출채권", "매출액 / 매출채권"),
]


def _src_str(res: dict) -> str:
    if res.get("match") in (None, "MISSING"):
        return f"(미발견: {res.get('reason', '')})"
    if res.get("match") == "aggregate":
        parts = [f"{n}={r['account_nm']}" for n, r in res.get("components", {}).items()
                 if r.get("match") != "MISSING"]
        return "합산[" + ", ".join(parts) + f"] rcept={_first_rcept(res)}"
    return f"{res.get('account_id') or '-'} | {res.get('account_nm')} | rcept={res.get('rcept_no')} | {res.get('sj_div')}"


def _first_rcept(bres: dict) -> str:
    for r in bres.get("components", {}).values():
        if r.get("match") != "MISSING" and r.get("rcept_no"):
            return r["rcept_no"]
    return ""


def _numerator(concept: str, base: dict, borrow: dict):
    """Return (value, source_str, reason). reason='' if ok."""
    if concept == BORROWINGS:
        return borrow["value"], _src_str(borrow), borrow["reason"]
    if concept == WORKING_CAPITAL:
        ca, cl = base["유동자산"], base["유동부채"]
        if ca["match"] == "MISSING" or cl["match"] == "MISSING":
            reason = "invalid_statement_section" if "invalid_statement_section" in (
                ca["reason"], cl["reason"]) else "missing_account"
            return None, f"유동자산[{_src_str(ca)}] − 유동부채[{_src_str(cl)}]", reason
        return (ca["value"] - cl["value"],
                f"유동자산({ca['account_nm']}) − 유동부채({cl['account_nm']}) rcept={ca['rcept_no']}", "")
    res = base[concept]
    return res["value"], _src_str(res), res["reason"]


def compute_company(company: dict, rows: list[dict]) -> dict:
    """Return per-company ratio input results + coverage + dedup events."""
    base = accounts.resolve_all(rows)
    borrow = accounts.resolve_borrowings(rows)
    ratio_rows = []
    for name, group, num_c, den_c, formula in RATIOS:
        n_val, n_src, n_reason = _numerator(num_c, base, borrow)
        d_res = base.get(den_c)
        d_val = d_res["value"] if d_res else None
        d_src = _src_str(d_res) if d_res else ""
        d_reason = d_res["reason"] if d_res else "missing_account"

        value, computable, reason = None, False, ""
        if n_reason or n_val is None:
            reason = n_reason or "missing_account"
        elif d_val is None:
            reason = d_reason or "missing_account"
        elif d_val <= 0:
            reason = "invalid_denominator"
        else:
            try:
                value = Decimal(n_val) / Decimal(d_val)
                computable = True
            except (InvalidOperation, ZeroDivisionError):
                reason = "invalid_denominator"
        ratio_rows.append({
            "corp_code": company["corp_code"], "stock_code": company.get("stock_code", ""),
            "corp_name": company["corp_name"], "is_target": company.get("is_target", ""),
            "ratio": name, "group": group, "formula": formula,
            "numerator_concept": num_c if not num_c.startswith("__") else num_c.strip("_"),
            "denominator_concept": den_c,
            "numerator_value": n_val, "numerator_src": n_src,
            "denominator_value": d_val, "denominator_src": d_src,
            "ratio_value": value, "computable": computable, "reason": reason,
        })
    coverage = {c: base[c]["match"] for c in accounts.CONCEPTS}
    coverage["이자부차입금"] = borrow["match"]
    return {"ratio_rows": ratio_rows, "coverage": coverage,
            "dedup_events": accounts.dedup_events(rows), "base": base, "borrow": borrow}
