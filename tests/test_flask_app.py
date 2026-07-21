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


def test_landing_renders_form():
    r = _client().get("/")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    # 문구(20-B: '분석 시작하기')가 아니라 폼 필드 존재로 검증 → 디자인 카피 변경에 견고.
    assert 'name="company"' in body and 'name="year"' in body


def test_download_rejects_traversal_and_missing():
    """output/ 밖 경로·상위 이탈·비 .xlsx·미존재 파일은 모두 404(조용한 노출 금지)."""
    c = _client()
    for bad in ["../app.py", "..\\..\\.env", "nonexistent.xlsx", "foo.txt", ""]:
        assert c.get("/download", query_string={"file": bad}).status_code == 404, bad


def test_report_rejects_bad_file():
    assert _client().get("/report", query_string={"file": "../app.py"}).status_code == 404
