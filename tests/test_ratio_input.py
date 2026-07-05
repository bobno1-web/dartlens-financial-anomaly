"""Practical tests for Loop 2 account resolution + ratio input. Not exhaustive."""
from decimal import Decimal

from src import accounts, ratio_input


def _row(sj, aid, nm, amt, rcept="R1", ordv="1"):
    return {"sj_div": sj, "account_id": aid, "account_nm": nm,
            "amount": (Decimal(amt) if amt is not None else None),
            "rcept_no": rcept, "ord": ordv}


def _samsung_like():
    return [
        _row("BS", "ifrs-full_Assets", "자산총계", "100"),
        _row("BS", "ifrs-full_CurrentAssets", "유동자산", "60"),
        _row("BS", "ifrs-full_Liabilities", "부채총계", "40"),
        _row("BS", "ifrs-full_CurrentLiabilities", "유동부채", "30"),
        _row("BS", "ifrs-full_Equity", "자본총계", "60"),
        _row("BS", "ifrs-full_Inventories", "재고자산", "20"),
        _row("BS", "ifrs-full_CurrentTradeReceivables", "매출채권", "15"),
        _row("BS", "ifrs-full_TradeAndOtherCurrentPayablesToTradeSuppliers", "매입채무", "10"),
        _row("BS", "-표준계정코드 미사용-", "단기차입금", "5"),       # id 없음 -> account_nm fallback
        _row("BS", "ifrs-full_CurrentPortionOfLongtermBorrowings", "유동성장기부채", "3"),
        _row("IS", "ifrs-full_Revenue", "매출액", "200"),
        _row("IS", "ifrs-full_CostOfSales", "매출원가", "150"),
        _row("IS", "dart_OperatingIncomeLoss", "영업이익", "18"),
        _row("IS", "ifrs-full_ProfitLoss", "당기순이익", "12"),
        _row("CIS", "ifrs-full_ProfitLoss", "당기순이익", "12"),     # 중복 -> dedup(IS 우선)
        _row("SCE", "ifrs-full_ProfitLoss", "당기순이익", "12"),     # SCE -> 원천 제외
    ]


def test_short_term_borrowing_uses_account_nm_fallback():
    r = accounts.resolve_concept(_samsung_like(), accounts.BORROWING_COMPONENTS["단기차입금"])
    assert r["match"] == "account_nm" and r["value"] == Decimal("5")


def test_net_income_prefers_is_not_sce():
    r = accounts.resolve_concept(_samsung_like(), accounts.CONCEPTS["당기순이익"])
    assert r["sj_div"] == "IS"          # IS 우선, SCE/CF 제외
    assert r["alternatives"] >= 1       # CIS 후보가 드롭됨(dedup 이벤트)


def test_ratio_values_and_borrowings_aggregate():
    out = ratio_input.compute_company({"corp_code": "C", "corp_name": "테스트", "is_target": "대상"},
                                      _samsung_like())
    rr = {r["ratio"]: r for r in out["ratio_rows"]}
    assert len(rr) == 15
    assert rr["부채비율"]["computable"] and abs(rr["부채비율"]["ratio_value"] - Decimal("40") / Decimal("60")) < Decimal("1e-9")
    # 차입금의존도 = (5+3)/100 = 0.08
    assert rr["차입금의존도"]["computable"] and rr["차입금의존도"]["ratio_value"] == Decimal("8") / Decimal("100")


def test_invalid_denominator_and_missing_not_computable():
    rows = [_row("BS", "ifrs-full_Assets", "자산총계", "100"),
            _row("BS", "ifrs-full_Liabilities", "부채총계", "40"),  # 분자 존재
            _row("BS", "ifrs-full_Equity", "자본총계", "0")]        # 분모=0 -> invalid_denominator
    out = ratio_input.compute_company({"corp_code": "C", "corp_name": "t", "is_target": "peer"}, rows)
    rr = {r["ratio"]: r for r in out["ratio_rows"]}
    # 부채비율 = 부채총계 / 자본총계(=0) -> invalid_denominator
    assert not rr["부채비율"]["computable"] and rr["부채비율"]["reason"] == "invalid_denominator"
    # 영업이익률: 영업이익/매출액 모두 없음 -> missing_account
    assert not rr["영업이익률"]["computable"] and rr["영업이익률"]["reason"] == "missing_account"
