"""DARTLens — 로컬 웹 UI (Flask). Loop 20-A: Streamlit → Flask 재구축 1단계.

★ 설계 원칙:
  - 이 파일은 **라우팅/기동만** 담당한다. 계산은 web_engine 을 통해 검증된 엔진(src/*)에 위임하며,
    src/* 는 import·호출만 하고 한 줄도 수정하지 않는다(DESIGN_INVARIANTS INV-7).
  - ★로컬 전용 바인딩(127.0.0.1). 외부 노출 금지.
  - OpenDART 키는 폼 입력 → 서버 세션 메모리에만 보관(파일/로그/화면/산출물/쿠키 미저장),
    엔진에는 세션 한정으로 전달만 한다.

흐름(Loop 22 — 3페이지 단계형):
  GET  /            랜딩(히어로 + 3단계 미리보기 + CTA). 입력폼 없음.
  GET  /apikey      입력 1/2 — API 키. .env/세션 키가 있으면 2단계로 건너뜀(?edit=1이면 폼 강제).
  POST /apikey      키를 세션 메모리에 저장 → 2단계로.
  GET  /company     입력 2/2 — 회사/연도(세션값 프리필). 키 없으면 1단계로 유도.
  POST /company     회사/연도 → 엔진 실행 → 결과. 입력값 세션 보존.
  POST /company/back 현재 입력을 세션에 저장하고 1단계로(뒤로가기 입력 보존).
  GET  /report      기존 리포트(basename) 읽기 전용 보기.
  GET  /download    산출 Excel 다운로드(basename, output/ 내부로만 제한).
  GET  /healthz     상태 체크.

이전 Streamlit UI(app.py)는 Loop 20-C에서 제거됨 — 롤백은 git 이력(`git checkout <ref> -- app.py`). 실행: python app_flask.py
"""
from __future__ import annotations

import secrets
import socket
import threading

from flask import (Flask, abort, g, redirect, render_template, request,
                   send_from_directory, url_for)

import web_engine

app = Flask(__name__)

YEARS = [2025, 2024]        # UI 선택지(회사 하드코딩 아님 — 연도 선택 목록)
DEFAULT_YEAR = 2025


# ── 세션 상태 (서버 메모리 전용) ─────────────────────────────────────────────
# 로컬 단일 사용자 도구다. API 키/입력값은 서버 프로세스 메모리(_SESSIONS)에만 두고, 쿠키에는
# 불투명 sid 만 담는다. 키 값은 쿠키·파일·로그·화면·산출물 어디에도 저장하지 않는다(세션 메모리만).
_SESSIONS: dict[str, dict] = {}
_SID_COOKIE = "dl_sid"


def _session() -> dict:
    """요청의 sid 쿠키로 서버 세션 dict 를 찾거나 새로 만든다(신규면 after_request 가 쿠키 설정)."""
    sid = request.cookies.get(_SID_COOKIE)
    if not sid or sid not in _SESSIONS:
        sid = secrets.token_urlsafe(18)
        _SESSIONS[sid] = {}
        g._dl_new_sid = sid
    g._dl_sid = sid
    return _SESSIONS[sid]


@app.after_request
def _persist_sid(resp):
    sid = getattr(g, "_dl_new_sid", None)
    if sid:
        # HttpOnly: JS 접근 차단. 로컬 전용이라 Secure 미설정(127.0.0.1 http).
        resp.set_cookie(_SID_COOKIE, sid, httponly=True, samesite="Lax")
    return resp


def _key_available(sess) -> bool:
    """세션에 키가 있거나 .env 에 키가 있으면 True(값은 확인만, 미노출)."""
    return bool(sess.get("api_key")) or web_engine.env_key_present()


# ── 라우트 ───────────────────────────────────────────────────────────────────
@app.get("/")
def index():
    """랜딩 — 로고(좌상단 헤더) + 히어로 + 3단계 미리보기 + CTA. 입력폼/최근목록 없음."""
    return render_template("index.html")


@app.get("/apikey")
def apikey():
    """입력 1/2 — OpenDART API 키. .env/세션에 이미 키가 있으면 2단계로 건너뛴다
    (?edit=1 이면 키 변경을 위해 폼을 강제로 보여준다)."""
    sess = _session()
    editing = request.args.get("edit") == "1"
    if _key_available(sess) and not editing:
        return redirect(url_for("company"))
    return render_template("apikey.html",
                           key_set=bool(sess.get("api_key")),
                           env_key=web_engine.env_key_present())


@app.post("/apikey")
def apikey_submit():
    sess = _session()
    key = (request.form.get("api_key") or "").strip()
    if key:
        sess["api_key"] = key          # 서버 메모리 세션에만 보관(미로그/미저장)
    # 키가 비어도 .env/기존 세션 키가 있으면 진행 가능. 둘 다 없으면 폼으로 되돌린다.
    if not _key_available(sess):
        return render_template("apikey.html", key_set=False, env_key=False,
                               error="API 키를 입력하세요. (.env에 키가 없으면 필수)"), 400
    return redirect(url_for("company"))


@app.get("/company")
def company():
    """입력 2/2 — 회사/연도. 키가 없으면 1단계로 유도. 입력값은 세션에서 프리필(뒤로/재조회 보존)."""
    sess = _session()
    if not _key_available(sess):
        return redirect(url_for("apikey"))
    return render_template("company.html", years=YEARS,
                           selected_year=sess.get("year", DEFAULT_YEAR),
                           company=sess.get("company", ""))


@app.post("/company")
def company_submit():
    sess = _session()
    company_in = (request.form.get("company") or "").strip()
    year = (request.form.get("year") or str(DEFAULT_YEAR)).strip()
    try:
        selected_year = int(year)
    except ValueError:
        selected_year = DEFAULT_YEAR
    # 입력값 보존(뒤로가기/재조회 시 프리필)
    sess["company"] = company_in
    sess["year"] = selected_year

    if not _key_available(sess):
        return redirect(url_for("apikey"))
    if not company_in:
        return render_template("company.html", years=YEARS,
                               selected_year=selected_year, company=company_in,
                               error="회사명 또는 6자리 종목코드를 입력하세요."), 400

    # 키는 받되 저장하지 않는다 — 세션값을 엔진에 세션 한정 전달(None이면 엔진이 .env 키 사용).
    api_key = sess.get("api_key") or None
    result = web_engine.run_analysis(company_in, str(selected_year), api_key=api_key)
    if not result.get("ok"):
        # 엔진 halt·회사 식별 실패 사유를 조용히 삼키지 않고 그대로 표면화(삼성 fallback 없음).
        return render_template("company.html", years=YEARS,
                               selected_year=selected_year, company=company_in,
                               error=result.get("message")), 200
    return render_template("result.html", r=result["report"], message=result.get("message"))


@app.post("/company/back")
def company_back():
    """뒤로가기 — 현재 입력을 세션에 저장하고 1단계로(입력값 보존). formnovalidate 로 미완성 입력도 보존."""
    sess = _session()
    sess["company"] = (request.form.get("company") or "").strip()
    try:
        sess["year"] = int((request.form.get("year") or str(DEFAULT_YEAR)).strip())
    except ValueError:
        sess["year"] = DEFAULT_YEAR
    return redirect(url_for("apikey", edit=1))


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
