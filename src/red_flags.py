"""Ralph Loop 15: 절대 red-flag 레이어(절대판정) — 상대판정과 병렬.

회사·산업 무관한 절대 기준선을 **config(settings.red_flag)에서만** 조달해 target 값에 적용한다.
상대판정(compare.py)의 label·값·통계를 **읽기만** 하고 절대 바꾸지 않는다(INV-7: 계산/표시 분리).

red flag는 "위험 확정"이 아니라 **검토 경고 / 점검 신호**다(INV-8, references/safety-rules).
못 뽑는 값(계정 미발견 등)은 조용히 무시하지 않고 '해당없음'으로 표기한다(INV-5: 은폐 금지).

산출:
  assess(...) -> {
    "flags":   [ {key, linked_ratio, severity, message, evaluable, triggered, observed, status}, ... ],
    "verdict": { ratio_name: {status, message} },   # 비율별 절대판정(가장 심각한 flag)
    "op_cash_flow": float|None, "net_income": float|None, "any_triggered": bool }
"""
from __future__ import annotations

SEVERITY_RANK = {"주의": 1, "경고": 2}   # 경고 > 주의
STATUS_NORMAL = "정상"
STATUS_NA = "해당없음"

# 영업활동현금흐름 총계(sj=CF) strict 태그 — red flag '이익-현금 괴리' 전용.
# 부분합/구성행이 아니라 총계만. 못 찾으면 None → 해당 flag는 '해당없음'.
_OCF_IDS = ("ifrs-full_CashFlowsFromUsedInOperatingActivities",)
_OCF_NMS = ("영업활동현금흐름", "영업활동으로 인한 현금흐름", "영업활동 현금흐름")


def _to_float(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return f


def operating_cash_flow(t_rows: list[dict]):
    """target CFS의 영업활동현금흐름 총계. id 일치 우선, 없으면 정확 nm 일치. 못 찾으면 None."""
    nm_hit = None
    for r in t_rows:
        if r.get("sj_div") != "CF":
            continue
        aid = r.get("account_id") or ""
        nm = r.get("account_nm") or ""
        if aid in _OCF_IDS:
            v = _to_float(r.get("amount"))
            if v is not None:
                return v
        elif nm in _OCF_NMS and nm_hit is None:
            nm_hit = _to_float(r.get("amount"))
    return nm_hit


def _target_row_index(ratio_rows_all: list[dict], target_corp_code: str) -> dict:
    return {r["ratio"]: r for r in ratio_rows_all if r["corp_code"] == target_corp_code}


def _observed(flag: dict, row: dict | None, *, op_cash_flow, net_income):
    """flag 판단 관측값. 얻을 수 없으면 None(=평가 불가). 특수 flag는 (op_cash_flow) 반환."""
    metric = flag.get("metric")
    if metric == "op_cash_flow_vs_net_income":
        return op_cash_flow
    if row is None:
        return None
    if metric == "ratio_value":
        return _to_float(row.get("ratio_value")) if row.get("computable") else None
    if metric == "numerator_value":
        return _to_float(row.get("numerator_value"))
    if metric == "denominator_value":
        return _to_float(row.get("denominator_value"))
    return None


def _evaluate(flag: dict, row: dict | None, *, op_cash_flow, net_income):
    """(evaluable, triggered, observed). 임계값·연산자는 전부 config에서."""
    op = flag.get("op")
    metric = flag.get("metric")
    if op == "special" and metric == "op_cash_flow_vs_net_income":
        if op_cash_flow is None or net_income is None:
            return False, False, None
        return True, (op_cash_flow < 0 and net_income > 0), op_cash_flow
    observed = _observed(flag, row, op_cash_flow=op_cash_flow, net_income=net_income)
    thr = flag.get("threshold")
    if observed is None or thr is None:
        return False, False, observed
    thrf = float(thr)
    if op == "<":
        return True, observed < thrf, observed
    if op == ">":
        return True, observed > thrf, observed
    return False, False, observed   # 알 수 없는 연산자 → 평가 불가(조용히 통과 금지)


def _rank(res: dict) -> int:
    if res["triggered"]:
        return 10 + SEVERITY_RANK.get(res["severity"], 0)
    if res["status"] == STATUS_NORMAL:
        return 5
    return 0   # 해당없음


def assess(ratio_rows_all: list[dict], target_corp_code: str, t_rows: list[dict], settings: dict) -> dict:
    cfg = settings.get("red_flag") or {}
    flags_cfg = cfg.get("flags") or []
    enabled = bool(cfg.get("enabled", True))

    idx = _target_row_index(ratio_rows_all, target_corp_code)
    ocf = operating_cash_flow(t_rows)
    ni_row = idx.get("순이익률")
    net_income = _to_float(ni_row.get("numerator_value")) if ni_row else None

    results = []
    if enabled:
        for f in flags_cfg:
            row = idx.get(f.get("linked_ratio"))
            evaluable, triggered, observed = _evaluate(f, row, op_cash_flow=ocf, net_income=net_income)
            status = f.get("severity") if triggered else (STATUS_NORMAL if evaluable else STATUS_NA)
            results.append({
                "key": f.get("key"), "linked_ratio": f.get("linked_ratio"),
                "severity": f.get("severity"), "message": f.get("message"),
                "op": f.get("op"), "threshold": f.get("threshold"), "metric": f.get("metric"),
                "evaluable": evaluable, "triggered": triggered, "observed": observed,
                "status": status,
            })

    # 비율별 절대판정: 링크된 flag 중 가장 심각한 것(triggered severity > 정상 > 해당없음)
    by_ratio: dict[str, dict] = {}
    for res in results:
        rn = res["linked_ratio"]
        if rn not in by_ratio or _rank(res) > _rank(by_ratio[rn]):
            by_ratio[rn] = res
    verdict = {}
    for rn, res in by_ratio.items():
        if res["triggered"]:
            verdict[rn] = {"status": res["severity"], "message": res["message"]}
        elif res["status"] == STATUS_NORMAL:
            verdict[rn] = {"status": STATUS_NORMAL, "message": ""}
        else:
            verdict[rn] = {"status": STATUS_NA, "message": ""}

    return {"flags": results, "verdict": verdict, "op_cash_flow": ocf, "net_income": net_income,
            "any_triggered": any(r["triggered"] for r in results)}


def ratio_verdict(assessment: dict, ratio_name: str) -> dict:
    """비율 시트 '절대판정' 컬럼 값. 링크된 flag가 없는 비율은 '해당없음'."""
    return assessment["verdict"].get(ratio_name) or {"status": STATUS_NA, "message": ""}
