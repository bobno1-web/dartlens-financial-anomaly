"""Practical tests for Loop 3 target-vs-benchmark comparison + labels. Not exhaustive."""
from decimal import Decimal

from src import benchmarks, compare


def _rr(corp, ratio, value):
    return {"corp_code": corp, "corp_name": corp, "is_target": "peer", "ratio": ratio,
            "group": "수익성", "formula": "f",
            "ratio_value": (Decimal(str(value)) if value is not None else None),
            "computable": True, "reason": "", "numerator_src": "n", "denominator_src": "d",
            "numerator_value": None, "denominator_value": None}


def _assess(values, cfs_success=None):
    rows = [_rr(f"P{i}", "r", v) for i, v in enumerate(values)]
    return benchmarks.assess_ratio("r", rows, "T", min_peers=5,
                                   cfs_success=(cfs_success or len(values)),
                                   winsor_lower=5, winsor_upper=95)


def _cmp(target_value, values, *, computable=True):
    a = _assess(values)
    return compare.compare("r", "수익성", target_value, computable, "", a,
                           min_peers=5, iqr_fence_k=1.5)


def test_label_high():
    r = _cmp(0.50, [0.10, 0.11, 0.12, 0.13, 0.14, 0.15])
    assert r["label"] == "HIGH"
    assert r["reason"] and "높은" in r["reason"]


def test_label_low():
    r = _cmp(-1.0, [0.10, 0.11, 0.12, 0.13, 0.14, 0.15])
    assert r["label"] == "LOW"


def test_label_normal():
    r = _cmp(0.125, [0.10, 0.11, 0.12, 0.13, 0.14, 0.15])
    assert r["label"] == "NORMAL"


def test_label_insufficient_peers():
    r = _cmp(0.5, [0.10, 0.11, 0.12])  # n=3 < min_peers=5
    assert r["label"] == "INSUFFICIENT_PEERS"


def test_label_not_computable():
    r = _cmp(None, [0.10, 0.11, 0.12, 0.13, 0.14, 0.15], computable=False)
    assert r["label"] == "NOT_COMPUTABLE"


def test_label_insufficient_variance():
    r = _cmp(0.5, [0.20, 0.20, 0.20, 0.20, 0.20, 0.20])  # iqr=0
    assert r["label"] == "INSUFFICIENT_VARIANCE"


def test_deviation_rate_median_near_zero():
    dev, reason = compare.deviation_rate(0.5, 0.0)
    assert dev is None and reason == "median_near_zero"


def test_robust_z_zero_mad_is_none():
    assert compare.robust_z(0.5, 0.1, 0.0) is None


def test_audit_comment_has_no_good_bad_words():
    for label in ("HIGH", "LOW", "NORMAL"):
        c = compare.audit_comment("수익성", label)
        assert not any(w in c for w in ("좋음", "나쁨", "우수", "부실", "부정 의심", "위험 확정"))


def test_high_low_mean_relative_position_not_good_bad():
    # HIGH/LOW 라벨이 '산업 대비' 표현을 쓰는지(좋음/나쁨 아님)
    assert "산업 대비" in compare.REASON_BY_LABEL["HIGH"]
    assert compare.LABEL_KO["HIGH"] == "산업 대비 높음"
    assert compare.LABEL_KO["LOW"] == "산업 대비 낮음"


# --- Loop 3-B 표시 보정 ---
_FORBIDDEN = ("위험 없음", "문제 없음", "검토 불필요", "부정 없음", "오류 없음", "왜곡표시 없음")


def test_compare_returns_deviation_pp():
    r = _cmp(0.50, [0.10, 0.11, 0.12, 0.13, 0.14, 0.15])
    assert r["deviation_pp"] is not None      # 값 − median (표시용 %p/값 원천)


def test_interpretation_note_large_multiple():
    note = compare.interpretation_note("NORMAL", 95.0, 4.4, "STRONG")
    assert "배수차이가 크게" in note and "IQR 이상치" in note


def test_interpretation_note_weak_quality():
    note = compare.interpretation_note("NORMAL", 50.0, 0.1, "WEAK")
    assert ("peer 수" in note) or ("커버리지" in note)


def test_interpretation_note_empty_when_plain():
    assert compare.interpretation_note("NORMAL", 50.0, 0.1, "STRONG") == ""


def test_enriched_comment_high_percentile():
    c = compare.audit_comment_enriched("수익성", "NORMAL", 92.0, "STRONG")
    assert "상위권" in c


def test_normal_outputs_have_no_forbidden_phrases():
    c = compare.audit_comment_enriched("수익성", "NORMAL", 95.0, "WEAK")
    n = compare.interpretation_note("NORMAL", 95.0, 4.4, "WEAK")
    assert not any(p in (c + " " + n) for p in _FORBIDDEN)
    # NORMAL 코멘트가 '위험 없음' 식으로 오독되지 않도록 '위험 부재' 표현 사용
    assert "위험 없음" not in compare.audit_comment("수익성", "NORMAL")
