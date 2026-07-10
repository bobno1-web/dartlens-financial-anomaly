"""Ralph Loop 5: multi-industry MVP runner.

기존 분석 엔진(pipeline.build_dataset, _compute_benchmarks, _excluded_summary; excel_report
빌더)을 **변경 없이 호출**해 여러 target을 통제된 방식으로 실행한다. 삼성전자 2025 전용
tripwire(60/51/9/780)는 사용하지 않고, 각 target의 실제 count를 그대로 기록한다(억지로 맞추지
않음, 실패는 fail_reason으로 남김). API key는 출력하지 않는다. 기존 output은 덮어쓰지 않고
target 식별 파일명으로 새 timestamp 생성.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime

from . import config
from . import excel_report as xr
from . import red_flags
from .dart_client import DartError, StopConditionError
from .pipeline import _compute_benchmarks, _excluded_summary, build_dataset
from .sparse_peer_comparison import build_sparse_peer_comparison

# 실행 대상 리스트(회사별 결과 분기 하드코딩이 아니라 단순 '실행 목록'이다).
DEFAULT_TARGETS = [
    {"name": "삼성전자", "stock": "005930", "industry_hint": "전자·반도체(baseline)"},
    {"name": "현대자동차", "stock": "005380", "industry_hint": "자동차 제조"},
    {"name": "CJ제일제당", "stock": "097950", "industry_hint": "식품 제조"},
]
BACKUP_TARGETS = [
    {"name": "대한항공", "stock": "003490", "industry_hint": "항공 운송"},
    {"name": "한화솔루션", "stock": "009830", "industry_hint": "화학·에너지 소재"},
]

SUMMARY_COLUMNS = [
    ("target_name", "회사"), ("stock_code", "종목코드"), ("bsns_year", "사업연도"),
    ("industry_code", "업종코드"), ("effective_prefix", "유효prefix"),
    ("peer_candidates", "peer후보"), ("cfs_success", "CFS성공"), ("cfs_failure", "CFS실패"),
    ("ratio_total", "비율총계"), ("ratio_computable", "계산가능"), ("ratio_not_computable", "계산불가"),
    ("label_high", "HIGH"), ("label_low", "LOW"), ("label_normal", "NORMAL"),
    ("label_insufficient", "INSUFFICIENT"),
    ("benchmark_quality_strong", "quality_STRONG"), ("benchmark_quality_weak", "quality_WEAK"),
    ("benchmark_quality_limited", "quality_LIMITED"),
    ("sparse_peer_comparison_available", "sparse비교"), ("sparse_peer_ratio_count", "sparse비율수"),
    ("sparse_peer_company_count_min", "sparse_peer_min"), ("sparse_peer_company_count_max", "sparse_peer_max"),
    ("sparse_peer_note", "sparse비고"),
    ("red_flag_count", "red_flag수"), ("red_flags", "red_flag내역"),
    ("final_report_path", "최종리포트경로"), ("debug_report_path", "debug경로"),
    ("status", "status"), ("fail_reason", "실패사유"), ("notes", "비고"),
]


def safe_filename(name: str) -> str:
    """파일명에 안전한 target 식별자. '(주)'·공백·금지문자 제거."""
    s = (name or "target").strip().replace("(주)", "").replace("（주）", "")
    s = re.sub(r'[\\/:*?"<>|]+', "_", s)   # 파일시스템 금지문자
    s = re.sub(r"\s+", "", s)
    return s or "target"


def _label_counts(comparison_rows) -> dict:
    c = {"HIGH": 0, "LOW": 0, "NORMAL": 0, "INSUFFICIENT_PEERS": 0,
         "INSUFFICIENT_VARIANCE": 0, "NOT_COMPUTABLE": 0}
    for r in comparison_rows:
        c[r["label"]] = c.get(r["label"], 0) + 1
    return c


def _quality_counts(comparison_rows) -> dict:
    q = {"STRONG": 0, "WEAK": 0, "LIMITED": 0, "NOT_AVAILABLE": 0}
    for r in comparison_rows:
        q[r["benchmark_quality"]] = q.get(r["benchmark_quality"], 0) + 1
    return q


def _blank_row(stock_code, bsns_year, industry_hint) -> dict:
    return {"target_name": None, "stock_code": str(stock_code), "bsns_year": str(bsns_year),
            "industry_hint": industry_hint, "industry_code": None, "effective_prefix": None,
            "peer_candidates": None, "cfs_success": None, "cfs_failure": None,
            "ratio_total": None, "ratio_computable": None, "ratio_not_computable": None,
            "label_high": None, "label_low": None, "label_normal": None, "label_insufficient": None,
            "label_not_computable": None,
            "benchmark_quality_strong": None, "benchmark_quality_weak": None,
            "benchmark_quality_limited": None, "benchmark_quality_not_available": None,
            "sparse_peer_comparison_available": None, "sparse_peer_ratio_count": None,
            "sparse_peer_company_count_min": None, "sparse_peer_company_count_max": None,
            "sparse_peer_note": "",
            "red_flag_count": None, "red_flags": "",
            "final_report_path": None, "debug_report_path": None,
            "status": None, "fail_reason": "", "notes": ""}


def run_target(stock_code, bsns_year, settings, paths, api_key, *, industry_hint="") -> dict:
    """단일 target 실행. 예외는 잡아 FAIL로 기록(조용히 삼키지 않고 reason 남김)."""
    row = _blank_row(stock_code, bsns_year, industry_hint)

    try:
        ds = build_dataset(stock_code, bsns_year, settings, paths, api_key)
    except (StopConditionError, DartError) as e:
        row["status"] = "FAIL"
        row["fail_reason"] = f"수집/데이터 실패: {e}"
        return row
    except Exception as e:  # noqa: BLE001 — 다음 target로 진행하되 사유 기록(조용한 성공처리 금지)
        row["status"] = "FAIL"
        row["fail_reason"] = f"예외: {type(e).__name__}: {e}"
        return row

    target = ds["target"]
    row["target_name"] = target.get("corp_name")
    row["industry_code"] = target.get("induty_code")
    row["effective_prefix"] = target.get("effective_prefix")
    row["peer_candidates"] = len(ds["peers"])
    row["cfs_success"] = ds["p_success"]
    row["cfs_failure"] = ds["p_fail"]

    ratio_rows_all = ds["ratio_rows_all"]
    target_cc = target["corp_code"]
    min_peers = int(settings.get("min_peers", 5))
    anomaly = settings.get("anomaly", {}) or {}
    iqr_k = float(anomaly.get("iqr_fence_k", 1.5))
    wl = float(anomaly.get("winsor_lower_pct", 5))
    wu = float(anomaly.get("winsor_upper_pct", 95))

    try:
        comparison_rows, pool_details = _compute_benchmarks(
            ds, ratio_rows_all, target_cc, min_peers=min_peers, iqr_k=iqr_k, wl=wl, wu=wu)
        excluded_summary = _excluded_summary(comparison_rows, ds, pool_details)
        # Loop 6: sparse(계산가능 peer<min_peers) 비율의 참고 직접 비교(통계 판정 불변).
        sparse_rows = build_sparse_peer_comparison(
            comparison_rows, pool_details, min_peers=min_peers,
            target_name=target.get("corp_name") or "대상회사")
    except Exception as e:  # noqa: BLE001
        row["status"] = "FAIL"
        row["fail_reason"] = f"benchmark 계산 실패: {type(e).__name__}: {e}"
        return row

    # Loop 15: 절대판정(red flag) 병렬 레이어. comparison_rows(상대판정)는 읽기만 하고 변경하지 않는다(INV-7).
    rf_assessment = red_flags.assess(ratio_rows_all, target_cc, ds["t_rows"], settings)
    for crow in comparison_rows:
        crow["abs_verdict"] = red_flags.ratio_verdict(rf_assessment, crow["ratio"])

    lc = _label_counts(comparison_rows)
    qc = _quality_counts(comparison_rows)
    row["ratio_total"] = len(comparison_rows)
    row["ratio_computable"] = sum(1 for r in comparison_rows if r["label"] != "NOT_COMPUTABLE")
    row["ratio_not_computable"] = row["ratio_total"] - row["ratio_computable"]
    row["label_high"], row["label_low"], row["label_normal"] = lc["HIGH"], lc["LOW"], lc["NORMAL"]
    row["label_insufficient"] = lc["INSUFFICIENT_PEERS"] + lc["INSUFFICIENT_VARIANCE"]
    row["label_not_computable"] = lc["NOT_COMPUTABLE"]
    row["benchmark_quality_strong"] = qc["STRONG"]
    row["benchmark_quality_weak"] = qc["WEAK"]
    row["benchmark_quality_limited"] = qc["LIMITED"]
    row["benchmark_quality_not_available"] = qc["NOT_AVAILABLE"]

    # Loop 6: sparse peer 직접 비교 요약(통계 판정 아님, 참고 비교)
    row["sparse_peer_comparison_available"] = "Y" if sparse_rows else "N"
    row["sparse_peer_ratio_count"] = len(sparse_rows)
    if sparse_rows:
        counts = [s["peer_count"] for s in sparse_rows]
        row["sparse_peer_company_count_min"] = min(counts)
        row["sparse_peer_company_count_max"] = max(counts)
        row["sparse_peer_note"] = (f"{len(sparse_rows)}개 비율에서 계산가능 peer<{min_peers} "
                                   f"참고 직접비교 제공(HIGH/LOW/NORMAL 통계 판정 보류)")
    else:
        row["sparse_peer_company_count_min"] = ""
        row["sparse_peer_company_count_max"] = ""
        row["sparse_peer_note"] = "sparse 비율 없음(전 비율 benchmark 성립)"

    # Loop 15: 절대판정(red flag) 요약 — 트리거·평가불가를 summary에 표면화(은폐 금지).
    _trig = [f for f in rf_assessment["flags"] if f.get("triggered")]
    _na = [f for f in rf_assessment["flags"] if f.get("status") == "해당없음"]
    row["red_flag_count"] = len(_trig)
    _base = "; ".join(f"{f['message']}({f['severity']})" for f in _trig) if _trig else "없음"
    row["red_flags"] = _base + (f" (평가불가 {len(_na)}종)" if _na else "")

    # --- Excel (target 식별 파일명, 기존 파일 미덮어쓰기: _atomic_new_path가 clobber 거부) ---
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = safe_filename(target.get("corp_name") or stock_code)
        fmeta = {**ds["meta"], "iqr_fence_k": iqr_k, "min_peers": min_peers}
        final_path = xr.build_final_report_workbook(
            paths["output"] / f"{safe}_산업대비_이상징후_리포트_{bsns_year}_{ts}.xlsx",
            target=target, target_cfs_rows=ds["t_rows"], peers=ds["peers"], peer_rows=ds["peer_rows"],
            comparison_rows=comparison_rows, excluded_summary=excluded_summary, meta=fmeta,
            sparse_comparison=sparse_rows, red_flag_assessment=rf_assessment)
        dbg_path = xr.build_benchmark_debug_workbook(
            paths["output"] / f"benchmark_debug_{safe}_{bsns_year}_{ts}.xlsx",
            target=target, comparison_rows=comparison_rows, pool_details=pool_details,
            ratio_rows_all=ratio_rows_all, target_trace=ds["target_trace"], meta=fmeta,
            red_flag_assessment=rf_assessment)
        row["final_report_path"] = str(final_path)
        row["debug_report_path"] = str(dbg_path)
    except Exception as e:  # noqa: BLE001
        row["status"] = "FAIL"
        row["fail_reason"] = f"Excel 생성 실패: {type(e).__name__}: {e}"
        return row

    # --- status 판정 (억지로 좋게 맞추지 않음) ---
    warnings = []
    if row["peer_candidates"] < min_peers:
        warnings.append(f"peer 후보 {row['peer_candidates']} < min_peers {min_peers}")
    if row["ratio_computable"] < 10:
        warnings.append(f"계산 가능 비율 {row['ratio_computable']}/15 (<10)")
    if row["label_insufficient"] >= 5:
        warnings.append(f"INSUFFICIENT 라벨 {row['label_insufficient']}개")
    if (qc["LIMITED"] + qc["NOT_AVAILABLE"]) >= 8:
        warnings.append("benchmark_quality 대부분 제한적(LIMITED/NOT_AVAILABLE)")
    row["notes"] = "; ".join(warnings)
    row["status"] = "PASS_WITH_WARNINGS" if warnings else "PASS"
    return row


def write_summary(rows, output_dir, bsns_year) -> "os.PathLike":
    import xlsxwriter
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"multi_industry_mvp_summary_{bsns_year}_{ts}.xlsx"
    tmp = path.with_suffix(".xlsx.tmp")
    wb = xlsxwriter.Workbook(str(tmp))
    ws = wb.add_worksheet("multi_industry_summary")
    bold = wb.add_format({"bold": True, "bg_color": "#DDDDDD", "border": 1})
    ws.set_column(0, len(SUMMARY_COLUMNS) - 1, 16)
    for c, (_k, h) in enumerate(SUMMARY_COLUMNS):
        ws.write(0, c, h, bold)
    for r, row in enumerate(rows, start=1):
        for c, (k, _h) in enumerate(SUMMARY_COLUMNS):
            v = row.get(k)
            ws.write(r, c, "" if v is None else v)
    wb.close()
    os.replace(tmp, path)
    return path


def main(argv=None) -> int:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Ralph Loop 5: multi-industry MVP runner")
    ap.add_argument("--set", dest="which", default="primary", choices=["primary", "backup", "all"])
    args = ap.parse_args(argv)

    settings = config.load_settings()
    year = settings.get("bsns_year", 2025)
    try:
        api_key = config.get_api_key()
    except config.ConfigError as e:
        print(f"STOP: {e}", flush=True)
        return 2
    paths = config.resolve_paths(settings)

    targets = {"primary": DEFAULT_TARGETS, "backup": BACKUP_TARGETS,
               "all": DEFAULT_TARGETS + BACKUP_TARGETS}[args.which]

    rows = []
    for t in targets:
        print(f"\n=== {t['name']} ({t['stock']}) {year} — {t['industry_hint']} ===", flush=True)
        row = run_target(t["stock"], year, settings, paths, api_key, industry_hint=t["industry_hint"])
        rows.append(row)
        print("    status=%s | peer=%s cfs=%s/%s | computable=%s/%s | "
              "labels H/L/N/INS=%s/%s/%s/%s | quality S/W/L=%s/%s/%s | %s"
              % (row["status"], row["peer_candidates"], row["cfs_success"], row["cfs_failure"],
                 row["ratio_computable"], row["ratio_total"], row["label_high"], row["label_low"],
                 row["label_normal"], row["label_insufficient"], row["benchmark_quality_strong"],
                 row["benchmark_quality_weak"], row["benchmark_quality_limited"],
                 row["fail_reason"] or row["notes"]), flush=True)

    summary_path = write_summary(rows, paths["output"], year)
    print(f"\nSUMMARY_XLSX: {summary_path}", flush=True)
    print("SUMMARY_JSON:" + json.dumps(rows, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
