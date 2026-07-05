"""Account concept resolution for ratio inputs (Loop 2).

Rules (per docs/BUILD_PLAN.md + references/methodology.md):
  - account_id 우선 매칭, account_nm은 **정확 일치** 제한 fallback만 (fuzzy/contains 확장 금지).
  - sj_div 필터 적용. SCE(자본변동표)·CF(현금흐름표) 구성행은 비율 계산 원천에서 제외.
  - 손익계정은 IS/CIS 양쪽 고려(IS 우선).
  - 영업이익은 dart_OperatingIncomeLoss 와 ifrs-full_ProfitLossFromOperatingActivities 모두 고려.
  - 후보가 여러 개면 결정적 규칙으로 하나 선택(tier→sj우선→id우선→최신 rcept_no→최소 ord), 나머지는 dedup 로그.
  - 매칭 실패: allowed 섹션에 없으면 missing_account, 제외 섹션(SCE/CF)에만 있으면 invalid_statement_section.

account_id 후보는 삼성전자 2025 CFS 실측 구조 + DART 확장태그로 구성(회사별 로직 아님).
"""
from __future__ import annotations

from decimal import Decimal

EXCLUDED_SJ = ("SCE", "CF")  # 비율 계산 원천에서 제외

# concept(한글) -> {sj: [...], ids: [...우선순위], nm: [정확일치 후보]}
CONCEPTS = {
    "자산총계": {"sj": ["BS"], "ids": ["ifrs-full_Assets"], "nm": ["자산총계"]},
    "유동자산": {"sj": ["BS"], "ids": ["ifrs-full_CurrentAssets"], "nm": ["유동자산"]},
    "부채총계": {"sj": ["BS"], "ids": ["ifrs-full_Liabilities"], "nm": ["부채총계"]},
    "유동부채": {"sj": ["BS"], "ids": ["ifrs-full_CurrentLiabilities"], "nm": ["유동부채"]},
    "자본총계": {"sj": ["BS"], "ids": ["ifrs-full_Equity"], "nm": ["자본총계"]},
    "재고자산": {"sj": ["BS"], "ids": ["ifrs-full_Inventories"], "nm": ["재고자산"]},
    "매출채권": {"sj": ["BS"], "ids": ["ifrs-full_CurrentTradeReceivables",
                                   "dart_ShortTermTradeReceivable", "ifrs-full_TradeReceivables"],
              "nm": ["매출채권"]},
    "매입채무": {"sj": ["BS"], "ids": ["ifrs-full_TradeAndOtherCurrentPayablesToTradeSuppliers",
                                   "dart_ShortTermTradePayables", "ifrs-full_TradePayables"],
              "nm": ["매입채무"]},
    "매출액": {"sj": ["IS", "CIS"], "ids": ["ifrs-full_Revenue",
                                        "ifrs-full_RevenueFromContractsWithCustomers", "dart_Revenue"],
             "nm": ["매출액", "수익(매출액)", "영업수익"]},
    "매출원가": {"sj": ["IS", "CIS"], "ids": ["ifrs-full_CostOfSales"], "nm": ["매출원가"]},
    "영업이익": {"sj": ["IS", "CIS"], "ids": ["dart_OperatingIncomeLoss",
                                         "ifrs-full_ProfitLossFromOperatingActivities"],
              "nm": ["영업이익", "영업이익(손실)"]},
    "당기순이익": {"sj": ["IS", "CIS"], "ids": ["ifrs-full_ProfitLoss"],
               "nm": ["당기순이익", "당기순이익(손실)"]},
}

# 이자부 차입금 구성(합산). 리스부채는 제외.
BORROWING_COMPONENTS = {
    "단기차입금": {"sj": ["BS"], "ids": ["ifrs-full_ShorttermBorrowings", "dart_ShortTermBorrowings"],
              "nm": ["단기차입금"]},
    "유동성장기부채": {"sj": ["BS"], "ids": ["ifrs-full_CurrentPortionOfLongtermBorrowings"],
                "nm": ["유동성장기부채", "유동성장기차입금"]},
    "사채": {"sj": ["BS"], "ids": ["ifrs-full_NoncurrentPortionOfNoncurrentBondsIssued",
                                "dart_BondsIssued"], "nm": ["사채"]},
    "장기차입금": {"sj": ["BS"], "ids": ["ifrs-full_NoncurrentPortionOfNoncurrentLoansReceived",
                                   "ifrs-full_LongtermBorrowings", "dart_LongTermBorrowings"],
              "nm": ["장기차입금"]},
}


def _rcept_int(r) -> int:
    s = str(r.get("rcept_no") or "")
    return int(s) if s.isdigit() else 0


def _ord_int(r) -> int:
    s = str(r.get("ord") or "")
    return int(s) if s.isdigit() else 10 ** 9


def resolve_concept(rows: list[dict], spec: dict) -> dict:
    """Resolve one concept. Returns a result dict (never raises)."""
    allowed, ids, nms = spec["sj"], spec["ids"], spec["nm"]
    cands = []
    for r in rows:
        if r["sj_div"] not in allowed:
            continue
        if r["account_id"] and r["account_id"] in ids:
            tier, idx = 0, ids.index(r["account_id"])
        elif r["account_nm"] in nms:
            tier, idx = 1, nms.index(r["account_nm"])
        else:
            continue
        sj_pri = allowed.index(r["sj_div"])
        # deterministic: id-match first, sj priority, id/nm priority, latest rcept, smallest ord
        cands.append(((tier, sj_pri, idx, -_rcept_int(r), _ord_int(r)), r))
    if not cands:
        in_excluded = any(
            r["sj_div"] in EXCLUDED_SJ and
            ((r["account_id"] and r["account_id"] in ids) or r["account_nm"] in nms)
            for r in rows)
        return {"value": None, "match": "MISSING",
                "reason": "invalid_statement_section" if in_excluded else "missing_account",
                "account_id": "", "account_nm": "", "sj_div": "", "rcept_no": "", "alternatives": 0}
    cands.sort(key=lambda c: c[0])
    best = cands[0][1]
    return {"value": best["amount"], "match": ("account_id" if cands[0][0][0] == 0 else "account_nm"),
            "reason": "", "account_id": best["account_id"], "account_nm": best["account_nm"],
            "sj_div": best["sj_div"], "rcept_no": best["rcept_no"], "alternatives": len(cands) - 1}


def resolve_all(rows: list[dict]) -> dict:
    """Resolve every base concept for one company's CFS rows."""
    return {name: resolve_concept(rows, spec) for name, spec in CONCEPTS.items()}


def resolve_borrowings(rows: list[dict]) -> dict:
    """이자부 차입금 = 매핑된 구성요소 합. 하나도 못 잡으면 mapping_not_confident."""
    comps, total, found = {}, Decimal(0), False
    for name, spec in BORROWING_COMPONENTS.items():
        res = resolve_concept(rows, spec)
        comps[name] = res
        if res["match"] != "MISSING" and res["value"] is not None:
            total += res["value"]
            found = True
    if not found:
        return {"value": None, "match": "MISSING", "reason": "mapping_not_confident",
                "components": comps}
    return {"value": total, "match": "aggregate", "reason": "", "components": comps}


def dedup_events(rows: list[dict]) -> list[dict]:
    """Concept resolutions that had >1 candidate (for the dedup log)."""
    events = []
    specs = dict(CONCEPTS)
    specs.update(BORROWING_COMPONENTS)
    for name, spec in specs.items():
        res = resolve_concept(rows, spec)
        if res.get("alternatives", 0) > 0:
            events.append({
                "concept": name, "chosen_account_id": res["account_id"],
                "chosen_account_nm": res["account_nm"], "chosen_sj": res["sj_div"],
                "chosen_rcept_no": res["rcept_no"], "dropped_alternatives": res["alternatives"],
                "rule": "tier(account_id>account_nm) > sj우선 > id/nm우선순위 > 최신 rcept_no > 최소 ord",
            })
    return events
