"""Ralph Loop 4 UI runner — '새 분석 실행' wrapper (Loop 11: 일반화).

기존 분석 엔진을 **변경하지 않고** multi_target_runner.run_target 를 호출한다(캐시 우선·결정적,
새 timestamp 산출물 생성, 기존 파일 미덮어쓰기). 사용자가 입력한 **회사명 또는 6자리 종목코드**와
**사업연도**를 그대로 pipeline까지 전달한다(삼성전자/2025 고정 게이트 제거).

회사/종목코드 리터럴을 코드에 두지 않는다(CLAUDE.md 규칙#1). 입력 해석은 정확일치만 하며
(fuzzy 금지, safety-rules §3), 실패는 조용히 삼키지 않고 message로 표면화한다(삼성 fallback 없음).
sidebar API key는 os.environ에 세션 한정으로 주입하며 파일에 저장하지 않는다(값 미출력).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from . import config, corp_codes
from . import multi_target_runner as mtr
from .dart_client import DartClient, DartError, StopConditionError

_STOCK_RE = re.compile(r"^\d{6}$")


def normalize_input(text: str) -> str:
    return (text or "").strip()


def _corpcode_client(settings, paths, api_key) -> DartClient:
    """corpCode 마스터 조회용 DartClient(엔진 build_dataset와 동일 파라미터, 캐시 우선)."""
    return DartClient(
        api_key, paths["raw"], paths["cache"], config.PROJECT_ROOT,
        timeout=int(settings.get("request_timeout_sec", 20)),
        delay=float(settings.get("request_delay_sec", 0.0)),
        max_retries=int(settings.get("max_retries", 3)),
    )


def resolve_stock_code(raw: str, settings, paths, api_key) -> str:
    """입력(6자리 종목코드 또는 정확 회사명)을 종목코드로 해석. 회사 하드코딩 없음.

    - 6자리 숫자면 종목코드로 간주하고 그대로 사용(엔진 resolve_by_stock가 검증).
    - 그 외는 상장 corp master에서 **정확 회사명** 일치만 허용. 0건/복수면 추측하지 않고
      corp_codes.ResolveError(STOP) 를 올린다.
    """
    raw = normalize_input(raw)
    if _STOCK_RE.match(raw):
        return raw
    records = corp_codes.parse_corp_codes(
        _corpcode_client(settings, paths, api_key).get_corpcode_xml())
    return corp_codes.resolve_by_name(records, raw)["stock_code"]


def run_new_analysis(company_or_stock: str, year, api_key: str | None = None) -> dict:
    """새 분석 실행. 반환: {'ok': bool, 'final': Path|None, 'debug': Path|None, 'message': str}.

    사용자 입력(회사/연도)을 그대로 엔진(multi_target_runner.run_target)에 전달한다. 엔진이
    halt하거나 회사 식별이 실패하면 그 사유를 message로 전달한다(조용한 성공처리/삼성 fallback 없음).
    """
    raw = normalize_input(company_or_stock)
    if not raw:
        return {"ok": False, "final": None, "debug": None,
                "message": "회사명 또는 6자리 종목코드를 입력하세요."}
    try:
        bsns_year = int(str(year).strip())
    except (TypeError, ValueError):
        return {"ok": False, "final": None, "debug": None,
                "message": f"사업연도를 확인하세요(입력: {year})."}

    # sidebar 키는 세션 한정 주입(파일 미기록). 값은 로그/화면에 출력하지 않는다.
    if api_key and api_key.strip():
        os.environ[config.KEY_NAME] = api_key.strip()

    settings = config.load_settings()
    paths = config.resolve_paths(settings)
    try:
        key = config.get_api_key()  # 없으면 ConfigError
    except config.ConfigError:
        return {"ok": False, "final": None, "debug": None,
                "message": "OpenDART API Key가 없습니다. .env 또는 sidebar에 키를 입력하세요."}

    try:
        stock_code = resolve_stock_code(raw, settings, paths, key)
    except corp_codes.ResolveError as e:
        return {"ok": False, "final": None, "debug": None, "message": f"회사 식별 실패: {e}"}
    except (StopConditionError, DartError) as e:
        return {"ok": False, "final": None, "debug": None,
                "message": f"corpCode 마스터 조회 실패: {e}"}

    # 엔진 미변경: 범용 run_target 호출(삼성 tripwire 미사용, 회사 식별 파일명으로 산출물 생성).
    row = mtr.run_target(stock_code, bsns_year, settings, paths, key, industry_hint="UI 입력")
    status = row.get("status")
    if status in ("PASS", "PASS_WITH_WARNINGS") and row.get("final_report_path"):
        note = f" · {row['notes']}" if row.get("notes") else ""
        return {"ok": True,
                "final": Path(row["final_report_path"]),
                "debug": Path(row["debug_report_path"]) if row.get("debug_report_path") else None,
                "message": f"새 분석 완료: {row.get('target_name') or stock_code} · {bsns_year} · {status}{note}"}
    return {"ok": False, "final": None, "debug": None,
            "message": f"분석 실패: {row.get('fail_reason') or status or '알 수 없는 오류'}"}
