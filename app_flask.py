"""DARTLens — 로컬 웹 UI (Flask). Loop 20-A: Streamlit → Flask 재구축 1단계.

★ 설계 원칙:
  - 이 파일은 **라우팅/기동만** 담당한다. 계산은 web_engine 을 통해 검증된 엔진(src/*)에 위임하며,
    src/* 는 import·호출만 하고 한 줄도 수정하지 않는다(DESIGN_INVARIANTS INV-7).
  - ★로컬 전용 바인딩(127.0.0.1). 외부 노출 금지.
  - OpenDART 키는 폼 입력 → 엔진에 세션 한정 전달만(파일/로그/화면 미저장).
  - 디자인(색·타이포·판정 배지)은 Loop 20-B. 여기서는 기능 확인용 최소 HTML.

라우트:
  GET  /          랜딩(입력 폼 + 최근 산출물)
  POST /analyze   회사/연도/키 → 엔진 실행 → 결과 표시
  GET  /report    기존 리포트(basename) 읽기 전용 보기
  GET  /download  산출 Excel 다운로드(basename, output/ 내부로만 제한)
  GET  /healthz   상태 체크

이전 Streamlit UI(app.py)는 Loop 20-C에서 제거됨 — 롤백은 git 이력(`git checkout <ref> -- app.py`). 실행: python app_flask.py
"""
from __future__ import annotations

import socket
import threading

from flask import (Flask, abort, render_template, request,
                   send_from_directory, url_for)

import web_engine

app = Flask(__name__)

YEARS = [2025, 2024]        # UI 선택지(회사 하드코딩 아님 — 연도 선택 목록)
DEFAULT_YEAR = 2025


# ── 라우트 ───────────────────────────────────────────────────────────────────
@app.get("/")
def index():
    return render_template("index.html", recent=web_engine.list_recent(),
                           years=YEARS, selected_year=DEFAULT_YEAR)


@app.post("/analyze")
def analyze():
    company = (request.form.get("company") or "").strip()
    year = (request.form.get("year") or str(DEFAULT_YEAR)).strip()
    # ★ 키는 받되 저장하지 않는다 — 엔진에 세션 한정 전달만 하고 이 지역변수 밖으로 새지 않는다.
    api_key = (request.form.get("api_key") or "").strip()

    try:
        selected_year = int(year)
    except ValueError:
        selected_year = DEFAULT_YEAR

    if not company:
        return render_template("index.html", recent=web_engine.list_recent(),
                               years=YEARS, selected_year=selected_year,
                               error="회사명 또는 6자리 종목코드를 입력하세요.", company=company), 400

    result = web_engine.run_analysis(company, year, api_key=api_key or None)
    if not result.get("ok"):
        # 엔진 halt·회사 식별 실패 사유를 조용히 삼키지 않고 그대로 표면화(삼성 fallback 없음).
        return render_template("index.html", recent=web_engine.list_recent(),
                               years=YEARS, selected_year=selected_year,
                               error=result.get("message"), company=company), 200

    return render_template("result.html", r=result["report"], message=result.get("message"))


@app.get("/report")
def report():
    """기존 리포트(output/<basename>.xlsx)를 읽어 결과 표시 — 엔진 미실행, 파일만 읽음(읽기 전용)."""
    path = web_engine.resolve_download(request.args.get("file", ""))
    if path is None:
        abort(404)
    return render_template("result.html", r=web_engine.read_report(path), message=None)


@app.get("/download")
def download():
    """산출 Excel 다운로드. basename 을 output/ 내부의 실제 .xlsx 로만 해석(경로 이탈 차단)."""
    path = web_engine.resolve_download(request.args.get("file", ""))
    if path is None:
        abort(404)
    return send_from_directory(path.parent, path.name, as_attachment=True)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


# ── 서버 기동 (로컬 전용) ─────────────────────────────────────────────────────
def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((host, port)) == 0


def _find_free_port(host: str, start: int, tries: int = 20) -> int:
    for port in range(start, start + tries):
        if _port_in_use(host, port):
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    return start


def _open_browser_when_ready(host: str, port: int) -> None:
    import time
    import webbrowser

    for _ in range(40):  # 최대 ~10초 대기 후 브라우저 오픈
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((host, port)) == 0:
                break
        time.sleep(0.25)
    webbrowser.open(f"http://{host}:{port}")


if __name__ == "__main__":
    import os

    host = "127.0.0.1"  # ★로컬 전용. 0.0.0.0 금지(외부 노출 방지).
    port = int(os.environ.get("DARTLENS_WEB_PORT") or _find_free_port(host, 5000))
    print("=" * 60)
    print("  DARTLens — 동종산업대비 재무 이상징후 분석기 (로컬 웹 UI)")
    print(f"  브라우저에서 열기:  http://{host}:{port}")
    print("  ★이 창을 닫지 마세요 — 창이 서버를 유지합니다.")
    print("=" * 60, flush=True)
    if os.environ.get("DARTLENS_OPEN_BROWSER") == "1":
        threading.Thread(target=_open_browser_when_ready, args=(host, port), daemon=True).start()
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
