"""Parse fnlttSinglAcntAll (CFS all-accounts) responses into FinancialFact rows,
and detect key accounts for the DEBUG wide summary.

This module does NOT compute ratios or benchmarks (out of scope for Loop 1). Key
account detection here is only to (a) verify the key accounts EXIST in the CFS and
(b) build a human-readable wide summary. Amounts are parsed to Decimal (verbatim),
never rescaled.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

# Standardized concept -> candidate account_ids + account_nm keywords.
# These are IFRS/DART concepts (industry-agnostic), NOT company-specific logic.
KEY_ACCOUNTS = {
    "자산총계": {"ids": ["ifrs-full_Assets", "ifrs_Assets"],
              "nm": ["자산총계"]},
    "부채총계": {"ids": ["ifrs-full_Liabilities", "ifrs_Liabilities"],
              "nm": ["부채총계"]},
    "자본총계": {"ids": ["ifrs-full_Equity", "ifrs_Equity"],
              "nm": ["자본총계"]},
    "매출액": {"ids": ["ifrs-full_Revenue", "ifrs-full_RevenueFromContractsWithCustomers",
                    "dart_Revenue"],
             "nm": ["매출액", "수익(매출액)", "영업수익"]},
    "영업이익": {"ids": ["dart_OperatingIncomeLoss",
                     "ifrs-full_ProfitLossFromOperatingActivities"],
              "nm": ["영업이익", "영업이익(손실)"]},
    "당기순이익": {"ids": ["ifrs-full_ProfitLoss"],
               "nm": ["당기순이익", "당기순이익(손실)", "연결당기순이익"]},
}


def parse_amount(raw) -> Decimal | None:
    """Parse an OpenDART amount string to a Decimal. Blank/'-' -> None (not 0)."""
    if raw is None:
        return None
    s = str(raw).strip().replace(",", "")
    if s in ("", "-"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    try:
        v = Decimal(s)
    except InvalidOperation:
        return None
    return -v if neg else v


def parse_cfs_rows(data: dict, *, corp_code: str, corp_name: str, stock_code: str = "",
                   bsns_year, reprt_code, fs_div: str, retrieved_at: str, req_hash: str,
                   raw_path: str) -> list[dict]:
    """Return FinancialFact rows (LONG). fs_div_actual == fs_div (CFS only)."""
    rows = []
    for it in (data.get("list") or []):
        rows.append({
            "corp_code": corp_code,
            "stock_code": stock_code,
            "corp_name": corp_name,
            "bsns_year": str(bsns_year),
            "reprt_code": str(reprt_code),
            "fs_div": fs_div,
            "fs_div_actual": fs_div,
            "sj_div": it.get("sj_div", ""),
            "sj_nm": it.get("sj_nm", ""),
            "account_id": (it.get("account_id") or "").strip(),
            "account_nm": (it.get("account_nm") or "").strip(),
            "amount": parse_amount(it.get("thstrm_amount")),
            "currency": (it.get("currency") or "").strip(),
            "unit": 1,
            "rcept_no": (it.get("rcept_no") or "").strip(),
            "ord": it.get("ord", ""),
            "retrieved_at": retrieved_at,
            "request_hash": req_hash,
            "raw_path": raw_path,
        })
    return rows


def detect_key_accounts(rows: list[dict]) -> dict:
    """For one company's CFS rows, find each key account's amount + how it matched.

    Returns {concept: {"amount", "account_id", "account_nm", "match", "rcept_no"}}.
    concept absent -> match == 'MISSING' (surfaced, never hidden).
    """
    result = {}
    for concept, spec in KEY_ACCOUNTS.items():
        found = None
        # 1) exact account_id
        for r in rows:
            if r["account_id"] and r["account_id"] in spec["ids"]:
                found = (r, "account_id"); break
        # 2) exact account_nm
        if not found:
            for r in rows:
                if r["account_nm"] in spec["nm"]:
                    found = (r, "account_nm"); break
        # 3) account_nm contains keyword
        if not found:
            for r in rows:
                if any(k in r["account_nm"] for k in spec["nm"]):
                    found = (r, "account_nm_contains"); break
        if found:
            r, how = found
            result[concept] = {
                "amount": r["amount"], "account_id": r["account_id"],
                "account_nm": r["account_nm"], "match": how, "rcept_no": r["rcept_no"],
            }
        else:
            result[concept] = {"amount": None, "account_id": "", "account_nm": "",
                               "match": "MISSING", "rcept_no": ""}
    return result
