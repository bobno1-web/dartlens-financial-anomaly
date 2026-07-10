"""Ralph Loop 4: Streamlit UI MVP (Loop 11: 새 분석 일반화).

검증된 분석 엔진을 로컬 웹 UI로 감싼다. 분석 로직은 변경하지 않고 산출물 Excel을 읽어
표시하거나(최근 결과 불러오기), 엔진(multi_target_runner.run_target)을 호출한다(새 분석 실행 —
사용자가 입력한 회사/연도를 그대로 전달). API key는 화면/로그/산출물/파일에 저장·출력하지 않는다.

실행:  streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

from src import config
from src import ui_helpers as uih

OUTPUT_DIR = config.PROJECT_ROOT / "output"

# Ralph Loop 7-2: DARTLens 브랜딩/랜딩 문구 (UX 표시 전용, 엔진 무관)
APP_NAME = "DARTLens"
APP_SUBTITLE = "동종산업대비 재무 이상징후 분석기"
APP_PAGE_TITLE = f"{APP_NAME} — {APP_SUBTITLE}"
APP_DESC = ("OpenDART 공시 데이터를 기반으로 대상 기업의 연결재무제표를 수집하고, "
            "동종산업 상장 peer와 주요 재무비율을 비교해 검토가 필요한 이상징후 후보를 선별합니다.")

# 첫 화면 기능 카드(작고 단정하게). 과한 gradient/badge/metrics 지양.
FEATURE_CARDS = [
    ("🏭 동종산업 Peer 구성", "induty_code 기준 상장 peer universe를 구성합니다."),
    ("📑 연결재무제표(CFS) 수집", "사업보고서 연결재무제표를 OpenDART에서 수집합니다."),
    ("📊 15개 재무비율 분석", "수익성·안정성·운전자본·회전율 15개 비율을 산업과 비교합니다."),
    ("📥 Excel 리포트 생성", "판정·근거·peer 목록이 담긴 Excel 리포트를 생성합니다."),
]

# HIGH/LOW 의미 고지(좋음/나쁨·오류·부정 아님).
HIGHLOW_NOTE = ("본 도구의 HIGH/LOW 표시는 오류 또는 부정의 결론이 아니라, "
                "동종산업 peer 대비 추가 검토가 필요한 재무비율 후보입니다.")

# sparse peer 09시트 안내(있을 때만 노출).
SPARSE_NOTICE = ("동종산업 peer 수가 최소 benchmark 기준에 미달한 경우, HIGH/LOW/NORMAL 판정은 보류하고 "
                 "**09_제한적_peer_비교** 시트에서 실제 peer 회사별 참고 비교를 제공합니다.")

CAVEATS = [
    HIGHLOW_NOTE,
    "HIGH/LOW/NORMAL은 확정 판단이 아니라 산업 대비 상대적 위치를 나타내는 **검토 보조용 분류**입니다.",
    "**NORMAL은 '위험 없음'이 아니라** 현재 peer universe와 IQR 기준상 이상치로 분류되지 않았다는 의미입니다.",
    "산업 benchmark는 induty_code peer universe와 계정 mapping 정책의 한계가 있습니다.",
    "매출채권·매입채무 관련 비율은 순수 계정 기준이라 계산 가능 peer 수가 제한될 수 있습니다.",
]


# --------------------------------------------------------------------------
def render_sidebar():
    st.sidebar.header("분석 입력")

    api_key = st.sidebar.text_input("OpenDART API Key", type="password",
                                    help="입력 키는 현재 세션에서만 사용하며 화면/로그/파일에 저장하지 않습니다.")
    st.sidebar.caption("🔑 " + uih.key_status_text(api_key))

    company = st.sidebar.text_input("회사명 또는 종목코드", value="",
                                    placeholder="회사명 또는 6자리 종목코드")
    year = st.sidebar.selectbox("사업연도", options=[2025, 2024], index=0)

    st.sidebar.markdown("**보고서 유형**: 사업보고서  \n**재무제표 기준**: 연결(CFS)")

    run_new = st.sidebar.button("분석 실행", type="primary", width="stretch")

    # 기존 산출물(삼성 외 Loop 5/6 포함) 후보 — 최신 timestamp 우선, 읽기 전용
    candidates = uih.list_report_candidates(OUTPUT_DIR)
    selected = None
    if candidates:
        idx = st.sidebar.selectbox(
            "불러올 산출물(최신순)", options=list(range(len(candidates))),
            format_func=lambda i: uih.candidate_label(candidates[i]), index=0,
            help="output 폴더의 기존 리포트를 읽기 전용으로 확인합니다(재생성 없음).")
        selected = candidates[idx]
    else:
        st.sidebar.caption("output 폴더에 불러올 리포트가 없습니다.")
    load_recent = st.sidebar.button("최근 분석 결과 불러오기", width="stretch")

    st.sidebar.info("API key는 화면/로그/산출물에 저장하지 않습니다.")
    return api_key, company, year, run_new, load_recent, selected


def render_hero():
    """상단 hero — DARTLens 브랜딩 + 2줄 설명(데모가 아닌 실제 분석 도구로 제시)."""
    st.title(APP_NAME)
    st.markdown(f"##### {APP_SUBTITLE}")
    st.write(APP_DESC)


def render_feature_cards():
    """기능 카드 4개(작고 단정하게)."""
    cols = st.columns(4)
    for col, (title, desc) in zip(cols, FEATURE_CARDS):
        with col:
            st.markdown(f"**{title}**")
            st.caption(desc)


def render_landing():
    """결과가 없을 때의 입력 중심 첫 화면(데모 전시 아님)."""
    st.info("시작하려면 왼쪽 **분석 입력** 패널에서 API Key · 회사명(또는 종목코드) · 사업연도를 입력하고 "
            "**분석 실행**을 누르세요. 이전 산출물은 **최근 분석 결과 불러오기**로 확인할 수 있습니다.")
    st.markdown("##### 제공 기능")
    render_feature_cards()
    st.caption("회사명 또는 6자리 종목코드와 사업연도를 입력하면 동종산업 peer와 비교해 리포트를 생성합니다. "
               "peer가 부족한 산업은 통계 판정을 보류하고 sparse peer 직접 비교로 표시합니다.")


def render_report(final_path, debug_path, pair_status="matched", pair_ts=""):
    tabs = st.tabs(["요약", "수익성", "안정성/재무구조", "운전자본/계정리스크", "회전율",
                    "Peer List", "계산불가/제외사유", "Methodology", "다운로드"])

    # 1. 요약
    with tabs[0]:
        s = uih.extract_summary(final_path)
        c = st.columns(6)
        c[0].metric("회사", s.get("company") or "-")
        c[1].metric("사업연도", s.get("year") or "-")
        c[2].metric("peer 후보", _fmt(s.get("peer_candidates")))
        c[3].metric("CFS 성공", _fmt(s.get("cfs_success")))
        c[4].metric("CFS 실패", _fmt(s.get("cfs_fail")))
        c[5].metric("계산 비율", f"{_fmt(s.get('computable_count'))}/{_fmt(s.get('total_ratios'))}")

        st.markdown(f"**분석 상태**: {uih.status_display(uih.report_status_token(final_path))}")
        if uih.has_sparse_sheet(final_path):
            st.info(SPARSE_NOTICE)

        st.subheader("판정 요약")
        lc = s.get("label_counts") or {}
        if lc:
            st.write("  ·  ".join(f"{k} {v}" for k, v in lc.items()))
        else:
            st.caption("판정 데이터를 읽지 못했습니다.")

        st.subheader("핵심 해석 요약")
        for line in uih.build_interpretation(final_path):
            st.markdown("- " + line)

        st.subheader("주의")
        for cav in CAVEATS:
            st.markdown("- " + cav)

    # 2~5. 비율 시트
    for i, (tab_name, sheet) in enumerate(uih.RATIO_TAB_SHEETS.items(), start=1):
        with tabs[i]:
            _show_ratio_sheet(final_path, sheet)

    # 6. Peer List
    with tabs[5]:
        s = uih.extract_summary(final_path)
        st.caption(f"peer 후보 {_fmt(s.get('peer_candidates'))} · "
                   f"CFS 성공 {_fmt(s.get('cfs_success'))} · CFS 실패 {_fmt(s.get('cfs_fail'))}")
        _show_sheet(final_path, "06_Peer_List", "기업코드")

    # 7. 계산불가/제외사유
    with tabs[6]:
        st.caption("NOT_COMPUTABLE · CFS 실패 · benchmark 제외 사유 (숨기지 않고 표시)")
        _show_sheet(final_path, "08_계산불가_및_제외사유", "구분")

    # 8. Methodology
    with tabs[7]:
        st.caption("HIGH/LOW/NORMAL의 의미와 한계 — NORMAL은 안전 확정이 아닙니다.")
        st.caption("표기 대응(원시 → 화면): " + " · ".join(
            f"{tok} → {uih.status_display(tok)}" for tok in uih.STATUS_LEGEND_TOKENS))
        st.caption(HIGHLOW_NOTE)
        _show_sheet(final_path, "07_Methodology", "항목")

    # 9. 다운로드
    with tabs[8]:
        # report/debug timestamp 쌍 상태
        if pair_status == "matched":
            st.success(f"최종 리포트와 Debug 파일 timestamp 일치 ({pair_ts})")
        else:
            st.warning(f"최신 리포트({pair_ts})에 대응하는 동일 timestamp benchmark_debug가 없습니다. "
                       "다른 timestamp debug를 조용히 내려받지 않도록 Debug 다운로드를 비활성화합니다.")
        # sparse peer 09시트가 있는 리포트에만 안내(없으면 과노출 금지)
        if uih.has_sparse_sheet(final_path):
            st.info(SPARSE_NOTICE)
        st.write("실제 파일명을 유지하여 다운로드합니다(읽기 전용).")
        _download_button("📊 최종 사용자용 Excel 다운로드", final_path)
        if pair_status == "matched" and debug_path is not None:
            _download_button("🔎 benchmark_debug Excel 다운로드", debug_path)
        else:
            st.caption("동일 timestamp benchmark_debug 파일이 없어 Debug 다운로드는 비활성화되었습니다.")


def _show_ratio_sheet(final_path, sheet):
    try:
        df = uih.ratio_sheet_df(final_path, sheet)
    except Exception as e:
        st.warning(f"시트를 읽지 못했습니다: {sheet} ({type(e).__name__})")
        return
    if df.empty:
        st.caption("표시할 데이터가 없습니다.")
        return
    try:
        st.dataframe(uih.style_ratio_df(df), width="stretch")
    except Exception:
        st.dataframe(df, width="stretch")


def _show_sheet(final_path, sheet, header_key):
    try:
        df = uih.sheet_to_df(final_path, sheet, header_contains=header_key)
    except Exception as e:
        st.warning(f"시트를 읽지 못했습니다: {sheet} ({type(e).__name__})")
        return
    if df.empty:
        st.caption("표시할 데이터가 없습니다.")
        return
    st.dataframe(df, width="stretch")


def _download_button(label, path):
    try:
        name, data = uih.prepare_download(path)
        st.download_button(label, data=data, file_name=name,
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        st.warning(f"다운로드 준비 실패: {type(e).__name__}")


def _fmt(v):
    return "-" if v is None else str(v)


# --------------------------------------------------------------------------
def main():
    st.set_page_config(page_title=APP_PAGE_TITLE, layout="wide")
    render_hero()

    api_key, company, year, run_new, load_recent, selected = render_sidebar()

    if "final_path" not in st.session_state:
        st.session_state["final_path"] = None
        st.session_state["debug_path"] = None

    if load_recent:
        if selected is None:
            st.error("output 폴더에서 불러올 산출물을 찾지 못했습니다. 먼저 분석을 실행하세요.")
        else:
            pair = uih.resolve_pair_for_report(OUTPUT_DIR, selected["path"], int(selected["year"]))
            st.session_state["final_path"] = str(pair["report"])
            st.session_state["debug_path"] = str(pair["debug"]) if pair["debug"] else None
            st.session_state["pair_status"] = pair["status"]
            st.session_state["pair_ts"] = pair["timestamp"]
            st.success(f"불러오기 완료: {selected['company']} · {selected['year']} · {pair['report'].name}")
            level, msg = uih.pair_status_text(pair)
            (st.success if level == "ok" else st.warning)(msg)

    if run_new:
        from src import ui_runner  # lazy: 엔진 import 체인은 실행 시에만
        if not (company or "").strip():
            st.warning("회사명 또는 6자리 종목코드를 입력하세요.")
        else:
            with st.status("새 분석 실행 중... (캐시 우선, 산출물 새 timestamp 생성)", expanded=True) as status:
                st.write("분석 엔진(multi_target_runner.run_target) 호출 — 계산 로직 불변")
                res = ui_runner.run_new_analysis(company, year, api_key=api_key)
                if res["ok"]:
                    st.session_state["final_path"] = str(res["final"])
                    st.session_state["debug_path"] = str(res["debug"]) if res["debug"] else None
                    # run_target는 final/debug를 동일 timestamp로 생성 → matched
                    st.session_state["pair_status"] = "matched" if res["debug"] else "debug_missing"
                    st.session_state["pair_ts"] = uih.timestamp_from_name(res["final"])
                    status.update(label=f"분석 상태: {uih.status_display('PASS')}", state="complete")
                    st.success(res["message"])
                else:
                    status.update(label=f"분석 상태: {uih.status_display('FAIL')}", state="error")
                    st.warning(res["message"])

    final_path = st.session_state.get("final_path")
    debug_path = st.session_state.get("debug_path")
    if final_path:
        render_report(final_path, debug_path,
                      pair_status=st.session_state.get("pair_status", "matched"),
                      pair_ts=st.session_state.get("pair_ts", ""))
    else:
        render_landing()


if __name__ == "__main__":
    main()
