"""Loop 15: 절대판정(red flag) 레이어 테스트.

실제 config(settings.yaml red_flag) + 합성 ratio row로 6종 flag 판정을 검증한다.
red flag는 상대판정과 독립이며, 임계값·연산자는 전부 config에서 온다(코드 하드코딩 없음).
"""
from decimal import Decimal

from src import config, red_flags

SET = config.load_settings()


def _rr(ratio, *, corp="T", ratio_value=None, num=None, den=None, computable=True):
    return {"corp_code": corp, "ratio": ratio, "ratio_value": ratio_value,
            "numerator_value": num, "denominator_value": den, "computable": computable}


def _verdict(rows, ratio, *, t_rows=None):
    a = red_flags.assess(rows, "T", t_rows or [], SET)
    return red_flags.ratio_verdict(a, ratio)["status"], a


def test_current_ratio_below_1_is_warning():
    status, a = _verdict([_rr("유동비율", ratio_value=Decimal("0.8"))], "유동비율")
    assert status == "경고" and a["any_triggered"]


def test_current_ratio_ok_is_normal():
    status, _ = _verdict([_rr("유동비율", ratio_value=Decimal("1.5"))], "유동비율")
    assert status == "정상"


def test_negative_working_capital_is_warning():
    # 운전자본 = 유동자산 − 유동부채 = numerator_value < 0
    status, _ = _verdict([_rr("운전자본비율", ratio_value=Decimal("-0.1"),
                              num=Decimal("-500"), den=Decimal("5000"))], "운전자본비율")
    assert status == "경고"


def test_negative_equity_is_warning_even_when_ratio_not_computable():
    # 자본총계<0 → 부채비율 분모≤0으로 NOT_COMPUTABLE이지만 denominator_value로 자본잠식 감지
    status, _ = _verdict([_rr("부채비율", ratio_value=None, num=Decimal("100"),
                              den=Decimal("-20"), computable=False)], "부채비율")
    assert status == "경고"


def test_high_debt_ratio_is_caution():
    status, _ = _verdict([_rr("부채비율", ratio_value=Decimal("5.0"),
                              num=Decimal("500"), den=Decimal("100"))], "부채비율")
    assert status == "주의"


def test_moderate_debt_ratio_is_normal():
    status, _ = _verdict([_rr("부채비율", ratio_value=Decimal("1.5"),
                              num=Decimal("150"), den=Decimal("100"))], "부채비율")
    assert status == "정상"


def test_interest_coverage_below_1_is_warning():
    status, _ = _verdict([_rr("이자보상배율", ratio_value=Decimal("0.5"))], "이자보상배율")
    assert status == "경고"


def test_interest_coverage_not_computable_is_na():
    status, _ = _verdict([_rr("이자보상배율", ratio_value=None, computable=False)], "이자보상배율")
    assert status == "해당없음"


def test_cash_profit_divergence_is_caution():
    rows = [_rr("순이익률", ratio_value=Decimal("0.05"), num=Decimal("300"), den=Decimal("6000"))]
    t_rows = [{"sj_div": "CF", "account_id": "ifrs-full_CashFlowsFromUsedInOperatingActivities",
               "account_nm": "영업활동현금흐름", "amount": Decimal("-100")}]
    status, _ = _verdict(rows, "순이익률", t_rows=t_rows)
    assert status == "주의"


def test_cash_profit_no_divergence_when_ocf_positive():
    rows = [_rr("순이익률", ratio_value=Decimal("0.05"), num=Decimal("300"), den=Decimal("6000"))]
    t_rows = [{"sj_div": "CF", "account_id": "ifrs-full_CashFlowsFromUsedInOperatingActivities",
               "account_nm": "영업활동현금흐름", "amount": Decimal("100")}]
    status, _ = _verdict(rows, "순이익률", t_rows=t_rows)
    assert status == "정상"


def test_ratio_without_linked_flag_is_na():
    status, _ = _verdict([_rr("영업이익률", ratio_value=Decimal("0.1"))], "영업이익률")
    assert status == "해당없음"


def test_taeyoung_like_current_and_working_capital_both_warn():
    """태영 케이스: 유동비율<1 + 운전자본 음수가 동시에 절대판정 '경고'로 잡힌다."""
    rows = [_rr("유동비율", ratio_value=Decimal("0.7")),
            _rr("운전자본비율", ratio_value=Decimal("-0.2"), num=Decimal("-800"), den=Decimal("4000"))]
    a = red_flags.assess(rows, "T", [], SET)
    assert red_flags.ratio_verdict(a, "유동비율")["status"] == "경고"
    assert red_flags.ratio_verdict(a, "운전자본비율")["status"] == "경고"
    assert sum(1 for f in a["flags"] if f["triggered"]) >= 2


def test_ocf_guard_interest_paid_is_not_operating_cash_flow():
    """CF 이자지급(nm '이자의 지급')만 있고 영업활동현금흐름 총계가 없으면 OCF=None →
    이익-현금 괴리 flag는 해당없음(조용히 정상 처리하지 않음)."""
    rows = [_rr("순이익률", ratio_value=Decimal("0.05"), num=Decimal("300"), den=Decimal("6000"))]
    t_rows = [{"sj_div": "CF", "account_id": "dart_InterestPaidClassifiedAsOperatingActivities",
               "account_nm": "이자의 지급", "amount": Decimal("-50")}]
    assert red_flags.operating_cash_flow(t_rows) is None
    status, _ = _verdict(rows, "순이익률", t_rows=t_rows)
    assert status == "해당없음"


def test_not_evaluated_default_is_na_verdict_helper():
    """assess를 돌린 뒤 링크 flag 없는 비율은 해당없음. (미평가는 비율시트 렌더 단계 구분.)"""
    a = red_flags.assess([_rr("총자산회전율", ratio_value=Decimal("1.2"))], "T", [], SET)
    assert red_flags.ratio_verdict(a, "총자산회전율")["status"] == "해당없음"


def test_no_hardcoded_thresholds_all_from_config():
    """config red_flag가 비면 어떤 flag도 트리거되지 않는다(임계값이 코드에 없음을 방증)."""
    empty = dict(SET)
    empty["red_flag"] = {"enabled": True, "flags": []}
    a = red_flags.assess([_rr("유동비율", ratio_value=Decimal("0.1"))], "T", [], empty)
    assert not a["any_triggered"] and a["flags"] == []
