"""Ralph Loop 4-B → Loop 20: 원클릭 런처 파일 존재/내용 smoke. (실제 서버는 띄우지 않음)

Loop 20: 기본 웹 UI가 Streamlit → Flask 로 전환됨(20-C에서 Streamlit app.py·run_streamlit.bat 제거).
  - run_app.bat / run_app.ps1 : Flask(python app_flask.py) 실행을 단언.
  - 키 안전(.env 미접근·키 이름 미노출)·자동설치 금지 단언은 그대로 유지.
  - Streamlit 롤백은 git 이력(예: main 커밋 3e0d1f7)에서 `git checkout <ref> -- app.py` 로 복구.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(name):
    return (ROOT / name).read_text(encoding="utf-8", errors="replace")


def test_bat_exists_and_launches_flask():
    assert (ROOT / "run_app.bat").exists()
    t = _read("run_app.bat")
    assert "%PYCMD% app_flask.py" in t           # 올바른 실행 명령(Flask, python/py 자동선택)
    assert "%~dp0" in t                          # 스크립트 위치 기준으로 루트 이동
    assert "pause" in t.lower()                  # 오류 시 창 유지
    assert "app_flask.py" in t                   # app_flask.py 존재 확인 로직


def test_bat_is_ascii_only():
    """Loop 21 회귀 가드: run_app.bat 은 ASCII 전용이어야 한다.
    한글 등 멀티바이트가 들어가면 한국어 Windows(OEM CP949)에서 cmd.exe 가 chcp 65001 이후
    배치 파일의 바이트 위치를 잃고 라인을 오파싱한다 → echo 가 떨어져 나가 requirements.txt 가
    메모장으로 열리거나 'org' 류 미인식 명령 오류가 난다(사람 보고 증상). 메시지는 ASCII로 유지하고
    한국어 콘솔 출력은 app_flask.py(파이썬 stdout + chcp 65001)에 맡긴다."""
    raw = (ROOT / "run_app.bat").read_bytes()
    nonascii = [b for b in raw if b > 0x7F]
    assert not nonascii, f"run_app.bat 에 비ASCII 바이트 {len(nonascii)}개 — 더블클릭 실행 깨짐 위험"


def test_bat_does_not_touch_env_or_print_key():
    low = _read("run_app.bat").lower()
    assert ".env" not in low                     # .env 읽기/수정 명령 없음
    assert "opendart_api_key" not in low         # key 이름/값 미노출


def test_ps1_if_present_launches_flask_and_is_key_safe():
    p = ROOT / "run_app.ps1"
    if not p.exists():
        return  # .ps1은 선택 구현
    t = p.read_text(encoding="utf-8", errors="replace")
    low = t.lower()
    assert "app_flask.py" in t                   # Flask 앱 기동(python/py 자동선택: `& $PY app_flask.py`)
    assert ".env" not in low and "opendart_api_key" not in low


def test_no_streamlit_app_remnant():
    """Loop 20 마무리: Streamlit 재구축 완료 — Streamlit 진입점 app.py·롤백 런처 run_streamlit.bat 은
    제거되어야 한다(롤백은 git 이력). Flask 진입점 app_flask.py 만 남는다."""
    assert not (ROOT / "app.py").exists(), "Streamlit app.py 제거됨이어야 함(롤백: git checkout <ref> -- app.py)"
    assert not (ROOT / "run_streamlit.bat").exists(), "Streamlit 롤백 런처 run_streamlit.bat 제거됨이어야 함"
    assert (ROOT / "app_flask.py").exists(), "Flask 진입점 app_flask.py 는 있어야 함"


def test_bat_does_not_force_auto_install():
    # requirements 설치는 '안내'만, 자동 강제 설치(pip install 실행)는 없어야 함
    low = _read("run_app.bat").lower()
    assert "pip install -r requirements.txt" in low   # 안내 문구로 포함
    # 자동 실행 라인(줄 시작이 설치 명령)이 아니라 echo 안내인지 확인
    for line in _read("run_app.bat").splitlines():
        s = line.strip().lower()
        if s.startswith("python -m pip install") or s.startswith("pip install"):
            raise AssertionError("런처가 pip install을 자동 실행함(안내만 해야 함): " + line)
