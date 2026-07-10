"""Loop 12 스크린샷 하네스 — 제품 코드 아님(harness 격리).

app.py의 **실제 render 함수를 그대로 호출**해 3개 화면을 결정적으로 렌더한다(?shot=).
실제 산출물(output/*.xlsx)의 데이터를 읽어 표시하며, 계산·엔진·app.py 로직을 건드리지 않는다.
API key 입력칸은 빈 password(마스킹)로 노출 0. 스크린샷 재현용일 뿐 배포 대상 아님.

실행: streamlit run harness/screenshot_app.py  (?shot=landing|result|sparse)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import glob

import streamlit as st

import app as A  # app.py의 실제 render 함수 재사용(로직 불변)
from src import config
from src import ui_helpers as uih

OUT = config.PROJECT_ROOT / "output"


def _latest(company: str):
    fs = sorted(glob.glob(str(OUT / f"{company}_산업대비_이상징후_리포트_2025_*.xlsx")))
    return fs[-1] if fs else None


def _render_report_for(company: str):
    p = _latest(company)
    if not p:
        st.error(f"산출물 없음: {company}")
        return
    dbg = uih.find_debug_for_report(OUT, p, 2025)
    A.render_report(p, dbg, pair_status="matched" if dbg else "debug_missing",
                    pair_ts=uih.timestamp_from_name(p))


def main():
    st.set_page_config(page_title=A.APP_PAGE_TITLE, layout="wide")
    shot = st.query_params.get("shot", "landing")
    A.render_hero()
    A.render_sidebar()  # 빈 API key 칸(마스킹) 노출, 실제 키 값 없음
    if shot == "result":
        _render_report_for("한화솔루션")   # HIGH 1건 화면
    elif shot == "sparse":
        _render_report_for("현대자동차")   # peer 부족 → sparse 09시트 안내
    elif shot == "redflag":
        _render_report_for("태영건설")     # 상대=정상 + 절대=경고 (red flag)
    else:
        A.render_landing()


main()
