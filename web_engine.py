"""DARTLens 웹(Flask) — 읽기 전용 엔진 소비자 (Loop 20-A).

★ 설계 원칙 (CLAUDE.md / DESIGN_INVARIANTS.md INV-7):
  - 웹은 **읽기 전용 소비자**다. 계산 엔진(src/*)을 복제·수정하지 않는다.
    새 분석은 `src.ui_runner.run_new_analysis()` 로만 호출하고, 결과 표시는 이미 검증된
    `src.ui_helpers` 의 Excel 읽기 함수를 그대로 재사용한다(재구현 0, 값·판정 불변).
  - 이 모듈은 src/* 를 **import·호출만** 한다. src/* 파일은 한 줄도 바꾸지 않는다.
  - OpenDART 키는 화면 입력 → 세션 한정으로 엔진에 전달만 하고(파일/로그/화면 미저장),
    이 모듈은 키 값을 반환·로그하지 않는다.
  - ★로컬 전용 도구(app_flask.py 가 127.0.0.1 로만 바인딩).

이 모듈이 하는 일: (1) run_analysis — 엔진 호출 후 산출된 Excel을 읽어 표시용 dict 구성,
(2) read_report — 기존 리포트(basename)를 읽어 동일 표시용 dict 구성, (3) resolve_download —
다운로드 대상 경로 안전 검증, (4) env_key_present — .env 키 가용성 boolean(값 미노출).
"""
from __future__ import annotations

import math
from pathlib import Path

from src import config
from src import ui_helpers as uih

OUTPUT_DIR = config.PROJECT_ROOT / "output"


# --------------------------------------------------------------------------
# 표시용 변환 (DataFrame → Jinja 렌더용 순수 dict). 값은 읽기만 한다(INV-7).
# --------------------------------------------------------------------------
def _clean(v):
    if v is None:
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    return str(v)


def format_display_number(raw, decimals: int = 2) -> str:
    """표시 전용 숫자 포맷(Loop 24): full-precision 원본을 소수 {decimals}자리로 반올림한 문자열.

    ★엔진·저장값·계산은 불변 — 화면에 보이는 숫자만 반올림한다(정보 손실 0). 원본 full precision은
    호출부에서 title 툴팁 등으로 유지한다. 숫자가 아니면 원문 유지, 빈 값/NaN/inf는 빈 문자열.
    """
    if raw is None:
        return ""
    s = str(raw).strip()
    if s == "" or s.lower() == "nan":
        return ""
    try:
        f = float(s)
    except (TypeError, ValueError):
        return s                       # 텍스트(예: '계산 불가')는 그대로 표시
    if f != f or f in (float("inf"), float("-inf")):
        return ""
    text = f"{f:.{decimals}f}"
    if text.lstrip("-") in ("0", "0." + "0" * decimals):   # '-0.00' → '0.00' 정규화
        text = text.lstrip("-")
    return text


# Loop 24: 비율별 표시 단위 분류 — **비율명 기준(회사 무관)** 이라 INV-4(회사 하드코딩 금지) 위반이
# 아니다(16개 비율은 모든 회사 공통). 재무 관례: 이익률·부채·구성비 등은 %(×100), 배수·회전율은 '배',
# 운전자본비율은 음수가 가능해 무단위. 저장값·엔진 계산은 불변 — 화면 숫자 표기에만 쓰인다.
#   pct  = ×100 후 '%'   | mult = '배'   | plain/미등록 = 단위 없음
RATIO_UNIT = {
    "영업이익률": "pct", "순이익률": "pct", "ROA": "pct", "ROE": "pct",
    "부채비율": "pct", "부채비중": "pct", "차입금의존도": "pct",
    "매출채권비율": "pct", "재고자산비율": "pct", "매입채무비율": "pct",
    "유동비율": "mult", "이자보상배율": "mult",
    "총자산회전율": "mult", "재고자산회전율": "mult", "매출채권회전율": "mult",
    "운전자본비율": "plain",
}


def format_ratio_value(raw, ratio_name=None, decimals: int = 2) -> str:
    """표시 전용 비율 포맷(Loop 24): 2자리 반올림 + 비율 성격별 단위(pct=×100%, mult=배, plain=없음).

    ★엔진·저장값·계산 불변 — 화면 숫자만 변환한다(정보 손실 0). %형은 원비율×100(같은 값, 표기만
    다름)이며 원본 full precision은 호출부 title 툴팁으로 유지한다. 숫자가 아니면 원문, 빈/NaN은 ''.
    """
    kind = RATIO_UNIT.get((ratio_name or "").strip())
    if raw is None:
        return ""
    s = str(raw).strip()
    if s == "" or s.lower() == "nan":
        return ""
    try:
        f = float(s)
    except (TypeError, ValueError):
        return s                       # 텍스트(예: '계산 불가')는 그대로 표시
    if f != f or f in (float("inf"), float("-inf")):
        return ""
    if kind == "pct":
        f *= 100.0
    text = f"{f:.{decimals}f}"
    if text.lstrip("-") in ("0", "0." + "0" * decimals):   # '-0.00' → '0.00'
        text = text.lstrip("-")
    if kind == "pct":
        return text + "%"
    if kind == "mult":
        return text + "배"
    return text


def _df_to_table(df) -> dict:
    """DataFrame → {'columns': [...], 'rows': [[...], ...]} (NaN/None → '')."""
    if df is None or getattr(df, "empty", True):
        return {"columns": [], "rows": []}
    cols = [str(c) for c in df.columns]
    rows = [[_clean(r[c]) for c in df.columns] for _, r in df.iterrows()]
    return {"columns": cols, "rows": rows}


def _safe_table(final_path, reader, *args) -> dict:
    """읽기 실패를 조용히 삼키지 않고 빈 표+note 로 표면화(INV-5 정신)."""
    try:
        return _df_to_table(reader(final_path, *args))
    except Exception as e:  # noqa: BLE001 — 시트 없음 등은 note 로 드러냄
        return {"columns": [], "rows": [], "note": f"시트를 읽지 못했습니다 ({type(e).__name__})"}


def read_report(final_path, debug_path=None) -> dict:
    """산출된(또는 기존) 최종 리포트 Excel을 읽어 표시용 dict 구성. 계산 재실행 없음(읽기 전용)."""
    final_path = Path(final_path)
    summary = uih.extract_summary(final_path)
    status_token = uih.report_status_token(final_path)

    # 02~05 비율 그룹(수익성/안정성/운전자본/회전율) — 각 시트를 표로.
    groups = []
    for tab_name, sheet in uih.RATIO_TAB_SHEETS.items():
        groups.append({"name": tab_name, "sheet": sheet,
                       **_safe_table(final_path, uih.ratio_sheet_df, sheet)})

    has_sparse = uih.has_sparse_sheet(final_path)
    debug_name = Path(debug_path).name if debug_path else None

    return {
        "ok": True,
        "company": summary.get("company") or "-",
        "year": summary.get("year") or "-",
        "status_token": status_token,
        "status_display": uih.status_display(status_token),
        "summary": summary,
        "interpretation": uih.build_interpretation(final_path),
        "has_sparse": has_sparse,
        "sparse_notice": (
            "동종산업 peer 수가 최소 benchmark 기준에 미달한 경우, HIGH/LOW/NORMAL 판정은 보류하고 "
            "09_제한적_peer_비교 표에서 실제 peer 회사별 참고 비교를 제공합니다."),
        "groups": groups,
        "peer_list": _safe_table(final_path, uih.sheet_to_df, "06_Peer_List", "기업코드"),
        "excluded": _safe_table(final_path, uih.sheet_to_df, "08_계산불가_및_제외사유", "구분"),
        # 09시트: 상단 병합 안내배너(row0)를 헤더로 오인하지 않도록 실제 헤더행('비율명' 포함)을
        # 탐지해 읽는다. 읽기 전용·값 불변(INV-7) — 계산이 아니라 표시용 파싱 보정일 뿐이다.
        "sparse": (_safe_table(final_path, uih.sheet_to_df, uih.SPARSE_SHEET_NAME, "비율명")
                   if has_sparse else {"columns": [], "rows": []}),
        "final_name": final_path.name,
        "debug_name": debug_name,
    }


# --------------------------------------------------------------------------
# 새 분석 실행 (엔진 호출) — src.ui_runner 위임. 키는 세션 한정 전달, 미저장/미로그.
# --------------------------------------------------------------------------
def run_analysis(company: str, year, api_key: str | None = None) -> dict:
    """엔진(ui_runner.run_new_analysis)을 호출하고, 성공 시 산출 Excel을 읽어 표시용 dict 반환.

    반환:
      성공 → {'ok': True, 'message': str, 'report': <read_report dict>}
      실패 → {'ok': False, 'message': str}   (엔진 halt·식별 실패 사유를 그대로 전달)
    """
    from src import ui_runner  # lazy: 엔진 import 체인은 실행 시에만
    res = ui_runner.run_new_analysis(company, year, api_key=api_key)
    if not res.get("ok"):
        return {"ok": False, "message": res.get("message") or "분석 실패"}
    report = read_report(res["final"], res.get("debug"))
    return {"ok": True, "message": res.get("message") or "분석 완료", "report": report}


# --------------------------------------------------------------------------
# 다운로드 경로 안전 검증 / 키 가용성
# (list_recent 는 Loop 22에서 랜딩의 '최근 산출물' 목록 제거와 함께 미사용이 되어 삭제.
#  최신탐지 원본 함수 uih.list_report_candidates 는 그대로 보존 — 테스트가 사용.)
# --------------------------------------------------------------------------
def env_key_present() -> bool:
    """OpenDART 키가 .env/환경에서 해석 가능한지 여부만 반환한다.

    키 '값'은 절대 반환·로그하지 않는다(가용성 boolean만). 입력 흐름에서 1단계(키 입력)를
    건너뛸지 판단하는 용도. config.get_api_key()는 키가 없으면 ConfigError를 올린다.
    """
    try:
        config.get_api_key()
        return True
    except Exception:  # noqa: BLE001 — 키 부재/설정 오류는 '없음'으로 처리(값 미노출)
        return False


def resolve_download(filename: str) -> Path | None:
    """다운로드 요청 basename 을 output 폴더 내부의 실제 .xlsx 로만 해석(경로 이탈 차단).

    - 디렉터리 구분자/상위 경로 포함 시 거부(traversal 방지).
    - output/ 밖으로 벗어나거나 존재하지 않으면 None.
    """
    name = (filename or "").strip()
    if not name or name.endswith(".tmp") or not name.endswith(".xlsx"):
        return None
    if "/" in name or "\\" in name or name != Path(name).name:
        return None
    path = (OUTPUT_DIR / name).resolve()
    out_root = OUTPUT_DIR.resolve()
    if out_root != path.parent or not path.exists():
        return None
    return path
