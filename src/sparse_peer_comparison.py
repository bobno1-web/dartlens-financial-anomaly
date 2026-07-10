"""Ralph Loop 6: Sparse-peer 직접 비교(참고용, read-only 파생).

동종산업 상장 CFS peer 수가 min_peers 미만이라 HIGH/LOW/NORMAL 통계 판정을 **보류**한
비율에 대해, benchmark pool이 실제로 사용한 peer 회사명·값을 그대로 보여주는 '참고 비교표'를
만든다.

이 모듈은 benchmark 통계·label 판정을 **절대 변경하지 않는다**:
  - min_peers를 낮추지 않는다.
  - 2자리 업종 prefix rollup을 하지 않는다.
  - 부족한 표본으로 HIGH/LOW/NORMAL을 억지로 만들지 않는다(판정은 보류 유지).
직접 비교는 통계적 이상치(benchmark) 판정이 아니라 **참고 비교**임을 명시한다.

sparse 판정 기준:
  비율별 계산 가능 peer 수(= stats["n_companies"] = len(pool_details[i]["included"]))가
  min_peers 미만이면 sparse. 이는 compare.compare가 INSUFFICIENT_PEERS를 부여하는 조건과
  동일하다(별도 임계값을 새로 만들지 않음).

peer 회사명·값의 출처:
  pool_details[i]["included"] = leave-one-out·계산가능 peer의 {corp_code, corp_name, value}.
  즉 benchmark가 실제로 본 peer와 동일하며, 익명(Peer 1/Peer 2) 없이 실제 corp_name을 쓴다.
"""
from __future__ import annotations

# 사용자 표시 상태 문구(peer 수 구간별). 통계 판정이 아니라 '참고 비교'임을 전제한다.
STATUS_LIMITED = "분석 완료 · 표본 제한"        # 2 <= peer < min_peers
STATUS_SINGLE = "분석 완료 · 단일 peer 비교"     # peer == 1
STATUS_NONE = "비교 가능 peer 없음"             # peer == 0

# 공통 주의 문구(통계 benchmark 아님을 명시). {mp}=min_peers.
SPARSE_WARNING = (
    "동종산업 상장 CFS peer 수가 최소 benchmark 기준(min_peers={mp})에 미달하여 "
    "HIGH/LOW/NORMAL 통계 판정은 보류했습니다. 아래 값은 제한적 peer 직접 비교 참고용이며, "
    "통계적 benchmark가 아닙니다. min_peers를 낮추거나 2자리 업종 rollup을 하지 않았습니다. "
    "색상으로 좋고 나쁨을 표시하지 않습니다."
)


def _num(v):
    """Decimal/숫자 → 유한 float, 아니면 None(NaN/inf 차단)."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return f


def _sample_status(peer_count: int) -> str:
    if peer_count <= 0:
        return STATUS_NONE
    if peer_count == 1:
        return STATUS_SINGLE
    return STATUS_LIMITED


def _rank_among(target_value, peer_values):
    """target_value의 순위(내림차순, 1=최대) + 표본 총수.

    target 또는 peer가 비교 불가면 rank=None. 통계 판정이 아니라 단순 위치 참고용.
    """
    tv = _num(target_value)
    peers = [p for p in (_num(x) for x in peer_values) if p is not None]
    if tv is None or not peers:
        return None, len(peers) + (1 if tv is not None else 0)
    combined = sorted(peers + [tv], reverse=True)
    return combined.index(tv) + 1, len(combined)


def build_sparse_peer_comparison(comparison_rows, pool_details, *, min_peers=5,
                                 target_name="대상회사"):
    """sparse(계산가능 peer < min_peers) 비율의 직접 비교 row 목록.

    Args:
      comparison_rows: pipeline._compute_benchmarks 반환값(비율별 target 비교; label·target_value·group).
      pool_details:    같은 반환값(비율별 included peer·stats). comparison_rows와 비율 단위로 매칭.
      min_peers:       benchmark 최소 peer 수(config; 낮추지 않음).
      target_name:     대상 회사명(표시용).

    Returns:
      list[dict] — peer 충분(>=min_peers) 비율은 제외. 빈 list면 sparse 비율 없음.
      각 row 키:
        ratio_id, ratio_name_ko(=한글 비율명), group,
        target_company, target_value(float|None),
        peer_count(int),
        peer_company_values: [{corp_code, corp_name, value}]  # 실제 회사명·값(내림차순)
        peer_median_reference(float|None),                    # 참고용(비통계)
        target_rank_among_peers(str|None),                    # 'k/n (값 내림차순)'
        sample_status(str), comparison_note(str), basis(str),
        label(원 label 그대로), is_statistical_benchmark=False
    """
    pd_by_ratio = {pd["ratio"]: pd for pd in pool_details}
    out = []
    for c in comparison_rows:
        pd = pd_by_ratio.get(c["ratio"])
        if pd is None:
            continue
        included = pd.get("included") or []
        peer_count = len(included)
        if peer_count >= min_peers:
            continue  # benchmark 성립 → 통계 판정 유지, sparse 비교 대상 아님

        # 실제 peer 회사명·값(값 내림차순, 결정적). 익명 컬럼 없음.
        peers = sorted(
            ({"corp_code": x.get("corp_code"), "corp_name": x.get("corp_name"),
              "value": _num(x.get("value"))} for x in included),
            key=lambda d: (d["value"] is None, -(d["value"] or 0.0), d["corp_name"] or ""))

        tv = _num(c.get("target_value"))
        median_ref = _num((pd.get("stats") or {}).get("median"))
        rank, total = _rank_among(tv, [p["value"] for p in peers])
        rank_disp = f"{rank}/{total} (값 내림차순)" if rank is not None else None

        note = SPARSE_WARNING.format(mp=min_peers)
        basis = (f"계산 가능 peer {peer_count} < min_peers {min_peers}; "
                 f"benchmark 통계 판정 보류(label={c.get('label')}); "
                 f"pool=leave-one-out 계산가능 peer(min_peers 미조정·2자리 rollup 없음)")
        out.append({
            "ratio_id": c["ratio"], "ratio_name_ko": c["ratio"], "group": c.get("group", ""),
            "target_company": target_name, "target_value": tv,
            "peer_count": peer_count, "peer_company_values": peers,
            "peer_median_reference": median_ref,
            "target_rank_among_peers": rank_disp,
            "sample_status": _sample_status(peer_count),
            "comparison_note": note, "basis": basis,
            "label": c.get("label"), "is_statistical_benchmark": False,
        })
    return out
