"""Excel writers (Loop 1). Two workbooks, all user-facing text in Korean.

  - build_skeleton_workbook(): 사용자용 skeleton (02~05 시트는 비율 미계산, 안내만)
  - build_debug_workbook(): Peer CFS Debug (수집/peer universe 검증용)

Uses xlsxwriter. Filenames are timestamped; writes to a temp file then atomic
os.replace. Refuses to clobber an existing file (no --overwrite here).
"""
from __future__ import annotations

import os
import re
from decimal import Decimal
from pathlib import Path

import xlsxwriter

# Excel 시트명 금지문자: \ / ? * [ ] :  (Excel 규칙)
_SHEET_BAD = re.compile(r"[\\/?*\[\]:]")


def safe_sheet_name(prefix: str, corp_name: str, suffix: str) -> str:
    """target corp_name 기반 Excel 시트명(≤31자, 금지문자·'(주)' 제거).

    삼성전자(주) → f"{prefix}삼성전자{suffix}" (기존 하드코딩 '01_삼성전자_연결재무제표'와 동일).
    긴 회사명은 corp 부분을 잘라 31자 이내로 맞춘다.
    """
    corp = (corp_name or "대상").strip().replace("(주)", "").replace("（주）", "")
    corp = _SHEET_BAD.sub("", corp)
    corp = re.sub(r"\s+", "", corp) or "대상"
    room = max(1, 31 - len(prefix) - len(suffix))
    if len(corp) > room:
        corp = corp[:room]
    return f"{prefix}{corp}{suffix}"[:31]


NOTE_NO_RATIO = "Ralph Loop 1에서는 비율 미계산 — 다음 루프에서 계산 예정"

# 사용자용 비율 시트 정의 (비율명, 산식, 사용 계정) — 값은 이번 루프에서 계산하지 않음
RATIO_SHEETS = {
    "02_수익성": [
        ("영업이익률", "영업이익 / 매출액", "영업이익, 매출액"),
        ("순이익률", "당기순이익 / 매출액", "당기순이익, 매출액"),
        ("ROA", "당기순이익 / 총자산(기말)", "당기순이익, 자산총계"),
        ("ROE", "당기순이익 / 자본총계(기말)", "당기순이익, 자본총계"),
    ],
    "03_안정성_재무구조": [
        ("부채비율", "부채총계 / 자본총계", "부채총계, 자본총계"),
        ("부채비중", "부채총계 / 자산총계", "부채총계, 자산총계"),
        ("유동비율", "유동자산 / 유동부채", "유동자산, 유동부채"),
        ("차입금의존도", "이자부차입금 / 자산총계", "단기차입금·유동성장기부채·사채·장기차입금, 자산총계"),
        ("이자보상배율", "영업이익 / 이자비용", "영업이익, 이자비용"),
    ],
    "04_운전자본_계정리스크": [
        ("매출채권비율", "매출채권 / 매출액", "매출채권, 매출액"),
        ("재고자산비율", "재고자산 / 매출액", "재고자산, 매출액"),
        ("매입채무비율", "매입채무 / 매출원가", "매입채무, 매출원가"),
        ("운전자본비율", "(유동자산 − 유동부채) / 매출액", "유동자산, 유동부채, 매출액"),
    ],
    "05_회전율": [
        ("총자산회전율", "매출액 / 자산총계", "매출액, 자산총계"),
        ("재고자산회전율", "매출원가 / 재고자산", "매출원가, 재고자산"),
        ("매출채권회전율", "매출액 / 매출채권", "매출액, 매출채권"),
    ],
}

RATIO_COLUMNS = ["비율명", "산식", "삼성전자 값", "산업 평균", "산업 중앙값",
                 "산업 대비 차이", "판정", "감사 관점 코멘트", "사용 계정", "peer 수"]


def _num(v):
    if v is None or v == "":
        return None
    if isinstance(v, Decimal):
        return float(v)
    return v


def _atomic_new_path(path: Path) -> Path:
    if path.exists():
        raise FileExistsError(f"기존 파일 덮어쓰기 금지: {path} (새 timestamp 파일명 사용)")
    return path


def _add_table(wb, ws, headers, rows, *, header_fmt, num_fmt=None, start_row=0,
               widths=None, col_num_formats=None):
    for c, h in enumerate(headers):
        ws.write(start_row, c, h, header_fmt)
    if widths:
        for c, w in enumerate(widths):
            ws.set_column(c, c, w)
    r = start_row + 1
    for row in rows:
        for c, val in enumerate(row):
            v = _num(val)
            if isinstance(v, float):
                fmt = None
                if col_num_formats and c in col_num_formats:
                    fmt = col_num_formats[c]
                elif num_fmt is not None:
                    fmt = num_fmt
                if fmt is not None:
                    ws.write_number(r, c, v, fmt)
                else:
                    ws.write_number(r, c, v)
            elif v is None:
                ws.write_blank(r, c, None)
            else:
                ws.write(r, c, v)
        r += 1
    ws.freeze_panes(start_row + 1, 0)
    if headers:
        ws.autofilter(start_row, 0, max(start_row, r - 1), len(headers) - 1)
    return r


# ---------------------------------------------------------------------------
def build_skeleton_workbook(path: Path, *, target: dict, target_cfs_rows: list[dict],
                            peers: list[dict], meta: dict) -> Path:
    path = _atomic_new_path(path)
    tmp = path.with_suffix(".xlsx.tmp")
    wb = xlsxwriter.Workbook(str(tmp), {"in_memory": True})
    bold = wb.add_format({"bold": True, "bg_color": "#DDDDDD", "border": 1})
    note_fmt = wb.add_format({"italic": True, "font_color": "#8A6D00", "text_wrap": True})
    num_fmt = wb.add_format({"num_format": "#,##0"})

    # 01_삼성전자_연결재무제표
    ws = wb.add_worksheet("01_삼성전자_연결재무제표")
    ws.write(0, 0, f"삼성전자({target['stock_code']}) {meta['bsns_year']}년 사업보고서 연결재무제표(CFS)", note_fmt)
    headers = ["재무제표구분", "재무제표명", "계정ID(account_id)", "계정명",
               "금액", "통화", "접수번호(rcept_no)", "수집시각(retrieved_at)"]
    rows = [[r["sj_div"], r["sj_nm"], r["account_id"], r["account_nm"], r["amount"],
             r["currency"], r["rcept_no"], r["retrieved_at"]] for r in target_cfs_rows]
    _add_table(wb, ws, headers, rows, header_fmt=bold, num_fmt=num_fmt, start_row=2,
               widths=[12, 16, 34, 30, 20, 8, 16, 26])

    # 02~05 비율 시트 (값 미계산)
    for sheet_name, ratios in RATIO_SHEETS.items():
        ws = wb.add_worksheet(sheet_name)
        ws.merge_range(0, 0, 0, len(RATIO_COLUMNS) - 1, NOTE_NO_RATIO, note_fmt)
        rows = []
        for name, formula, accounts in ratios:
            rows.append([name, formula, "", "", "", "", "미계산", NOTE_NO_RATIO, accounts, ""])
        _add_table(wb, ws, RATIO_COLUMNS, rows, header_fmt=bold, start_row=1,
                   widths=[16, 26, 14, 12, 12, 14, 10, 40, 40, 8])

    # 06_Peer_List
    ws = wb.add_worksheet("06_Peer_List")
    ws.write(0, 0, f"업종 {target['induty_code']} / 유효 prefix {target['effective_prefix']} 기준 peer 후보", note_fmt)
    headers = ["기업코드", "기업명", "종목코드", "법인구분(corp_cls)", "업종코드(induty_code)",
               "유효_prefix", "결산월(acc_mt)", "대상여부"]
    rows = [[p["corp_code"], p["corp_name"], p["stock_code"], p["corp_cls"],
             p["induty_code"], p["effective_prefix"], p["acc_mt"], "peer"] for p in peers]
    _add_table(wb, ws, headers, rows, header_fmt=bold, start_row=1,
               widths=[12, 24, 10, 16, 18, 12, 12, 10])

    # 07_Methodology
    ws = wb.add_worksheet("07_Methodology")
    _methodology(ws, wb, target, meta, peers, note_fmt, bold)

    wb.close()
    os.replace(tmp, path)
    return path


def _methodology(ws, wb, target, meta, peers, note_fmt, bold):
    wrap = wb.add_format({"text_wrap": True, "valign": "top"})
    ws.set_column(0, 0, 24)
    ws.set_column(1, 1, 90)
    lines = [
        ("문서", "Ralph Loop 1 산출물 방법론 안내 (사용자용 skeleton)"),
        ("대상 회사", f"삼성전자 (종목 {target['stock_code']}, corp_code {target['corp_code']})"),
        ("사업연도", f"{meta['bsns_year']}년"),
        ("보고서", "사업보고서(reprt_code=11011)"),
        ("재무제표", "연결재무제표(CFS)"),
        ("업종코드", f"{target['induty_code']} (기업개황 induty_code 기준)"),
        ("유효 업종 prefix", f"{target['effective_prefix']} (앞 {meta['prefix_len']}자리)"),
        ("peer 정의", "OpenDART corp_cls 상장회사(유가증권·코스닥) 중 동일 유효 prefix"),
        ("peer 후보 수", str(len(peers))),
        ("이번 루프 범위", "OpenDART 수집 + peer universe 검증. 비율/벤치마크/판정은 미구현."),
        ("비율 계산", NOTE_NO_RATIO),
        ("주의", "플래그·판정은 향후 루프에서 산업 대비 통계로 산출되며, 좋음/나쁨이 아니라 산업 대비 높음/낮음을 의미합니다. 검토 후보일 뿐 부정·오류의 결론이 아닙니다."),
        ("추적성", "모든 수집 값은 rcept_no / retrieved_at / request_hash / raw snapshot 경로로 원본까지 추적됩니다(디버그 엑셀 참조)."),
    ]
    ws.write(0, 0, "항목", bold); ws.write(0, 1, "설명", bold)
    for i, (k, v) in enumerate(lines, start=1):
        ws.write(i, 0, k)
        ws.write(i, 1, v, wrap)


# ---------------------------------------------------------------------------
def build_debug_workbook(path: Path, *, target: dict, peer_rows: list[dict],
                         long_rows: list[dict], wide_rows: list[dict],
                         log_records: list[dict], excluded: list[dict],
                         meta: dict) -> Path:
    path = _atomic_new_path(path)
    tmp = path.with_suffix(".xlsx.tmp")
    wb = xlsxwriter.Workbook(str(tmp), {"in_memory": True})
    bold = wb.add_format({"bold": True, "bg_color": "#DDDDDD", "border": 1})
    note = wb.add_format({"italic": True, "font_color": "#555555", "text_wrap": True})
    num_fmt = wb.add_format({"num_format": "#,##0"})
    wrap = wb.add_format({"text_wrap": True, "valign": "top"})

    # 00_DEBUG_README
    ws = wb.add_worksheet("00_DEBUG_README")
    ws.set_column(0, 0, 24); ws.set_column(1, 1, 100)
    readme = [
        ("문서", "Peer CFS Debug — Ralph Loop 1 (사람 검증용)"),
        ("목적", "삼성전자 2025 연결재무제표(CFS) 수집과 induty_code 3자리 prefix 기준 peer universe를 사람이 검증하기 위한 디버그 산출물."),
        ("대상", f"삼성전자 (종목 {target['stock_code']}, corp_code {target['corp_code']}, 업종 {target['induty_code']}, 유효 prefix {target['effective_prefix']})"),
        ("사업연도/보고서", f"{meta['bsns_year']}년 / 사업보고서(11011) / CFS"),
        ("시트 안내", "01 대상회사 · 02 peer universe · 03 CFS Long(수집분) · 04 주요계정 Wide 요약 · 05 수집 로그 · 06 제외/사용불가"),
        ("추적성", "Wide 요약의 각 값은 03 Long 시트의 (기업코드+계정ID+접수번호)로 역추적되며, Long의 각 행은 request_hash/raw snapshot 경로로 원본 응답까지 추적됩니다."),
        ("CFS/OFS", "이번 루프는 CFS만 수집합니다(OFS 미혼합). fs_div_actual 컬럼으로 확인."),
        ("주의", "수집·검증 단계이며 비율/판정은 계산하지 않습니다. 누락된 핵심 계정은 숨기지 않고 04/06 시트에 표시합니다."),
        ("peer CFS 상한", meta.get("debug_cap_note", "")),
    ]
    ws.write(0, 0, "항목", bold); ws.write(0, 1, "설명", bold)
    for i, (k, v) in enumerate(readme, start=1):
        ws.write(i, 0, k); ws.write(i, 1, v, wrap)

    # 01_Target_Company
    ws = wb.add_worksheet("01_Target_Company")
    headers = ["기업코드", "종목코드", "기업명", "업종코드(induty_code)", "유효_prefix",
               "결산월(acc_mt)", "법인구분(corp_cls)"]
    rows = [[target["corp_code"], target["stock_code"], target["corp_name"],
             target["induty_code"], target["effective_prefix"], target["acc_mt"],
             target["corp_cls"]]]
    _add_table(wb, ws, headers, rows, header_fmt=bold, start_row=0,
               widths=[12, 10, 24, 18, 12, 12, 16])

    # 02_Peer_Universe
    ws = wb.add_worksheet("02_Peer_Universe")
    ws.write(0, 0, f"유효 prefix {target['effective_prefix']} / 상장범위 {meta.get('allowed_cls')} 기준", note)
    headers = ["기업코드", "기업명", "종목코드", "법인구분(corp_cls)", "업종코드(induty_code)",
               "유효_prefix", "결산월(acc_mt)", "대상여부(is_target)", "디버그포함(included_for_debug)",
               "CFS수집상태(cfs_fetch_status)", "제외사유(exclude_reason)"]
    rows = [[r["corp_code"], r["corp_name"], r["stock_code"], r["corp_cls"], r["induty_code"],
             r["effective_prefix"], r["acc_mt"], r["is_target"], r["included_for_debug"],
             r["cfs_fetch_status"], r["exclude_reason"]] for r in peer_rows]
    _add_table(wb, ws, headers, rows, header_fmt=bold, start_row=1,
               widths=[12, 24, 10, 16, 18, 12, 10, 14, 20, 22, 24])

    # 03_All_Peer_CFS_Long
    ws = wb.add_worksheet("03_All_Peer_CFS_Long")
    headers = ["기업코드", "기업명", "사업연도", "보고서", "fs_div_actual", "재무제표구분(sj_div)",
               "계정ID(account_id)", "계정명", "금액", "통화", "접수번호(rcept_no)",
               "수집시각(retrieved_at)", "요청해시(request_hash)", "raw_snapshot_경로"]
    rows = [[r["corp_code"], r["corp_name"], r["bsns_year"], r["reprt_code"], r["fs_div_actual"],
             r["sj_div"], r["account_id"], r["account_nm"], r["amount"], r["currency"],
             r["rcept_no"], r["retrieved_at"], r["request_hash"], r["raw_path"]]
            for r in long_rows]
    _add_table(wb, ws, headers, rows, header_fmt=bold, num_fmt=num_fmt, start_row=0,
               widths=[12, 22, 10, 10, 14, 16, 30, 28, 20, 8, 16, 26, 18, 40])

    # 04_Peer_CFS_Wide_Summary
    ws = wb.add_worksheet("04_Peer_CFS_Wide_Summary")
    ws.write(0, 0, "각 값은 03 Long의 (기업코드+계정ID+접수번호)로 역추적 가능", note)
    key_cols = ["자산총계", "부채총계", "자본총계", "매출액", "영업이익", "당기순이익"]
    headers = ["기업코드", "기업명", "접수번호(rcept_no)", "대상여부"] + key_cols + \
              [f"{k}_매칭방식" for k in key_cols]
    rows = []
    for w in wide_rows:
        base = [w["corp_code"], w["corp_name"], w["rcept_no"], w["is_target"]]
        vals = [w["accounts"][k]["amount"] for k in key_cols]
        matches = [w["accounts"][k]["match"] for k in key_cols]
        rows.append(base + vals + matches)
    _add_table(wb, ws, headers, rows, header_fmt=bold, num_fmt=num_fmt, start_row=1,
               widths=[12, 22, 16, 10] + [18] * len(key_cols) + [18] * len(key_cols))

    # 05_Collection_Log
    ws = wb.add_worksheet("05_Collection_Log")
    headers = ["엔드포인트", "요청파라미터", "상태(status)", "메시지", "수집시각(retrieved_at)",
               "요청해시(request_hash)", "raw_경로", "캐시사용(from_cache)"]
    rows = [[r.get("endpoint"), str(r.get("params")), r.get("status"), r.get("message"),
             r.get("retrieved_at"), r.get("request_hash"), r.get("raw_path"),
             r.get("from_cache")] for r in log_records]
    _add_table(wb, ws, headers, rows, header_fmt=bold, start_row=0,
               widths=[18, 40, 12, 30, 26, 18, 40, 14])

    # 06_Excluded_or_Not_Usable
    ws = wb.add_worksheet("06_Excluded_or_Not_Usable")
    headers = ["기업코드", "기업명", "구분", "사유(reason)"]
    rows = [[r["corp_code"], r["corp_name"], r["kind"], r["reason"]] for r in excluded]
    _add_table(wb, ws, headers, rows, header_fmt=bold, start_row=0,
               widths=[12, 24, 20, 60])

    wb.close()
    os.replace(tmp, path)
    return path


# =========================================================================
# Loop 2 builders (all user-facing text in Korean)
# =========================================================================
def build_debug_full_workbook(path: Path, *, target: dict, peer_rows: list[dict],
                              long_rows: list[dict], wide_rows: list[dict],
                              log_records: list[dict], excluded: list[dict], meta: dict) -> Path:
    """전체 peer CFS debug — 한글 시트. 03에 stock_code 포함."""
    path = _atomic_new_path(path)
    tmp = path.with_suffix(".xlsx.tmp")
    wb = xlsxwriter.Workbook(str(tmp), {"in_memory": True})
    bold = wb.add_format({"bold": True, "bg_color": "#DDDDDD", "border": 1})
    note = wb.add_format({"italic": True, "font_color": "#555555", "text_wrap": True})
    num_fmt = wb.add_format({"num_format": "#,##0"})
    wrap = wb.add_format({"text_wrap": True, "valign": "top"})

    ws = wb.add_worksheet("00_검증안내")
    ws.set_column(0, 0, 24); ws.set_column(1, 1, 100)
    readme = [
        ("문서", "전체 peer CFS Debug — Ralph Loop 2 (사람 검증용)"),
        ("목적", f"삼성전자 2025 CFS + 유효 prefix {target['effective_prefix']} peer 후보 전체 CFS 수집 검증. 디버그 상한 없음."),
        ("대상", f"삼성전자(종목 {target['stock_code']}, corp_code {target['corp_code']}, 업종 {target['induty_code']})"),
        ("Loop 범위", "전체 peer CFS 수집 + 추적성 검증. 산업 benchmark/HIGH-LOW 판정은 Loop 3."),
        ("CFS/OFS", "CFS만 수집(OFS 미혼합·자동 fallback 없음). fs_div_actual 컬럼으로 확인."),
        ("추적성", "03의 각 행은 요청해시(request_hash)/raw_snapshot_경로로 원본 응답까지 추적. stock_code 포함."),
        ("leave-one-out", "삼성전자는 target이며, 향후 benchmark pool에서는 leave-one-out 대상."),
    ]
    ws.write(0, 0, "항목", bold); ws.write(0, 1, "설명", bold)
    for i, (k, v) in enumerate(readme, 1):
        ws.write(i, 0, k); ws.write(i, 1, v, wrap)

    ws = wb.add_worksheet("01_대상회사")
    _add_table(wb, ws, ["기업코드", "종목코드", "기업명", "업종코드(induty_code)", "유효_prefix",
                        "결산월(acc_mt)", "법인구분(corp_cls)", "비고"],
               [[target["corp_code"], target["stock_code"], target["corp_name"], target["induty_code"],
                 target["effective_prefix"], target["acc_mt"], target["corp_cls"],
                 "target(향후 benchmark pool에서 leave-one-out 대상)"]],
               header_fmt=bold, start_row=0, widths=[12, 10, 24, 18, 12, 12, 16, 40])

    ws = wb.add_worksheet("02_피어_유니버스")
    ws.write(0, 0, f"유효 prefix {target['effective_prefix']} / 상장범위 {meta.get('allowed_cls')} — peer 후보 전체 CFS 시도(디버그 상한 없음)", note)
    _add_table(wb, ws,
               ["기업코드", "기업명", "종목코드", "법인구분(corp_cls)", "업종코드(induty_code)", "유효_prefix",
                "결산월(acc_mt)", "대상여부(is_target)", "CFS수집상태(cfs_fetch_status)",
                "제외사유(exclude_reason)", "데이터구분(data_kind)"],
               [[r["corp_code"], r["corp_name"], r["stock_code"], r["corp_cls"], r["induty_code"],
                 r["effective_prefix"], r["acc_mt"], r["is_target"], r["cfs_fetch_status"],
                 r["exclude_reason"], r.get("data_kind", "")] for r in peer_rows],
               header_fmt=bold, start_row=1, widths=[12, 24, 10, 16, 18, 12, 10, 14, 22, 24, 18])

    ws = wb.add_worksheet("03_전체_CFS_Long")
    _add_table(wb, ws,
               ["기업코드", "종목코드", "기업명", "사업연도", "보고서", "fs_div_actual", "재무제표구분(sj_div)",
                "계정ID(account_id)", "계정명", "금액", "통화", "접수번호(rcept_no)", "수집시각(retrieved_at)",
                "요청해시(request_hash)", "raw_snapshot_경로"],
               [[r["corp_code"], r.get("stock_code", ""), r["corp_name"], r["bsns_year"], r["reprt_code"],
                 r["fs_div_actual"], r["sj_div"], r["account_id"], r["account_nm"], r["amount"],
                 r["currency"], r["rcept_no"], r["retrieved_at"], r["request_hash"], r["raw_path"]]
                for r in long_rows],
               header_fmt=bold, num_fmt=num_fmt, start_row=0,
               widths=[12, 10, 20, 10, 10, 14, 16, 30, 26, 20, 8, 16, 26, 18, 40])

    ws = wb.add_worksheet("04_주요계정_Wide")
    ws.write(0, 0, "각 값은 03의 (기업코드+계정ID+접수번호)로 역추적 가능", note)
    key_cols = ["자산총계", "부채총계", "자본총계", "매출액", "영업이익", "당기순이익"]
    headers = ["기업코드", "기업명", "접수번호(rcept_no)", "대상여부"] + key_cols + [f"{k}_매칭방식" for k in key_cols]
    rows = []
    for w in wide_rows:
        rows.append([w["corp_code"], w["corp_name"], w["rcept_no"], w["is_target"]]
                    + [w["accounts"][k]["amount"] for k in key_cols]
                    + [w["accounts"][k]["match"] for k in key_cols])
    _add_table(wb, ws, headers, rows, header_fmt=bold, num_fmt=num_fmt, start_row=1,
               widths=[12, 22, 16, 10] + [18] * len(key_cols) + [16] * len(key_cols))

    ws = wb.add_worksheet("05_수집로그")
    _add_table(wb, ws,
               ["엔드포인트", "요청파라미터", "상태(status)", "메시지", "수집시각(retrieved_at)",
                "요청해시(request_hash)", "raw_경로", "캐시사용(from_cache)"],
               [[r.get("endpoint"), str(r.get("params")), r.get("status"), r.get("message"),
                 r.get("retrieved_at"), r.get("request_hash"), r.get("raw_path"), r.get("from_cache")]
                for r in log_records],
               header_fmt=bold, start_row=0, widths=[18, 40, 12, 30, 26, 18, 40, 14])

    ws = wb.add_worksheet("06_제외_사용불가")
    _add_table(wb, ws, ["기업코드", "기업명", "구분", "사유(reason)"],
               [[r["corp_code"], r["corp_name"], r["kind"], r["reason"]] for r in excluded],
               header_fmt=bold, start_row=0, widths=[12, 24, 20, 60])

    wb.close()
    os.replace(tmp, path)
    return path


def build_ratio_input_workbook(path: Path, *, ratio_rows_all: list[dict], coverage_concepts: list[str],
                               coverage_rows: list[dict], dedup_rows: list[dict],
                               trace_sample_rows: list[dict], meta: dict) -> Path:
    from . import accounts, ratio_input  # lazy (avoid import cycle)

    path = _atomic_new_path(path)
    tmp = path.with_suffix(".xlsx.tmp")
    wb = xlsxwriter.Workbook(str(tmp), {"in_memory": True})
    bold = wb.add_format({"bold": True, "bg_color": "#DDDDDD", "border": 1})
    note = wb.add_format({"italic": True, "font_color": "#555555", "text_wrap": True})
    amt = wb.add_format({"num_format": "#,##0"})
    ratio_fmt = wb.add_format({"num_format": "0.0000"})
    wrap = wb.add_format({"text_wrap": True, "valign": "top"})

    ws = wb.add_worksheet("00_검증안내")
    ws.set_column(0, 0, 24); ws.set_column(1, 1, 100)
    readme = [
        ("문서", "계정 매핑 / 비율 입력값 Debug — Ralph Loop 2"),
        ("목적", "15개 비율의 회사별 계산 가능 여부·입력값·source를 검증. 개별 비율값은 계산하되 산업 benchmark/HIGH-LOW 판정은 하지 않음(Loop 3)."),
        ("매핑 원칙", "account_id 우선, account_nm 정확일치 제한 fallback. fuzzy 확장 금지. 불확실 시 NOT_COMPUTABLE."),
        ("추적성", "각 비율의 분자/분모는 source(account_id·account_nm·rcept_no)로 표시되며, 전체_CFS_Long(별도 파일)에서 (기업코드+계정ID+rcept_no)로 raw까지 추적."),
        ("NOT_COMPUTABLE 사유", "missing_account / invalid_denominator / mapping_not_confident / invalid_statement_section"),
        ("차입금의존도", "이자부 차입금(단기차입금+유동성장기부채+사채+장기차입금, 리스 제외) / 자산총계"),
        ("운전자본비율", "(유동자산 − 유동부채) / 매출액"),
    ]
    ws.write(0, 0, "항목", bold); ws.write(0, 1, "설명", bold)
    for i, (k, v) in enumerate(readme, 1):
        ws.write(i, 0, k); ws.write(i, 1, v, wrap)

    ws = wb.add_worksheet("01_비율정의")
    _add_table(wb, ws, ["비율명", "그룹", "산식", "분자concept", "분모concept"],
               [[n, g, f, (nc if not nc.startswith("__") else nc.strip("_")), dc]
                for n, g, nc, dc, f in ratio_input.RATIOS],
               header_fmt=bold, start_row=0, widths=[16, 10, 30, 16, 12])

    ws = wb.add_worksheet("02_계정매핑_정본")
    mrows = []
    for name, spec in accounts.CONCEPTS.items():
        mrows.append([name, "/".join(spec["sj"]), ", ".join(spec["ids"]), ", ".join(spec["nm"]), "기본계정"])
    for name, spec in accounts.BORROWING_COMPONENTS.items():
        mrows.append([name, "/".join(spec["sj"]), ", ".join(spec["ids"]), ", ".join(spec["nm"]), "이자부차입금 구성"])
    _add_table(wb, ws, ["개념", "재무제표구분(sj_div)", "account_id 후보(우선순위)", "account_nm 정확일치 후보", "구분"],
               mrows, header_fmt=bold, start_row=0, widths=[16, 14, 52, 30, 16])

    ws = wb.add_worksheet("03_회사별_필수계정_커버리지")
    headers = ["기업코드", "기업명", "대상여부"] + coverage_concepts
    rows = [[cr["corp_code"], cr["corp_name"], cr["is_target"]] + [cr["coverage"].get(c, "") for c in coverage_concepts]
            for cr in coverage_rows]
    _add_table(wb, ws, headers, rows, header_fmt=bold, start_row=0,
               widths=[12, 22, 10] + [14] * len(coverage_concepts))

    ws = wb.add_worksheet("04_비율별_입력값")
    headers = ["기업코드", "종목코드", "기업명", "대상여부", "비율명", "그룹", "산식", "분자concept",
               "분자값", "분자source", "분모concept", "분모값", "분모source", "비율값", "계산가능", "사유"]
    rows = [[r["corp_code"], r["stock_code"], r["corp_name"], r["is_target"], r["ratio"], r["group"],
             r["formula"], r["numerator_concept"], r["numerator_value"], r["numerator_src"],
             r["denominator_concept"], r["denominator_value"], r["denominator_src"], r["ratio_value"],
             ("가능" if r["computable"] else "불가"), r["reason"]] for r in ratio_rows_all]
    _add_table(wb, ws, headers, rows, header_fmt=bold, start_row=0,
               col_num_formats={8: amt, 11: amt, 13: ratio_fmt},
               widths=[12, 10, 20, 10, 16, 10, 26, 14, 18, 40, 14, 18, 40, 12, 10, 22])

    ws = wb.add_worksheet("05_NOT_COMPUTABLE_사유")
    nc = [r for r in ratio_rows_all if not r["computable"]]
    _add_table(wb, ws, ["기업코드", "기업명", "비율명", "사유(reason)", "분자source", "분모source"],
               [[r["corp_code"], r["corp_name"], r["ratio"], r["reason"], r["numerator_src"], r["denominator_src"]]
                for r in nc],
               header_fmt=bold, start_row=0, widths=[12, 20, 16, 24, 40, 40])

    ws = wb.add_worksheet("06_dedup_로그")
    _add_table(wb, ws,
               ["기업코드", "기업명", "개념", "선택_account_id", "선택_account_nm", "선택_sj",
                "선택_rcept_no", "드롭_후보수", "규칙"],
               [[d["corp_code"], d["corp_name"], d["concept"], d["chosen_account_id"], d["chosen_account_nm"],
                 d["chosen_sj"], d["chosen_rcept_no"], d["dropped_alternatives"], d["rule"]] for d in dedup_rows],
               header_fmt=bold, start_row=0, widths=[12, 20, 14, 30, 20, 8, 16, 12, 60])

    ws = wb.add_worksheet("07_source_trace_샘플")
    ws.write(0, 0, "삼성전자 15개 비율 입력값 — 각 계정은 전체_CFS_Long에서 (기업코드+계정ID+rcept_no)로 raw까지 추적", note)
    _add_table(wb, ws,
               ["비율명", "분자값", "분자source", "분모값", "분모source", "비율값", "계산가능", "사유"],
               [[r["ratio"], r["numerator_value"], r["numerator_src"], r["denominator_value"],
                 r["denominator_src"], r["ratio_value"], ("가능" if r["computable"] else "불가"), r["reason"]]
                for r in trace_sample_rows],
               header_fmt=bold, start_row=1, col_num_formats={1: amt, 3: amt, 5: ratio_fmt},
               widths=[16, 18, 44, 18, 44, 12, 10, 22])

    wb.close()
    os.replace(tmp, path)
    return path


def build_skeleton_workbook_v2(path: Path, *, target: dict, target_cfs_rows: list[dict],
                               peers: list[dict], target_ratio_map: dict, meta: dict) -> Path:
    """사용자용 skeleton — 02~05에 삼성전자 개별 비율값 표시. benchmark/판정은 Loop 3 안내."""
    path = _atomic_new_path(path)
    tmp = path.with_suffix(".xlsx.tmp")
    wb = xlsxwriter.Workbook(str(tmp), {"in_memory": True})
    bold = wb.add_format({"bold": True, "bg_color": "#DDDDDD", "border": 1})
    note_fmt = wb.add_format({"italic": True, "font_color": "#8A6D00", "text_wrap": True})
    num_fmt = wb.add_format({"num_format": "#,##0"})
    ratio_fmt = wb.add_format({"num_format": "0.0000"})
    L3 = "Ralph Loop 3에서 산업 benchmark 판정 예정"

    ws = wb.add_worksheet("01_삼성전자_연결재무제표")
    ws.write(0, 0, f"삼성전자({target['stock_code']}) {meta['bsns_year']}년 사업보고서 연결재무제표(CFS)", note_fmt)
    _add_table(wb, ws, ["재무제표구분", "재무제표명", "계정ID(account_id)", "계정명", "금액", "통화",
                        "접수번호(rcept_no)", "수집시각(retrieved_at)"],
               [[r["sj_div"], r["sj_nm"], r["account_id"], r["account_nm"], r["amount"], r["currency"],
                 r["rcept_no"], r["retrieved_at"]] for r in target_cfs_rows],
               header_fmt=bold, num_fmt=num_fmt, start_row=2, widths=[12, 16, 34, 30, 20, 8, 16, 26])

    for sheet_name, ratios in RATIO_SHEETS.items():
        ws = wb.add_worksheet(sheet_name)
        ws.merge_range(0, 0, 0, len(RATIO_COLUMNS) - 1,
                       "삼성전자 개별 비율값은 계산·표시. 산업 평균/중앙값/차이/판정은 " + L3, note_fmt)
        rows = []
        for name, formula, accounts_used in ratios:
            tm = target_ratio_map.get(name, {})
            if tm.get("computable"):
                val = tm.get("value")
            else:
                val = f"계산불가({tm.get('reason', '')})" if tm else ""
            rows.append([name, formula, val, L3, L3, L3, L3, L3, accounts_used, ""])
        _add_table(wb, ws, RATIO_COLUMNS, rows, header_fmt=bold, start_row=1,
                   col_num_formats={2: ratio_fmt},
                   widths=[16, 26, 16, 30, 30, 30, 30, 30, 40, 8])

    ws = wb.add_worksheet("06_Peer_List")
    ws.write(0, 0, f"업종 {target['induty_code']} / 유효 prefix {target['effective_prefix']} 기준 peer 후보", note_fmt)
    _add_table(wb, ws, ["기업코드", "기업명", "종목코드", "법인구분(corp_cls)", "업종코드(induty_code)",
                        "유효_prefix", "결산월(acc_mt)", "대상여부"],
               [[p["corp_code"], p["corp_name"], p["stock_code"], p["corp_cls"], p["induty_code"],
                 p["effective_prefix"], p["acc_mt"], "peer"] for p in peers],
               header_fmt=bold, start_row=1, widths=[12, 24, 10, 16, 18, 12, 12, 10])

    ws = wb.add_worksheet("07_Methodology")
    _methodology(ws, wb, target, meta, peers, note_fmt, bold)

    wb.close()
    os.replace(tmp, path)
    return path


# =========================================================================
# Loop 3 builders — 산업 benchmark 최종 리포트 + benchmark debug (한글)
# =========================================================================
# 그룹 -> 사용자 시트명
_GROUP_SHEET = {"수익성": "02_수익성", "안정성": "03_안정성_재무구조",
                "운전자본": "04_운전자본_계정리스크", "회전율": "05_회전율"}
_SHEET_ORDER = ["02_수익성", "03_안정성_재무구조", "04_운전자본_계정리스크", "05_회전율"]

# Loop 15: 사용자용 비율 시트 핵심 9열(기존 24열 → 9열). 나머지 상세 통계·source는 삭제가
# 아니라 benchmark_debug 리포트로 이동(계산은 그대로, 사용자 화면에서만 숨김).
FINAL_RATIO_COLUMNS = [
    "비율명", "산식", "대상회사 값", "산업 중앙값", "산업 내 위치(percentile)",
    "상대판정", "절대판정(red flag)", "판정 사유", "신뢰도(peer·품질)",
]
# 참고: 상대판정=median/IQR 기준 산업 대비 위치, 절대판정=회사·산업 무관 절대 기준선(red flag) 점검.
FINAL_RATIO_COLUMNS_DEBUG_MOVED = [   # 사용자 시트에서 debug로 옮긴 열(감사용, benchmark_debug에 존재)
    "그룹", "산업 평균", "산업 p25", "산업 p75", "IQR", "중앙값 대비 비율차이(%)",
    "중앙값 대비 차이(%p·값)", "robust_z", "benchmark_quality(상세)", "해석 비고",
    "사용 계정", "peer 후보 수", "CFS 성공/실패 peer 수", "source reference",
]
_SJ_NM_FALLBACK = {"BS": "재무상태표", "IS": "손익계산서", "CIS": "포괄손익계산서",
                   "CF": "현금흐름표", "SCE": "자본변동표"}


def _label_formats(wb):
    """판정 라벨별 셀 서식. 초록/빨강(좋음/나쁨 암시) 금지 — 주황/파랑/회색만."""
    return {
        "HIGH": wb.add_format({"bg_color": "#FFE0B2", "font_color": "#E65100", "border": 1}),   # 주황
        "LOW": wb.add_format({"bg_color": "#BBDEFB", "font_color": "#0D47A1", "border": 1}),     # 파랑
        "NORMAL": wb.add_format({"bg_color": "#F5F5F5", "font_color": "#424242", "border": 1}),  # 연회색
        "INSUFFICIENT_PEERS": wb.add_format({"bg_color": "#E0E0E0", "font_color": "#616161", "border": 1}),
        "NOT_COMPUTABLE": wb.add_format({"bg_color": "#E0E0E0", "font_color": "#616161", "border": 1}),
        "INSUFFICIENT_VARIANCE": wb.add_format({"bg_color": "#E0E0E0", "font_color": "#616161", "border": 1}),
    }


def _abs_formats(wb):
    """절대판정(red flag) 상태별 서식. 빨강(위험 확정)·초록(안전) 금지 — 앰버/노랑/회색만.
    red flag는 '점검 신호'이지 결론이 아니므로 danger red를 쓰지 않는다(INV-8 정신)."""
    return {
        "경고": wb.add_format({"bg_color": "#FFD180", "font_color": "#5D4037", "border": 1, "bold": True}),
        "주의": wb.add_format({"bg_color": "#FFF3C4", "font_color": "#6D4C41", "border": 1}),
        "정상": wb.add_format({"bg_color": "#F5F5F5", "font_color": "#424242", "border": 1}),
        "해당없음": wb.add_format({"bg_color": "#FAFAFA", "font_color": "#9E9E9E", "border": 1}),
        "미평가": wb.add_format({"bg_color": "#FFFFFF", "font_color": "#BDBDBD", "italic": True, "border": 1}),
    }


def _write_final_ratio_sheet(wb, ws, comp_rows, *, ratio_fmt, z_fmt, wrap, header_fmt,
                             label_fmts, label_ko, abs_fmts):
    """Loop 15: 사용자용 핵심 9열. 상대판정(median/IQR)과 절대판정(red flag)을 병렬 표시.
    상세 통계·source는 benchmark_debug로 이동(여기서 숨김, 계산 불변)."""
    ws.merge_range(0, 0, 0, len(FINAL_RATIO_COLUMNS) - 1,
                   "상대판정=산업 peer 대비 위치(HIGH=산업 대비 높음/LOW=산업 대비 낮음/정상, median·IQR 기준, "
                   "좋음·나쁨 아님). 절대판정=회사·산업 무관 절대 기준선(red flag) 점검이며 '위험 확정'이 아니라 "
                   "검토 경고/점검 신호입니다. 상세 통계(평균·p25·p75·IQR·robust_z·차이·source 등)는 "
                   "benchmark_debug 리포트에 있습니다.", wrap)
    for c, h in enumerate(FINAL_RATIO_COLUMNS):
        ws.write(1, c, h, header_fmt)
    widths = [16, 26, 14, 14, 18, 14, 20, 62, 22]
    for c, w in enumerate(widths):
        ws.set_column(c, c, w)
    r = 2
    for row in comp_rows:
        st = row["stats"]
        label = row["label"]
        # abs_verdict 없음 = red flag 레이어 미평가(CLI 등). '해당없음'(평가함·링크 flag 없음)과 구분.
        av = row.get("abs_verdict")
        astatus = av.get("status") if av else "미평가"
        amsg = (av.get("message") if av else "") or ""
        base_reason = row.get("reason", "")
        reason_cell = f"[절대판정 {astatus}] {amsg}  |  {base_reason}" if amsg else base_reason
        n = st.get("n_companies")
        conf = f"{row.get('benchmark_quality', '')} (peer {n})"
        cells = [
            (row["ratio"], None), (row["formula"], None),
            (row["target_value"], ratio_fmt), (st["median"], ratio_fmt),
            (row["percentile"], z_fmt),
            (label_ko.get(label, label), label_fmts.get(label)),
            (astatus, abs_fmts.get(astatus)),
            (reason_cell, wrap), (conf, None),
        ]
        for c, (v, fmt) in enumerate(cells):
            v = _num(v)
            if isinstance(v, float):
                ws.write_number(r, c, v, fmt) if fmt else ws.write_number(r, c, v)
            elif v is None:
                ws.write_blank(r, c, None, fmt) if fmt else ws.write_blank(r, c, None)
            else:
                ws.write(r, c, v, fmt) if fmt else ws.write(r, c, v)
        r += 1
    ws.freeze_panes(2, 0)
    ws.autofilter(1, 0, max(1, r - 1), len(FINAL_RATIO_COLUMNS) - 1)


def build_final_report_workbook(path: Path, *, target: dict, target_cfs_rows: list[dict],
                                peers: list[dict], peer_rows: list[dict],
                                comparison_rows: list[dict], excluded_summary: list[dict],
                                meta: dict, sparse_comparison: list[dict] | None = None,
                                red_flag_assessment: dict | None = None) -> Path:
    """최종 사용자용 산업대비 이상징후 리포트(기본 9시트, 전부 한글).

    sparse_comparison(Ralph Loop 6): 계산 가능 peer<min_peers라 통계 판정을 보류한 비율의
    '참고 직접 비교' row 목록(sparse_peer_comparison.build_sparse_peer_comparison 결과).
    비어 있지 않으면 '09_제한적_peer_비교' 시트를 **추가**한다(sparse 비율이 없으면 미생성 →
    충분 peer target은 9시트 구조가 그대로 유지된다). benchmark/label은 변경하지 않는다.
    """
    from . import compare as cmp  # LABEL_KO
    path = _atomic_new_path(path)
    tmp = path.with_suffix(".xlsx.tmp")
    wb = xlsxwriter.Workbook(str(tmp), {"in_memory": True})
    bold = wb.add_format({"bold": True, "bg_color": "#DDDDDD", "border": 1})
    note = wb.add_format({"italic": True, "font_color": "#8A6D00", "text_wrap": True})
    wrap = wb.add_format({"text_wrap": True, "valign": "top"})
    amt = wb.add_format({"num_format": "#,##0"})
    ratio_fmt = wb.add_format({"num_format": "0.0000"})
    pct_fmt = wb.add_format({"num_format": "+0.0%;-0.0%;0.0%"})
    pp_fmt = wb.add_format({"num_format": "+0.00;-0.00;0.00"})      # 비율 %p 차이(값−중앙값)×100
    turn_fmt = wb.add_format({"num_format": "+0.0000;-0.0000;0.0000"})  # 회전율 값 차이
    z_fmt = wb.add_format({"num_format": "0.00"})
    int_fmt = wb.add_format({"num_format": "0"})
    label_fmts = _label_formats(wb)
    abs_fmts = _abs_formats(wb)

    n_cand = len(peers)
    n_succ = sum(1 for r in peer_rows if r["is_target"] == "peer" and r["cfs_fetch_status"] == "성공")
    n_fail = sum(1 for r in peer_rows if r["is_target"] == "peer" and r["cfs_fetch_status"] != "성공")

    # 00_README
    ws = wb.add_worksheet("00_README")
    ws.set_column(0, 0, 24); ws.set_column(1, 1, 104)
    readme = [
        ("문서", f"{target['corp_name']} {meta['bsns_year']} 산업대비 이상징후 리포트 (Ralph Loop 3, 사용자용)"),
        ("성격", "본 산출물은 감사 보조용 screening 자료입니다. 확정 결론이 아닙니다."),
        ("HIGH/LOW 의미", "HIGH=산업 대비 높음, LOW=산업 대비 낮음. 부정·오류·왜곡표시·좋음/나쁨을 의미하지 않으며, 산업 대비 상대적 위치입니다."),
        ("benchmark 기준", f"OpenDART induty_code {target['induty_code']}(유효 prefix {target['effective_prefix']}) peer universe에서 계산."),
        ("peer 구성", f"peer 후보 {n_cand}개, CFS 성공 {n_succ}개, CFS 실패 {n_fail}개. 실패분은 CFS 사용불가(status=013 등)로 제외."),
        ("비율별 n", "각 비율별 benchmark는 그 비율의 계산 가능 peer 수(n) 기준입니다. n은 비율마다 다를 수 있습니다."),
        ("전부 NORMAL 해석", f"모든 비율이 NORMAL이라는 것은 안전이 확정됐다는 의미가 아니라, 현재 induty_code {target['induty_code']} peer universe와 median/IQR fence 기준에서 이상치로 분류되지 않았다는 뜻입니다. 추가 확인이 여전히 필요할 수 있습니다."),
        ("상대판정 vs 절대판정", "상대판정(HIGH/LOW/정상)은 산업 peer 대비 위치입니다. 절대판정(red flag)은 회사·산업 무관 절대 기준선(유동비율<1·운전자본 음수·이자보상배율<1·자본잠식·고부채·이익-현금 괴리) 점검이며, 각 비율 시트 '절대판정' 열에 표시됩니다. red flag는 '위험 확정'이 아니라 검토 경고/점검 신호입니다."),
        ("IQR fence 한계", "peer 분포의 꼬리가 두껍거나 비교가능성이 낮은 회사가 섞이면 IQR fence가 넓어져 극단적 HIGH/LOW가 줄 수 있습니다. percentile·robust_z·benchmark_quality·peer 수를 함께 해석하세요."),
        ("중앙값 대비 차이 해석", "'중앙값 대비 비율차이(%)'는 (값−중앙값)/|중앙값|로, 중앙값이 작으면 크게 보일 수 있습니다. 이 경우 '중앙값 대비 차이(%p·값)'(값−중앙값)와 IQR 판정을 함께 보세요. %비율 항목은 %p, 회전율 항목은 값 차이로 표시됩니다."),
        ("benchmark_quality", "WEAK/LIMITED인 비율은 계산 가능 peer 수나 계정 커버리지가 제한적입니다. 특히 매출채권·매입채무 관련 비율은 순수 계정 기준을 유지해 n이 낮을 수 있습니다."),
        ("leave-one-out", "대상 회사는 자기 자신의 benchmark 계산에서 제외했습니다(비교 대상값으로만 사용)."),
        ("매핑 정책", "매출채권·매입채무는 순수 계정 기준이며, '및기타채권/및기타채무' fallback은 사용하지 않았습니다."),
        ("통계 기준", "평균은 참고값이며 판정은 median/IQR 중심입니다. winsorized 평균은 참고값입니다."),
        ("비교가능성 한계", "대상 회사와 산업 peer 간 사업 구성·규모 차이로 induty_code 기반 peer benchmark에는 비교가능성 한계가 있을 수 있습니다."),
        ("색상", "HIGH=주황, LOW=파랑, 정상=연회색, 계산불가/peer부족/분포부족=회색. 초록/빨강(좋음/나쁨)은 사용하지 않습니다."),
        ("추적성", "각 비율의 source reference와 별도 benchmark_debug 파일의 pool/통계로 원본까지 추적됩니다."),
    ]
    # Loop 15: 절대판정(red flag) 6종 점검 요약(트리거/평가불가를 은폐하지 않고 표면화 — INV-5).
    if red_flag_assessment:
        flags = red_flag_assessment.get("flags", [])
        trig = [f for f in flags if f.get("triggered")]
        na = [f for f in flags if f.get("status") == "해당없음"]
        if trig:
            body = "트리거됨 → " + " / ".join(f"{f['message']}({f['severity']})" for f in trig)
        else:
            body = "트리거된 red flag 없음(6종 점검)"
        if na:
            body += f". 평가불가 {len(na)}종(해당 계정 미발견 등, 예: 이자비용/영업현금흐름)"
        readme.append(("절대판정(red flag) 점검 결과",
                       body + ". red flag는 위험 확정이 아니라 검토 경고/점검 신호입니다."))

    ws.write(0, 0, "항목", bold); ws.write(0, 1, "설명", bold)
    for i, (k, v) in enumerate(readme, 1):
        ws.write(i, 0, k); ws.write(i, 1, v, wrap)

    # 01_삼성전자_연결재무제표
    ws = wb.add_worksheet(safe_sheet_name("01_", target["corp_name"], "_연결재무제표"))
    ws.write(0, 0, f"{target['corp_name']}({target['stock_code']}) {meta['bsns_year']}년 사업보고서 연결재무제표(CFS)", note)
    _add_table(wb, ws, ["재무제표구분", "재무제표명", "계정ID(account_id)", "계정명", "금액", "통화",
                        "접수번호(rcept_no)", "수집시각(retrieved_at)"],
               [[r["sj_div"], r.get("sj_nm") or _SJ_NM_FALLBACK.get(r["sj_div"], ""), r["account_id"],
                 r["account_nm"], r["amount"], r["currency"], r["rcept_no"], r["retrieved_at"]]
                for r in target_cfs_rows],
               header_fmt=bold, num_fmt=amt, start_row=2, widths=[12, 16, 34, 30, 20, 8, 16, 26])

    # 02~05 비율 시트
    by_group = {}
    for row in comparison_rows:
        by_group.setdefault(_GROUP_SHEET.get(row["group"]), []).append(row)
    for sheet_name in _SHEET_ORDER:
        ws = wb.add_worksheet(sheet_name)
        _write_final_ratio_sheet(wb, ws, by_group.get(sheet_name, []),
                                 ratio_fmt=ratio_fmt, z_fmt=z_fmt, wrap=wrap, header_fmt=bold,
                                 label_fmts=label_fmts, label_ko=cmp.LABEL_KO, abs_fmts=abs_fmts)

    # 06_Peer_List
    ws = wb.add_worksheet("06_Peer_List")
    ws.write(0, 0, f"업종 {target['induty_code']} / 유효 prefix {target['effective_prefix']} — "
                   f"peer 후보 {n_cand} / CFS 성공 {n_succ} / CFS 실패 {n_fail}", note)
    _add_table(wb, ws, ["기업코드", "기업명", "종목코드", "법인구분(corp_cls)", "업종코드(induty_code)",
                        "결산월(acc_mt)", "대상여부", "CFS수집상태", "제외/비고 사유"],
               [[r["corp_code"], r["corp_name"], r["stock_code"], r["corp_cls"], r["induty_code"],
                 r["acc_mt"], r["is_target"], r["cfs_fetch_status"], r["exclude_reason"]]
                for r in peer_rows],
               header_fmt=bold, start_row=1, widths=[12, 24, 10, 16, 18, 10, 10, 18, 30])

    # 07_Methodology
    ws = wb.add_worksheet("07_Methodology")
    _methodology_loop3(ws, wb, target, meta, n_cand, n_succ, n_fail, bold, wrap)

    # 08_계산불가_및_제외사유
    ws = wb.add_worksheet("08_계산불가_및_제외사유")
    ws.write(0, 0, "NOT_COMPUTABLE / INSUFFICIENT_PEERS / INSUFFICIENT_VARIANCE / CFS 실패 사유 모음", note)
    _add_table(wb, ws, ["구분", "대상", "항목", "사유"],
               [[e["kind"], e["who"], e["item"], e["reason"]] for e in excluded_summary],
               header_fmt=bold, start_row=1, widths=[24, 24, 20, 70])

    # 09_제한적_peer_비교 (Ralph Loop 6): sparse 비율이 있을 때만 추가.
    # 충분 peer target(sparse 없음)은 미생성 → 기존 9시트 구조 그대로 유지.
    if sparse_comparison:
        ws = wb.add_worksheet("09_제한적_peer_비교")
        _write_sparse_peer_sheet(wb, ws, sparse_comparison, bold=bold, wrap=wrap, note=note,
                                 ratio_fmt=ratio_fmt, min_peers=int(meta.get("min_peers", 5)))

    wb.close()
    os.replace(tmp, path)
    return path


def _write_sparse_peer_sheet(wb, ws, sparse_rows, *, bold, wrap, note, ratio_fmt, min_peers):
    """09_제한적_peer_비교 시트: peer<min_peers 비율의 참고용 직접 비교(통계 benchmark 아님).

    실제 peer 회사명을 컬럼(f"{corp_name} 값")으로 표시한다(익명 Peer 1/2 금지). 색상으로
    좋고 나쁨을 암시하지 않는다(label 서식 미사용). 값이 없는 peer는 빈칸으로 둔다.
    """
    from collections import Counter
    warn = (f"이 시트는 동종산업 상장 CFS peer 수가 최소 benchmark 기준(min_peers={min_peers})에 "
            "미달하여 HIGH/LOW/NORMAL 통계 판정을 보류한 비율의 '참고용 직접 비교'입니다. "
            "통계적 benchmark가 아니며, 소수 peer와의 단순 비교 참고값입니다. min_peers를 낮추거나 "
            "2자리 업종 rollup을 하지 않았습니다. 색상으로 좋고 나쁨을 표시하지 않습니다.")

    # peer 회사 union(등장 빈도 desc, 이름 asc) → 실제 회사명 컬럼(결정적 순서).
    freq = Counter()
    for row in sparse_rows:
        for p in row["peer_company_values"]:
            if p.get("corp_name"):
                freq[p["corp_name"]] += 1
    peer_names = [n for n, _ in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))]

    fixed_head = ["비율 그룹", "비율명", "대상회사", "대상회사 값", "비교 가능 peer 수"]
    peer_head = [f"{n} 값" for n in peer_names]
    tail_head = ["참고 중위값(비통계)", "대상회사 위치(순위)", "판정 상태", "통계 benchmark 여부",
                 "해석 메모", "산정 근거"]
    headers = fixed_head + peer_head + tail_head

    ws.merge_range(0, 0, 0, max(0, len(headers) - 1), warn, note)
    for c, h in enumerate(headers):
        ws.write(1, c, h, bold)

    ws.set_column(0, 0, 12); ws.set_column(1, 1, 16); ws.set_column(2, 2, 16)
    ws.set_column(3, 4, 14)
    if peer_head:
        ws.set_column(5, 5 + len(peer_head) - 1, 16)
    t0 = 5 + len(peer_head)
    ws.set_column(t0, t0, 16); ws.set_column(t0 + 1, t0 + 1, 20); ws.set_column(t0 + 2, t0 + 2, 22)
    ws.set_column(t0 + 3, t0 + 3, 16); ws.set_column(t0 + 4, t0 + 4, 60); ws.set_column(t0 + 5, t0 + 5, 60)

    def _wnum(r, c, v):
        v = _num(v)
        if v is None:
            ws.write_blank(r, c, None)
        else:
            ws.write_number(r, c, float(v), ratio_fmt)

    r = 2
    for row in sparse_rows:
        pv = {p["corp_name"]: p["value"] for p in row["peer_company_values"] if p.get("corp_name")}
        ws.write(r, 0, row["group"])
        ws.write(r, 1, row["ratio_name_ko"])
        ws.write(r, 2, row["target_company"])
        _wnum(r, 3, row["target_value"])
        ws.write_number(r, 4, int(row["peer_count"]))
        for i, n in enumerate(peer_names):
            _wnum(r, 5 + i, pv.get(n))
        _wnum(r, t0, row["peer_median_reference"])
        ws.write(r, t0 + 1, row["target_rank_among_peers"] or "판정 보류(비교 불가)")
        ws.write(r, t0 + 2, row["sample_status"])
        ws.write(r, t0 + 3, "아니오(참고 비교)")
        ws.write(r, t0 + 4, row["comparison_note"], wrap)
        ws.write(r, t0 + 5, row["basis"], wrap)
        r += 1
    ws.freeze_panes(2, 0)
    ws.autofilter(1, 0, max(1, r - 1), len(headers) - 1)


def _methodology_loop3(ws, wb, target, meta, n_cand, n_succ, n_fail, bold, wrap):
    ws.set_column(0, 0, 26); ws.set_column(1, 1, 100)
    k = meta.get("iqr_fence_k", 1.5)
    mp = meta.get("min_peers", 5)
    lines = [
        ("문서", f"Ralph Loop 3 방법론 — {target['corp_name']} {meta['bsns_year']} 산업대비 비율 benchmark"),
        ("대상", f"{target['corp_name']}(종목 {target['stock_code']}, corp_code {target['corp_code']}, 업종 {target['induty_code']})"),
        ("benchmark pool", "비율별로 그 비율을 계산 가능한 peer만 pool에 포함. NOT_COMPUTABLE·CFS 실패 회사는 제외. n_companies=비율별 계산 가능 peer 수."),
        ("peer 요약", f"peer 후보 {n_cand} / CFS 성공 {n_succ} / CFS 실패 {n_fail}(CFS 사용불가 status=013 등으로 제외)."),
        ("leave-one-out", "대상 회사는 모든 비율의 benchmark 계산에서 제외(비교 대상값으로만 유지)."),
        ("통계", "mean·winsorized_mean·median·p25·p75·iqr·mad·std·min·max·n_companies 산출. 판정은 median/IQR 중심, 평균은 참고값."),
        ("판정 규칙", f"IQR fence(k={k}): 값 > p75+k·IQR → HIGH, 값 < p25−k·IQR → LOW, 그 외 NORMAL. n<{mp}(min_peers)면 peer 부족, IQR≤0이면 분포 부족, target 계정 부족이면 계산 불가."),
        ("보조 지표", "robust_z(=0.6745·(값−median)/MAD), percentile(pool 대비 위치)."),
        ("중앙값 대비 차이 표시", "'중앙값 대비 비율차이(%)'=(값−median)/|median| — median이 작으면 크게 보일 수 있음. '중앙값 대비 차이(%p·값)'=값−median — %비율 항목(수익성·안정성·운전자본)은 %p(×100), 회전율(배수) 항목은 값 차이. 둘을 함께 보아야 과장 해석을 피할 수 있음."),
        ("전부 NORMAL 해석", "모든 비율이 NORMAL은 안전 확정이 아니라 현재 peer universe·IQR fence 기준상 이상치로 분류되지 않았다는 의미. 추가 확인이 필요할 수 있음."),
        ("IQR fence 한계", "peer 분포 꼬리가 두껍거나 비교가능성 낮은 회사가 섞이면 fence가 넓어져 HIGH/LOW가 줄고 전부 NORMAL이 나올 수 있음. percentile·robust_z·benchmark_quality·peer 수 병행 해석 필요."),
        ("benchmark_quality", "STRONG(n≥2·min_peers, IQR>0, coverage 충분) / LIMITED(n 충분하나 IQR=0 또는 coverage 낮음) / WEAK(n이 min_peers는 넘으나 작음) / NOT_AVAILABLE(계산 불가). WEAK/LIMITED는 해석 주의. 매출채권·매입채무 비율은 순수계정 기준이라 n이 낮을 수 있음."),
        ("매핑 정책", "매출채권·매입채무는 순수 계정 기준. '및기타채권/및기타채무' fallback·재고자산 nm-fallback은 미사용. 불확실 매핑은 NOT_COMPUTABLE(mapping_not_confident)."),
        ("HIGH/LOW 의미", "산업 대비 높음/낮음일 뿐, 부정·오류·왜곡표시·좋음/나쁨이 아님. 검토 후보 신호이며 추가 확인이 필요."),
        ("비교가능성 한계", "대상 회사와 산업 peer 간 사업 구성·규모 차이로 단일 induty_code peer benchmark와 비교가능성 한계가 있을 수 있음."),
        ("추적성", "모든 값은 rcept_no/account_id/request_hash/raw snapshot으로 추적. pool 구성원은 benchmark_debug의 01 시트에 corp_code로 명시."),
    ]
    ws.write(0, 0, "항목", bold); ws.write(0, 1, "설명", bold)
    for i, (kk, v) in enumerate(lines, 1):
        ws.write(i, 0, kk); ws.write(i, 1, v, wrap)


def build_benchmark_debug_workbook(path: Path, *, target: dict, comparison_rows: list[dict],
                                   pool_details: list[dict], ratio_rows_all: list[dict],
                                   target_trace: list[dict], meta: dict,
                                   red_flag_assessment: dict | None = None) -> Path:
    """Loop 3 검증용 benchmark debug(전부 한글). Loop 15: 절대판정(red flag) 점검표 추가."""
    from . import compare as cmp
    path = _atomic_new_path(path)
    tmp = path.with_suffix(".xlsx.tmp")
    wb = xlsxwriter.Workbook(str(tmp), {"in_memory": True})
    bold = wb.add_format({"bold": True, "bg_color": "#DDDDDD", "border": 1})
    note = wb.add_format({"italic": True, "font_color": "#555555", "text_wrap": True})
    wrap = wb.add_format({"text_wrap": True, "valign": "top"})
    amt = wb.add_format({"num_format": "#,##0"})
    ratio_fmt = wb.add_format({"num_format": "0.0000"})
    z_fmt = wb.add_format({"num_format": "0.0000"})
    cmp_by_ratio = {r["ratio"]: r for r in comparison_rows}

    # 00_검증안내
    ws = wb.add_worksheet("00_검증안내")
    ws.set_column(0, 0, 24); ws.set_column(1, 1, 100)
    readme = [
        ("문서", "산업 benchmark 검증용 Debug — Ralph Loop 3 (사람 검증용)"),
        ("목적", "비율별 benchmark pool 구성·통계·대상 회사 comparison·label 산정근거·품질을 사람이 검증."),
        ("pool 원칙", "비율별 계산 가능 peer만 pool 포함. 대상 회사는 leave-one-out으로 제외(01 시트에서 포함/제외·사유 확인)."),
        ("판정", "median/IQR fence 기준. HIGH/LOW는 산업 대비 높음/낮음(좋음/나쁨 아님)."),
        ("추적성", "01 pool의 corp_code, 07 source_trace로 raw까지 추적. 통계는 유한값(NaN/inf 미유출)."),
    ]
    ws.write(0, 0, "항목", bold); ws.write(0, 1, "설명", bold)
    for i, (k, v) in enumerate(readme, 1):
        ws.write(i, 0, k); ws.write(i, 1, v, wrap)

    # 01_비율별_benchmark_pool
    ws = wb.add_worksheet("01_비율별_benchmark_pool")
    rows = []
    for pd in pool_details:
        for x in pd["included"]:
            rows.append([pd["ratio"], x["corp_code"], x["corp_name"], x["value"], "포함", ""])
        for x in pd["excluded"]:
            rows.append([pd["ratio"], x["corp_code"], x["corp_name"], None,
                         "제외(target)" if x["is_target"] else "제외", x["reason"]])
    _add_table(wb, ws, ["비율명", "기업코드", "기업명", "비율값", "포함/제외", "사유"],
               rows, header_fmt=bold, start_row=0, col_num_formats={3: ratio_fmt},
               widths=[16, 12, 24, 16, 12, 22])

    # 02_비율별_통계
    ws = wb.add_worksheet("02_비율별_통계")
    srows = []
    for pd in pool_details:
        st = pd["stats"]
        srows.append([pd["ratio"], st["n_companies"], st["mean"], st["winsorized_mean"], st["median"],
                      st["p25"], st["p75"], st["iqr"], st["mad"], st["std"], st["min"], st["max"]])
    _add_table(wb, ws, ["비율명", "n_companies", "mean(참고)", "winsorized_mean(참고)", "median",
                        "p25", "p75", "iqr", "mad", "std(참고)", "min", "max"],
               srows, header_fmt=bold, start_row=0,
               col_num_formats={c: ratio_fmt for c in range(2, 12)},
               widths=[16, 12, 14, 18, 14, 14, 14, 14, 14, 12, 14, 14])

    # 03_삼성전자_comparison
    ws = wb.add_worksheet(safe_sheet_name("03_", target["corp_name"], "_comparison"))
    crows = []
    for pd in pool_details:
        c = cmp_by_ratio.get(pd["ratio"], {})
        st = pd["stats"]
        crows.append([pd["ratio"], c.get("target_value"), st["median"], st["p25"], st["p75"], st["iqr"],
                      pd.get("upper_fence"), pd.get("lower_fence"), c.get("label"),
                      c.get("robust_z"), c.get("percentile"), c.get("deviation_rate")])
    _add_table(wb, ws, ["비율명", "대상회사값", "median", "p25", "p75", "iqr", "상단fence(p75+k·iqr)",
                        "하단fence(p25−k·iqr)", "label", "robust_z", "percentile", "deviation_rate"],
               crows, header_fmt=bold, start_row=0,
               col_num_formats={c: ratio_fmt for c in (1, 2, 3, 4, 5, 6, 7, 9, 10, 11)},
               widths=[16, 16, 14, 14, 14, 12, 20, 20, 22, 12, 12, 14])

    # 04_label_reason_상세 (Loop 3-B: %p·값 차이 + 해석 비고 보강)
    ws = wb.add_worksheet("04_label_reason_상세")
    pct_fmt = wb.add_format({"num_format": "+0.0%;-0.0%;0.0%"})
    signed_fmt = wb.add_format({"num_format": "+0.0000;-0.0000;0.0000"})
    lrows = []
    for pd in pool_details:
        c = cmp_by_ratio.get(pd["ratio"], {})
        basis = (f"대상값={_fmt(c.get('target_value'))}, 상단fence={_fmt(pd.get('upper_fence'))}, "
                 f"하단fence={_fmt(pd.get('lower_fence'))}, n={pd['stats']['n_companies']}")
        note_txt = c.get("interpret_note") or c.get("deviation_reason", "")
        lrows.append([pd["ratio"], c.get("label"), cmp.LABEL_KO.get(c.get("label"), ""),
                      c.get("deviation_rate"), c.get("deviation_pp_display"), c.get("robust_z"),
                      c.get("percentile"), c.get("benchmark_quality"), c.get("reason"),
                      note_txt, c.get("audit_comment"), basis])
    _add_table(wb, ws, ["비율명", "label", "판정(한글)", "중앙값 대비 비율차이(%)", "중앙값 대비 차이(%p·값)",
                        "robust_z", "percentile", "benchmark_quality", "판정 사유(reason)", "해석 비고",
                        "감사 관점 코멘트", "label 산정근거(fence)"],
               lrows, header_fmt=bold, start_row=0,
               col_num_formats={3: pct_fmt, 4: signed_fmt, 5: z_fmt, 6: z_fmt},
               widths=[16, 20, 14, 18, 20, 12, 12, 16, 40, 50, 50, 46])

    # 05_benchmark_quality
    ws = wb.add_worksheet("05_benchmark_quality")
    qrows = []
    for pd in pool_details:
        n = pd["stats"]["n_companies"]
        cov = (n / pd["cfs_success"]) if pd.get("cfs_success") else 0.0
        qrows.append([pd["ratio"], n, pd.get("cfs_success"), cov, pd["stats"]["iqr"],
                      pd["benchmark_quality"], pd["quality_reason"]])
    _add_table(wb, ws, ["비율명", "n_companies", "CFS 성공 peer 수", "coverage(n/CFS성공)", "iqr",
                        "benchmark_quality", "근거"],
               qrows, header_fmt=bold, start_row=0,
               col_num_formats={3: wb.add_format({"num_format": "0.0%"}), 4: ratio_fmt},
               widths=[16, 12, 16, 18, 14, 18, 50])

    # 06_NOT_COMPUTABLE_상세
    ws = wb.add_worksheet("06_NOT_COMPUTABLE_상세")
    nc = [r for r in ratio_rows_all if not r["computable"]]
    _add_table(wb, ws, ["기업코드", "기업명", "대상여부", "비율명", "사유(reason)", "분자source", "분모source"],
               [[r["corp_code"], r["corp_name"], r["is_target"], r["ratio"], r["reason"],
                 r["numerator_src"], r["denominator_src"]] for r in nc],
               header_fmt=bold, start_row=0, widths=[12, 22, 10, 16, 22, 40, 40])

    # 07_source_trace_샘플
    ws = wb.add_worksheet("07_source_trace_샘플")
    ws.write(0, 0, "대상 회사 전체 비율 입력값 — 각 계정은 전체_CFS_Long(별도 파일)에서 (기업코드+계정ID+rcept_no)로 raw까지 추적", note)
    _add_table(wb, ws, ["비율명", "분자값", "분자source", "분모값", "분모source", "비율값", "계산가능", "사유"],
               [[r["ratio"], r["numerator_value"], r["numerator_src"], r["denominator_value"],
                 r["denominator_src"], r["ratio_value"], ("가능" if r["computable"] else "불가"), r["reason"]]
                for r in target_trace],
               header_fmt=bold, start_row=1, col_num_formats={1: amt, 3: amt, 5: z_fmt},
               widths=[16, 18, 44, 18, 44, 12, 10, 22])

    # 08_red_flag_점검 (Loop 15): 절대판정 6종 산정근거(임계값·연산자·관측값·트리거) — 상대층 debug와 추적성 대칭.
    if red_flag_assessment:
        ws = wb.add_worksheet("08_red_flag_점검")
        ws.write(0, 0, "절대판정(red flag) 6종 점검 — 회사·산업 무관 절대 기준선. 임계값·연산자는 config(settings.yaml)에서 조달. "
                       "'위험 확정'이 아니라 검토 경고/점검 신호.", note)
        _add_table(wb, ws, ["red_flag", "연결 비율", "관측값(metric)", "연산자", "임계값", "관측 수치",
                            "판정", "트리거", "메시지"],
                   [[f.get("key"), f.get("linked_ratio"), f.get("metric"), f.get("op"), f.get("threshold"),
                     f.get("observed"), f.get("status"), ("예" if f.get("triggered") else "아니오"),
                     f.get("message")] for f in red_flag_assessment.get("flags", [])],
                   header_fmt=bold, start_row=1, col_num_formats={4: ratio_fmt, 5: ratio_fmt},
                   widths=[24, 14, 22, 8, 12, 18, 12, 8, 40])

    wb.close()
    os.replace(tmp, path)
    return path


def _fmt(v):
    if v is None:
        return "N/A"
    try:
        return f"{float(v):.4f}"
    except (TypeError, ValueError):
        return str(v)
