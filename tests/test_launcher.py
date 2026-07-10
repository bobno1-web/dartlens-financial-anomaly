"""Ralph Loop 4-B: 원클릭 런처 파일 존재/내용 smoke. (실제 서버는 띄우지 않음)"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(name):
    return (ROOT / name).read_text(encoding="utf-8", errors="replace")


def test_bat_exists_and_launches_streamlit():
    assert (ROOT / "run_app.bat").exists()
    t = _read("run_app.bat")
    assert "streamlit run app.py" in t          # 올바른 실행 명령
    assert "%~dp0" in t                          # 스크립트 위치 기준으로 루트 이동
    assert "pause" in t.lower()                  # 오류 시 창 유지
    assert "app.py" in t                         # app.py 존재 확인 로직


def test_bat_does_not_touch_env_or_print_key():
    low = _read("run_app.bat").lower()
    assert ".env" not in low                     # .env 읽기/수정 명령 없음
    assert "opendart_api_key" not in low         # key 이름/값 미노출


def test_ps1_if_present_launches_streamlit_and_is_key_safe():
    p = ROOT / "run_app.ps1"
    if not p.exists():
        return  # .ps1은 선택 구현
    t = p.read_text(encoding="utf-8", errors="replace")
    low = t.lower()
    assert "streamlit run app.py" in t
    assert ".env" not in low and "opendart_api_key" not in low


def test_bat_does_not_force_auto_install():
    # requirements 설치는 '안내'만, 자동 강제 설치(pip install 실행)는 없어야 함
    low = _read("run_app.bat").lower()
    assert "pip install -r requirements.txt" in low   # 안내 문구로 포함
    # 자동 실행 라인(줄 시작이 설치 명령)이 아니라 echo 안내인지 확인
    for line in _read("run_app.bat").splitlines():
        s = line.strip().lower()
        if s.startswith("python -m pip install") or s.startswith("pip install"):
            raise AssertionError("런처가 pip install을 자동 실행함(안내만 해야 함): " + line)
