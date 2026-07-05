"""Practical tests for Loop 3 benchmark computation (pool, stats, quality). Not exhaustive."""
from decimal import Decimal

from src import benchmarks


def _rr(corp, ratio, value, *, computable=True, reason="", is_target="peer"):
    return {"corp_code": corp, "corp_name": corp, "is_target": is_target, "ratio": ratio,
            "group": "수익성", "formula": "f",
            "ratio_value": (Decimal(str(value)) if value is not None else None),
            "computable": computable, "reason": reason,
            "numerator_src": "n", "denominator_src": "d",
            "numerator_value": None, "denominator_value": None}


def test_percentile_linear_interpolation():
    sv = [1.0, 2.0, 3.0, 4.0]
    assert abs(benchmarks._percentile(sv, 0.25) - 1.75) < 1e-9
    assert abs(benchmarks._percentile(sv, 0.75) - 3.25) < 1e-9
    assert abs(benchmarks._median(sv) - 2.5) < 1e-9


def test_compute_stats_basic():
    st = benchmarks.compute_stats([1, 2, 3, 4, 5], winsor_lower=5, winsor_upper=95)
    assert st["n_companies"] == 5
    assert st["median"] == 3
    assert st["p25"] == 2 and st["p75"] == 4 and st["iqr"] == 2
    assert st["min"] == 1 and st["max"] == 5


def test_winsorized_mean_is_reference_and_robust():
    st = benchmarks.compute_stats([1, 2, 3, 4, 100], winsor_lower=5, winsor_upper=95)
    # 100(이상치)에 평균은 끌려가지만 winsorized 평균은 덜 끌린다(참고값)
    assert st["winsorized_mean"] < st["mean"]


def test_build_pool_excludes_target_and_not_computable():
    rows = [
        _rr("T", "영업이익률", 0.13, is_target="대상"),
        _rr("P1", "영업이익률", 0.10),
        _rr("P2", "영업이익률", 0.12),
        _rr("P3", "영업이익률", None, computable=False, reason="missing_account"),
    ]
    inc, exc = benchmarks.build_pool("영업이익률", rows, "T")
    assert {x["corp_code"] for x in inc} == {"P1", "P2"}
    assert any(e["is_target"] and e["reason"] == benchmarks.POOL_EXCLUDE_TARGET for e in exc)
    assert any(e["corp_code"] == "P3" and e["reason"] == "missing_account" for e in exc)


def test_assess_ratio_leave_one_out():
    rows = [_rr("T", "r", 9.9, is_target="대상")] + [_rr(f"P{i}", "r", 0.1 * i) for i in range(1, 7)]
    a = benchmarks.assess_ratio("r", rows, "T", min_peers=5, cfs_success=6, winsor_lower=5, winsor_upper=95)
    assert all(x["corp_code"] != "T" for x in a["included"])       # target 제외
    assert a["stats"]["n_companies"] == 6


def test_benchmark_quality_levels():
    strong = benchmarks.compute_stats([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
                                      winsor_lower=5, winsor_upper=95)
    q, _ = benchmarks.benchmark_quality(strong, min_peers=5, cfs_success=10)
    assert q == "STRONG"
    flat = benchmarks.compute_stats([0.2] * 8, winsor_lower=5, winsor_upper=95)  # iqr=0
    q2, _ = benchmarks.benchmark_quality(flat, min_peers=5, cfs_success=8)
    assert q2 == "LIMITED"
    empty = benchmarks.compute_stats([], winsor_lower=5, winsor_upper=95)
    q3, _ = benchmarks.benchmark_quality(empty, min_peers=5, cfs_success=10)
    assert q3 == "NOT_AVAILABLE"


def test_stats_no_nan_inf():
    st = benchmarks.compute_stats([0.0, 0.0, 0.0], winsor_lower=5, winsor_upper=95)
    for k in ("mean", "median", "iqr", "mad", "std"):
        v = st[k]
        assert v is None or (v == v and v not in (float("inf"), float("-inf")))
