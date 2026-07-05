"""Ralph Loop 3: target vs 산업 benchmark 비교 + 판정(label) + 감사 관점 코멘트.

label ∈ {NORMAL, HIGH, LOW, INSUFFICIENT_PEERS, NOT_COMPUTABLE, INSUFFICIENT_VARIANCE}.
HIGH/LOW 는 **산업 대비 높음/낮음**이며 좋음/나쁨·부정·오류가 아니다. 판정은 median/IQR
fence 기준(결정적). 모든 통계는 유한 float 또는 None(NaN/inf 미유출).
"""
from __future__ import annotations

# 라벨별 사람이 읽는 판정 사유(결정적).
REASON_BY_LABEL = {
    "HIGH": "산업 peer IQR 기준 상단 fence를 초과하여 산업 대비 높은 비율입니다.",
    "LOW": "산업 peer IQR 기준 하단 fence보다 낮아 산업 대비 낮은 비율입니다.",
    "NORMAL": "산업 peer IQR 기준 정상 범위에 있습니다.",
    "INSUFFICIENT_PEERS": "해당 비율을 계산 가능한 peer 수가 기준보다 부족합니다.",
    "NOT_COMPUTABLE": "target 또는 source 계정 부족으로 계산할 수 없습니다.",
    "INSUFFICIENT_VARIANCE": "peer 분포의 변동성이 부족하여 판정할 수 없습니다.",
}

# 감사 관점 코멘트: (그룹, 방향) 결정적 템플릿. 과장 표현 금지.
_DIRECTION_TEMPLATES = {
    "수익성": {
        "HIGH": "수익성 지표가 산업 peer 대비 상대적으로 높은 위치입니다. 일회성 손익·회계정책 차이 여부를 추가 확인할 검토 후보입니다.",
        "LOW": "수익성 지표가 산업 peer 대비 상대적으로 낮은 위치입니다. 원가구조·업황 영향 여부를 추가 확인할 검토 후보입니다.",
    },
    "안정성": {
        "HIGH": "재무구조/안정성 지표가 산업 peer 대비 상대적으로 높은 위치입니다. 자본·부채 구성의 배경을 추가 확인할 검토 후보입니다.",
        "LOW": "재무구조/안정성 지표가 산업 peer 대비 상대적으로 낮은 위치입니다. 자본·부채 구성의 배경을 추가 확인할 검토 후보입니다.",
    },
    "운전자본": {
        "HIGH": "운전자본/계정 지표가 산업 peer 대비 상대적으로 높은 위치입니다. 매출채권·재고·매입채무 인식 시점을 추가 확인할 검토 후보입니다.",
        "LOW": "운전자본/계정 지표가 산업 peer 대비 상대적으로 낮은 위치입니다. 매출채권·재고·매입채무 인식 시점을 추가 확인할 검토 후보입니다.",
    },
    "회전율": {
        "HIGH": "회전율 지표가 산업 peer 대비 상대적으로 높은 위치입니다. 매출·자산·재고 인식의 계절성·정책을 추가 확인할 검토 후보입니다.",
        "LOW": "회전율 지표가 산업 peer 대비 상대적으로 낮은 위치입니다. 매출·자산·재고 인식의 계절성·정책을 추가 확인할 검토 후보입니다.",
    },
}
_COMMENT_NORMAL = ("현재 peer universe와 IQR fence 기준상 정상 범위이며, IQR 이상치로 분류되지 않았습니다"
                   "(정상 범위가 위험 부재를 의미하지는 않습니다).")
_COMMENT_NA = {
    "INSUFFICIENT_PEERS": "계산 가능한 peer 수가 부족하여 산업 대비 위치를 판정하지 못했습니다. 추가 확인 필요.",
    "NOT_COMPUTABLE": "target 계정 부족으로 비율을 계산하지 못했습니다. 추가 확인 필요.",
    "INSUFFICIENT_VARIANCE": "peer 분포의 변동성이 부족하여 산업 대비 위치를 판정하지 못했습니다. 추가 확인 필요.",
}

# 사용자 표시용 한글 라벨.
LABEL_KO = {
    "HIGH": "산업 대비 높음", "LOW": "산업 대비 낮음", "NORMAL": "정상 범위",
    "INSUFFICIENT_PEERS": "peer 부족", "NOT_COMPUTABLE": "계산 불가",
    "INSUFFICIENT_VARIANCE": "분포 부족",
}

_MEDIAN_EPS = 1e-12  # deviation_rate 계산 시 median≈0 판단


def _finite(x):
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return f


def audit_comment(group: str, label: str) -> str:
    if label in ("HIGH", "LOW"):
        return _DIRECTION_TEMPLATES.get(group, {}).get(
            label, f"산업 peer 대비 상대적으로 {'높은' if label == 'HIGH' else '낮은'} 위치입니다. 추가 확인 필요.")
    if label == "NORMAL":
        return _COMMENT_NORMAL
    return _COMMENT_NA.get(label, "산업 대비 위치를 판정하지 못했습니다. 추가 확인 필요.")


def audit_comment_enriched(group: str, label: str, percentile, benchmark_quality: str) -> str:
    """Loop 3-B: NORMAL 코멘트에 percentile 상하위권·품질 제한 맥락을 보강(계산 불변)."""
    base = audit_comment(group, label)
    if label != "NORMAL":
        return base
    extra = []
    if percentile is not None and percentile >= 90:
        extra.append("산업 내 상대적 위치는 상위권입니다.")
    elif percentile is not None and percentile <= 10:
        extra.append("산업 내 상대적 위치는 하위권입니다.")
    if benchmark_quality in ("WEAK", "LIMITED"):
        extra.append("계산 가능 peer 수/계정 커버리지가 제한적이므로 해석에 주의가 필요합니다.")
    return base + (" " + " ".join(extra) if extra else "")


def interpretation_note(label: str, percentile, deviation_rate, benchmark_quality: str) -> str:
    """Loop 3-B 자동 해석 비고. 계산에 영향 없음(표시 전용)."""
    parts = []
    if deviation_rate is not None and abs(deviation_rate) >= 1.0:
        note = "산업 중앙값이 작아 중앙값 대비 배수차이가 크게 보일 수 있습니다."
        if label == "NORMAL":
            note += " 다만 IQR 이상치 기준은 초과하지 않았습니다."
        parts.append(note)
    if label == "NORMAL" and percentile is not None and (percentile >= 90 or percentile <= 10):
        pos = "상위권" if percentile >= 90 else "하위권"
        parts.append(f"산업 내 상대적 위치는 {pos}이나 IQR 이상치 기준은 초과하지 않았습니다.")
    if benchmark_quality in ("WEAK", "LIMITED"):
        parts.append("계산 가능 peer 수 또는 계정 커버리지 제한으로 해석에 주의가 필요합니다.")
    return " ".join(parts)


def robust_z(value: float, median: float, mad: float):
    """0.6745*(value-median)/MAD. MAD 없거나 0이면 None."""
    mad = _finite(mad)
    if mad is None or mad == 0:
        return None
    return _finite(0.6745 * (value - median) / mad)


def percentile_of(value: float, sorted_pool: list[float]):
    """pool 대비 value의 위치(0~100). pool 비면 None."""
    if not sorted_pool:
        return None
    below = sum(1 for v in sorted_pool if v <= value)
    return _finite(100.0 * below / len(sorted_pool))


def deviation_rate(value: float, median):
    """(value-median)/|median|. median 없거나 ≈0이면 (None, reason)."""
    median = _finite(median)
    if median is None:
        return None, "median_unavailable"
    if abs(median) < _MEDIAN_EPS:
        return None, "median_near_zero"
    return _finite((value - median) / abs(median)), ""


def compare(ratio_name: str, group: str, target_value, target_computable: bool,
            target_reason: str, assessed: dict, *, min_peers: int, iqr_fence_k: float) -> dict:
    """target 값을 assess_ratio 결과와 비교해 label·보조지표·사유·코멘트를 만든다.

    assessed = benchmarks.assess_ratio(...) 반환값(stats, pool_values 포함).
    """
    stats = assessed["stats"]
    pool = assessed["pool_values"]
    n = stats["n_companies"]
    tv = _finite(target_value) if target_computable else None

    # --- 결정적 라벨 순서 ---
    if not target_computable or tv is None:
        label = "NOT_COMPUTABLE"
    elif n < min_peers:
        label = "INSUFFICIENT_PEERS"
    elif stats["iqr"] is None or stats["iqr"] <= 0:
        label = "INSUFFICIENT_VARIANCE"
    else:
        hi = stats["p75"] + iqr_fence_k * stats["iqr"]
        lo = stats["p25"] - iqr_fence_k * stats["iqr"]
        if tv > hi:
            label = "HIGH"
        elif tv < lo:
            label = "LOW"
        else:
            label = "NORMAL"

    # --- 보조 지표(가능할 때만) ---
    rz = pct = dev = dev_pp = None
    dev_reason = ""
    if tv is not None and n > 0 and stats["median"] is not None:
        rz = robust_z(tv, stats["median"], stats["mad"])
        pct = percentile_of(tv, pool)
        dev, dev_reason = deviation_rate(tv, stats["median"])
        dev_pp = _finite(tv - stats["median"])  # Loop 3-B: 값−중앙값 (단위: 비율차이, 표시 시 %p/값)

    # --- fence(감사 근거 표시용) ---
    upper_fence = lower_fence = None
    if stats["iqr"] is not None and stats["p75"] is not None:
        upper_fence = _finite(stats["p75"] + iqr_fence_k * stats["iqr"])
        lower_fence = _finite(stats["p25"] - iqr_fence_k * stats["iqr"])

    return {
        "ratio": ratio_name, "group": group,
        "target_value": tv, "label": label,
        "reason": REASON_BY_LABEL[label], "audit_comment": audit_comment(group, label),
        "robust_z": rz, "percentile": pct, "deviation_rate": dev, "deviation_pp": dev_pp,
        "deviation_reason": dev_reason,
        "upper_fence": upper_fence, "lower_fence": lower_fence,
        "n_companies": n,
    }
