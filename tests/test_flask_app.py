"""Loop 20-A: Flask 앱 최소 스모크. 엔진(OpenDART) 미호출 — 라우팅·안전 가드만 검증.

무거운/네트워크 경로(POST /analyze → 엔진)는 여기서 다루지 않는다(수동/통합 검증). 여기서는
서버 기동 없이 test_client 로 헬스체크·랜딩 렌더·다운로드 경로탐색 차단만 빠르게 확인한다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app_flask  # noqa: E402  (sys.path 조정 후 import)


def _client():
    return app_flask.app.test_client()


def test_healthz_ok():
    r = _client().get("/healthz")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}


def test_landing_has_cta_no_form():
    """Loop 22: 랜딩은 입력폼을 두지 않는다(폼은 2단계로 이동). CTA로 흐름에 진입한다."""
    r = _client().get("/")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'name="company"' not in body          # 랜딩에 회사 입력폼 없음
    assert "/apikey" in body                      # CTA → 1단계
    assert "분석 시작하기" in body


def test_apikey_skips_when_key_in_session():
    """API 키 세션 유지: 세션에 키가 있으면 GET /apikey 는 2단계(/company)로 건너뛴다
    (재조회 시 키 재입력 불필요)."""
    c = _client()
    c.post("/apikey", data={"api_key": "dummy-session-key"})   # 엔진 미호출, 세션 저장만
    r = c.get("/apikey")                                        # follow_redirects=False
    assert r.status_code == 302
    assert "/company" in r.headers.get("Location", "")


def test_company_step_shows_form_after_key():
    """키가 세션에 있으면 2단계에서 회사/연도 폼이 렌더된다."""
    c = _client()
    c.post("/apikey", data={"api_key": "dummy-session-key"})
    r = c.get("/company")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'name="company"' in body and 'name="year"' in body


def test_back_preserves_inputs():
    """뒤로가기 입력값 보존: /company/back 로 저장한 회사/연도가 이후 /company 프리필에 반영된다."""
    c = _client()
    c.post("/apikey", data={"api_key": "dummy-session-key"})
    c.post("/company/back", data={"company": "태영건설", "year": "2024"})  # 미제출 입력 보존
    r = c.get("/company")
    body = r.get_data(as_text=True)
    assert 'value="태영건설"' in body           # 회사명 프리필
    assert '<option value="2024" selected' in body  # 연도 프리필


def test_download_rejects_traversal_and_missing():
    """output/ 밖 경로·상위 이탈·비 .xlsx·미존재 파일은 모두 404(조용한 노출 금지)."""
    c = _client()
    for bad in ["../app.py", "..\\..\\.env", "nonexistent.xlsx", "foo.txt", ""]:
        assert c.get("/download", query_string={"file": bad}).status_code == 404, bad


def test_report_rejects_bad_file():
    assert _client().get("/report", query_string={"file": "../app.py"}).status_code == 404
