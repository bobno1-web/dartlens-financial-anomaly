"""Ralph Loop 3: per-ratio industry benchmark (median/IQR-centered).

각 비율마다 benchmark pool을 **계산 가능한 peer 값만**으로 구성한다. NOT_COMPUTABLE
peer와 CFS 실패 peer는 pool에 들어가지 않는다. target(삼성전자)은 leave-one-out으로
모든 비율의 benchmark 계산에서 제외한다(단 비교 대상값으로는 유지).

mean / winsorized_mean 은 참고값일 뿐, 판정은 median/IQR 기준(→ src/compare.py).
NaN/inf는 산출물에 남기지 않는다(모든 통계는 유한 float 또는 None).
"""
from __future__ import annotations

# 이 상수들은 pool 제외 사유(감사용). label 은 compare.py 소관.
POOL_EXCLUDE_TARGET = "target_leave_one_out"
POOL_EXCLUDE_NOT_COMPUTABLE = "not_computable"


def _to_float(v):
    """Decimal/숫자 → 유한 float, 아니면 None."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):  # NaN/inf 차단
        return None
    return f


def _percentile(sorted_vals: list[float], q: float) -> float:
    """선형보간 백분위(numpy 기본, type 7). sorted_vals 비어있지 않다고 가정. q∈[0,1]."""
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    idx = q * (n - 1)
    lo = int(idx)
    if lo >= n - 1:
        return sorted_vals[-1]
    frac = idx - lo
    return sorted_vals[lo] + frac * (sorted_vals[lo + 1] - sorted_vals[lo])


def _median(sorted_vals: list[float]) -> float:
    return _percentile(sorted_vals, 0.5)


def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals)


def _winsorized_mean(sorted_vals: list[float], lower_pct: float, upper_pct: float) -> float:
    lo = _percentile(sorted_vals, lower_pct / 100.0)
    hi = _percentile(sorted_vals, upper_pct / 100.0)
    clipped = [min(max(v, lo), hi) for v in sorted_vals]
    return _mean(clipped)


def _mad(sorted_vals: list[float], med: float) -> float:
    devs = sorted(abs(v - med) for v in sorted_vals)
    return _median(devs)


def _std(vals: list[float], mean: float) -> float:
    """표본 표준편차(n-1). n<2면 0.0."""
    if len(vals) < 2:
        return 0.0
    var = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
    return var ** 0.5


def build_pool(ratio_name: str, ratio_rows_all: list[dict], target_corp_code: str):
    """한 비율의 benchmark pool을 구성한다.

    Returns (included, excluded):
      included = [{corp_code, corp_name, value(float)}]   # 계산 가능 peer 값
      excluded = [{corp_code, corp_name, reason, is_target}]  # target/NOT_COMPUTABLE
    target은 leave-one-out으로 excluded(POOL_EXCLUDE_TARGET).
    """
    included, excluded = [], []
    for r in ratio_rows_all:
        if r["ratio"] != ratio_name:
            continue
        is_target = r["corp_code"] == target_corp_code
        if is_target:
            excluded.append({"corp_code": r["corp_code"], "corp_name": r["corp_name"],
                             "reason": POOL_EXCLUDE_TARGET, "is_target": True})
            continue
        val = _to_float(r["ratio_value"]) if r.get("computable") else None
        if not r.get("computable") or val is None:
            excluded.append({"corp_code": r["corp_code"], "corp_name": r["corp_name"],
                             "reason": r.get("reason") or POOL_EXCLUDE_NOT_COMPUTABLE,
                             "is_target": False})
            continue
        included.append({"corp_code": r["corp_code"], "corp_name": r["corp_name"], "value": val})
    return included, excluded


def compute_stats(values: list[float], *, winsor_lower: float, winsor_upper: float) -> dict:
    """benchmark 통계. values=유한 float 목록. 비면 전부 None(+n_companies=0)."""
    vals = [v for v in (_to_float(x) for x in values) if v is not None]
    n = len(vals)
    stats = {"n_companies": n, "mean": None, "winsorized_mean": None, "median": None,
             "p25": None, "p75": None, "iqr": None, "mad": None, "std": None,
             "min": None, "max": None}
    if n == 0:
        return stats
    sv = sorted(vals)
    med = _median(sv)
    p25 = _percentile(sv, 0.25)
    p75 = _percentile(sv, 0.75)
    mean = _mean(vals)
    stats.update({
        "mean": mean,
        "winsorized_mean": _winsorized_mean(sv, winsor_lower, winsor_upper),
        "median": med, "p25": p25, "p75": p75, "iqr": p75 - p25,
        "mad": _mad(sv, med), "std": _std(vals, mean),
        "min": sv[0], "max": sv[-1],
    })
    return stats


def benchmark_quality(stats: dict, *, min_peers: int, cfs_success: int) -> tuple[str, str]:
    """비율별 benchmark 품질 등급 + 근거(한글).

    STRONG      : n>=2*min_peers, iqr>0, coverage(=n/cfs_success)>=0.7
    LIMITED     : n>=min_peers 이지만 iqr=0(변동성 부족) 또는 coverage<0.5(mapping 부족)
    WEAK        : n>=min_peers 이지만 STRONG/LIMITED 조건 미달(표본 작음)
    NOT_AVAILABLE / (n<min_peers): 계산 불가/부족
    """
    n = stats["n_companies"]
    if n == 0 or stats["median"] is None:
        return "NOT_AVAILABLE", "계산 가능 peer 없음"
    coverage = (n / cfs_success) if cfs_success else 0.0
    iqr = stats["iqr"]
    if n < min_peers:
        # 문서 정의상 WEAK은 n>=min_peers 표본이 작은 경우. n<min_peers는 라벨상 INSUFFICIENT_PEERS이며
        # benchmark_quality는 NOT_AVAILABLE로 둔다(계산 불가/부족). 현 15개 비율은 모두 n>=min_peers라 미영향.
        return "NOT_AVAILABLE", f"계산 가능 peer {n} < min_peers {min_peers}"
    if iqr is None or iqr <= 0:
        return "LIMITED", f"n={n}이나 IQR=0(분포 변동성 부족)"
    if coverage < 0.5:
        return "LIMITED", f"n={n}이나 mapping coverage {coverage:.0%} 낮음"
    if n >= 2 * min_peers and coverage >= 0.7:
        return "STRONG", f"n={n}(>=2*min_peers), IQR>0, coverage {coverage:.0%}"
    return "WEAK", f"n={n}(min_peers는 넘으나 표본 제한적), coverage {coverage:.0%}"


def assess_ratio(ratio_name: str, ratio_rows_all: list[dict], target_corp_code: str, *,
                 min_peers: int, cfs_success: int, winsor_lower: float, winsor_upper: float) -> dict:
    """한 비율의 pool·통계·품질을 한 번에 산출(compare.py가 target 비교에 사용)."""
    included, excluded = build_pool(ratio_name, ratio_rows_all, target_corp_code)
    pool_values = sorted(x["value"] for x in included)
    stats = compute_stats(pool_values, winsor_lower=winsor_lower, winsor_upper=winsor_upper)
    quality, quality_reason = benchmark_quality(stats, min_peers=min_peers, cfs_success=cfs_success)
    return {"ratio": ratio_name, "included": included, "excluded": excluded,
            "pool_values": pool_values, "stats": stats,
            "benchmark_quality": quality, "quality_reason": quality_reason}
