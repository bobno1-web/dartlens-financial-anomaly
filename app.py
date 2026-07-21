"""Ralph Loop 4: Streamlit UI MVP (Loop 11: 새 분석 일반화).

검증된 분석 엔진을 로컬 웹 UI로 감싼다. 분석 로직은 변경하지 않고 산출물 Excel을 읽어
표시하거나(최근 결과 불러오기), 엔진(multi_target_runner.run_target)을 호출한다(새 분석 실행 —
사용자가 입력한 회사/연도를 그대로 전달). API key는 화면/로그/산출물/파일에 저장·출력하지 않는다.

실행:  streamlit run app.py
"""
from __future__ import annotations

import html as _html

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


# ==========================================================================
# Ralph Loop 17: 표시(display) 디자인 layer — custom CSS/HTML 전용.
# 계산·판정·데이터 로직은 건드리지 않는다(INV-7). 이미 계산된 label/값을 '읽어' 색·형태로만
# 표현한다. 판정 색은 INV-8 준수: HIGH=앰버 · LOW=파랑 · NORMAL=중립(초록/빨강 금지),
# 절대판정(red flag)은 danger red 없이 앰버/노랑/회색(점검 신호이지 위험 확정 아님).
# --------------------------------------------------------------------------

# 판정 라벨 → 배지 종류(kind). 문자열을 '색 종류'로만 매핑(값·판정 자체는 불변).
_REL_KIND = {
    "산업 대비 높음": "amber",   # HIGH — INV-8: 빨강이 아니라 주황
    "산업 대비 낮음": "blue",    # LOW  — INV-8: 파랑
    "정상 범위": "neutral",
    "peer 부족": "gray",
    "분포 부족": "gray",
    "계산 불가": "gray",
}
_ABS_KIND = {
    "경고": "amber",
    "주의": "soft",
    "정상": "neutral",
    "해당없음": "gray",
    "미평가": "gray",
}
_REL_ORDER = ["산업 대비 높음", "산업 대비 낮음", "정상 범위", "peer 부족", "분포 부족", "계산 불가"]
_ABS_ORDER = ["경고", "주의", "정상", "미평가", "해당없음"]

# 배지/표 셀 색 (배경, 글자, 테두리) — pill(HTML)과 표 Styler가 공유해 일관 유지.
PILL = {
    "amber":   ("#FCE7BE", "#875200", "#EFC069"),
    "soft":    ("#FAF1D2", "#836210", "#E8D48F"),
    "blue":    ("#DBE9FB", "#1B4E80", "#ADC9EB"),
    "neutral": ("#E9EEF4", "#45505E", "#D0D9E4"),
    "gray":    ("#EDF0F4", "#6A7480", "#DBE1E9"),
}
# KPI 카드 상단 severity stripe 색(상태를 형태로 표현).
TONE = {
    "accent":  "#10708C",
    "amber":   "#E29A34",
    "soft":    "#E3C25F",
    "blue":    "#3E77B8",
    "neutral": "#B6C0CD",
    "gray":    "#C6CDD7",
}
_ZEBRA_BG = "background-color:#F4F7FB"

THEME_CSS = """
@import url('https://cdn.jsdelivr.net/npm/pretendard@1.3.9/dist/web/static/pretendard.min.css');
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root{
  --bg:#F4F6FA; --surface:#FFFFFF; --surface-2:#EEF2F8;
  --ink:#16202E; --ink-2:#56616F; --ink-3:#8A94A2; --line:#E1E7F0;
  --navy:#111A2B; --accent:#10708C; --accent-2:#0B5470;
  --sans:'Pretendard','Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',
         'Malgun Gothic','Apple SD Gothic Neo',system-ui,sans-serif;
}
html, body, .stApp,
[data-testid="stAppViewContainer"], [data-testid="stSidebar"]{ font-family:var(--sans); }
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"]{ background:var(--bg); }
[data-testid="stMain"] .block-container{
  max-width:1200px; padding-top:1.6rem; padding-bottom:3rem;
}
[data-testid="stMain"] .block-container p,
[data-testid="stMain"] .block-container li{ color:var(--ink-2); }
[data-testid="stMain"] h1,[data-testid="stMain"] h2,
[data-testid="stMain"] h3,[data-testid="stMain"] h4{ color:var(--ink); letter-spacing:-.01em; }

[data-testid="stSidebar"]{ background:#F7F9FC; border-right:1px solid var(--line); }
[data-testid="stSidebar"] .block-container{ padding-top:1.4rem; }

[data-baseweb="tab-list"]{ gap:.1rem; border-bottom:1px solid var(--line); flex-wrap:wrap; }
button[data-baseweb="tab"]{ color:var(--ink-3); font-weight:500; padding:.55rem .8rem; }
button[data-baseweb="tab"][aria-selected="true"]{
  color:var(--accent); box-shadow:inset 0 -2.5px 0 var(--accent);
}

/* primary action 버튼 — signal red 대신 브랜드 accent(teal). 위험색은 판정 신호 전용. */
[data-testid="stBaseButton-primary"]{
  background-color:var(--accent) !important; border-color:var(--accent) !important;
  color:#fff !important; font-weight:600;
}
[data-testid="stBaseButton-primary"]:hover,
[data-testid="stBaseButton-primary"]:focus{
  background-color:var(--accent-2) !important; border-color:var(--accent-2) !important;
}
[data-testid="stBaseButton-secondary"]{ border-color:var(--line); color:var(--ink); }
[data-testid="stBaseButton-secondary"]:hover{ border-color:var(--accent); color:var(--accent); }
[data-testid="stDownloadButton"] button{ border-color:var(--accent); color:var(--accent); font-weight:600; }

[data-testid="stAlert"]{ border-radius:10px; border:1px solid var(--line); }
[data-testid="stDataFrame"]{ border:1px solid var(--line); border-radius:10px; overflow:hidden; }
[data-testid="stMetric"]{
  background:var(--surface); border:1px solid var(--line);
  border-radius:10px; padding:.6rem .8rem;
}
[data-testid="stMetricValue"]{ font-variant-numeric:tabular-nums; color:var(--ink); }

/* ---- 브랜드 밴드 ---- */
.dl-band{
  display:flex; align-items:baseline; gap:.75rem; flex-wrap:wrap;
  padding:.1rem 0 .85rem; border-bottom:1px solid var(--line); margin-bottom:.2rem;
}
.dl-logo{ font-weight:700; font-size:1.7rem; letter-spacing:-.02em; color:var(--navy); }
.dl-logo .dl-dot{ color:var(--accent); }
.dl-sub-inline{ color:var(--ink-2); font-size:.95rem; font-weight:500; }
.dl-badge-brand{
  margin-left:auto; font-size:.66rem; font-weight:600; letter-spacing:.07em;
  text-transform:uppercase; color:var(--accent-2); background:#E4F0F4;
  border:1px solid #C9E1E8; border-radius:999px; padding:.2rem .55rem;
}
.dl-sub{ color:var(--ink-2); font-size:.9rem; margin:.7rem 0 .2rem; line-height:1.5; }

/* ---- 요약 헤더 ---- */
.dl-summary-head{
  display:flex; align-items:baseline; gap:.7rem; flex-wrap:wrap; margin:.1rem 0 .5rem;
}
.dl-sh-name{ font-size:1.35rem; font-weight:700; color:var(--ink); letter-spacing:-.01em; }
.dl-sh-year{ font-size:.9rem; color:var(--ink-2); }
.dl-status{
  margin-left:auto; font-size:.75rem; font-weight:600; color:var(--accent-2);
  background:#E4F0F4; border:1px solid #C9E1E8; border-radius:999px; padding:.2rem .6rem;
}
.dl-context{ color:var(--ink-2); font-size:.85rem; margin:.1rem 0 .6rem; }
.dl-context b{ color:var(--ink); font-variant-numeric:tabular-nums; }

/* ---- KPI 카드 ---- */
.dl-grid{
  display:grid; grid-template-columns:repeat(auto-fit,minmax(185px,1fr));
  gap:.7rem; margin:.2rem 0 .9rem;
}
.dl-card{
  position:relative; background:var(--surface); border:1px solid var(--line);
  border-radius:12px; padding:.9rem 1rem .8rem 1.1rem; overflow:hidden;
  box-shadow:0 1px 2px rgba(20,30,50,.04);
}
.dl-card-stripe{ position:absolute; left:0; top:0; bottom:0; width:4px; }
.dl-card-label{
  font-size:.72rem; font-weight:600; letter-spacing:.03em; text-transform:uppercase;
  color:var(--ink-3); margin-bottom:.35rem;
}
.dl-card-value{
  font-size:1.7rem; font-weight:700; line-height:1.1; color:var(--ink);
  font-variant-numeric:tabular-nums;
}
.dl-card-sub{ font-size:.78rem; color:var(--ink-2); margin-top:.3rem; }

/* ---- 판정 배지(pill) ---- */
.dl-pillrow{ display:flex; flex-wrap:wrap; gap:.4rem; align-items:center; margin:.15rem 0 .5rem; }
.dl-pilllabel{ font-size:.74rem; color:var(--ink-3); font-weight:600; margin-right:.15rem; }
.dl-pill{
  display:inline-flex; align-items:center; gap:.35rem; font-size:.8rem; font-weight:500;
  line-height:1; padding:.32rem .62rem; border-radius:999px; border:1px solid transparent;
}
.dl-pill b{ font-weight:700; font-variant-numeric:tabular-nums; }

/* ---- 기능 카드 ---- */
.dl-feat{
  display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr));
  gap:.7rem; margin:.4rem 0 .2rem;
}
.dl-fcard{ background:var(--surface); border:1px solid var(--line); border-radius:11px; padding:.8rem .9rem; }
.dl-ft{ font-weight:600; color:var(--ink); font-size:.92rem; }
.dl-fd{ color:var(--ink-2); font-size:.8rem; margin-top:.25rem; line-height:1.45; }

@media (max-width:640px){
  .dl-logo{ font-size:1.42rem; }
  .dl-card-value{ font-size:1.5rem; }
  [data-testid="stMain"] .block-container{ padding-top:1rem; }
}
"""


def inject_theme():
    """폰트/색/여백 custom CSS 주입(표시 전용). 오프라인이면 폰트는 시스템으로 graceful fallback."""
    st.markdown(f"<style>{THEME_CSS}</style>", unsafe_allow_html=True)


def _col(df, *names):
    cols = getattr(df, "columns", [])
    for n in names:
        if n in cols:
            return n
    return None


def _kind_for(label, absolute=False):
    table = _ABS_KIND if absolute else _REL_KIND
    return table.get(str(label).strip(), "gray")


def _pill(label, count=None, absolute=False):
    """판정 라벨을 색 배지(HTML span)로. 값·판정은 그대로 두고 색·형태만 부여."""
    bg, fg, bd = PILL[_kind_for(label, absolute)]
    tail = "" if count is None else f" <b>{int(count)}</b>"
    return (f'<span class="dl-pill" style="background:{bg};color:{fg};'
            f'border-color:{bd}">{_html.escape(str(label))}{tail}</span>')


def _ordered_counts(labels, order):
    c = {}
    for l in labels:
        c[l] = c.get(l, 0) + 1
    out = [(k, c[k]) for k in order if k in c]
    out += [(k, v) for k, v in c.items() if k not in order]
    return out


def _overview(final_path):
    """요약 대시보드/배지용 집계 — 이미 계산된 판정값을 '읽기만' 한다(값·판정 불변, INV-7)."""
    o = {"total": 0, "computable": 0, "high": 0, "low": 0, "normal": 0, "peer_short": 0,
         "warn": 0, "caution": 0, "strong": 0, "limited": 0, "rel": [], "abs": []}
    try:
        df = uih.combined_ratio_df(final_path)
    except Exception:
        return o
    if df is None or getattr(df, "empty", True):
        return o
    o["total"] = len(df)
    jcol = _col(df, "상대판정", "판정")
    acol = _col(df, "절대판정(red flag)")
    qcol = _col(df, "benchmark_quality", "신뢰도(peer·품질)")
    if jcol:
        labels = [str(x) for x in df[jcol].tolist() if x is not None and str(x) != "nan"]
        o["rel"] = _ordered_counts(labels, _REL_ORDER)
        o["computable"] = sum(1 for l in labels if l != "계산 불가")
        o["high"] = labels.count("산업 대비 높음")
        o["low"] = labels.count("산업 대비 낮음")
        o["normal"] = labels.count("정상 범위")
        o["peer_short"] = labels.count("peer 부족")
    if acol:
        av = [str(x) for x in df[acol].tolist() if x is not None and str(x) != "nan"]
        o["abs"] = _ordered_counts(av, _ABS_ORDER)
        o["warn"] = av.count("경고")
        o["caution"] = av.count("주의")
    if qcol:
        qv = [str(x).upper() for x in df[qcol].tolist() if x is not None]
        o["strong"] = sum(1 for x in qv if x.startswith("STRONG"))
        o["limited"] = sum(1 for x in qv if x.startswith(("WEAK", "LIMITED", "NOT_AVAILABLE")))
    return o


def _kpi_card(label, value, sub, tone="neutral"):
    stripe = TONE.get(tone, TONE["neutral"])
    return (f'<div class="dl-card"><span class="dl-card-stripe" style="background:{stripe}"></span>'
            f'<div class="dl-card-label">{_html.escape(label)}</div>'
            f'<div class="dl-card-value">{value}</div>'
            f'<div class="dl-card-sub">{sub}</div></div>')


def render_dashboard(o):
    """요약 상단 KPI 카드 4개(상태를 stripe 색으로 인코딩). 값은 _overview 집계(읽기 전용)."""
    high_tone = "amber" if o["high"] else ("blue" if o["low"] else "neutral")
    warn_tone = "amber" if o["warn"] else ("soft" if o["caution"] else "neutral")
    if o["strong"]:
        rel_tone, rel_sub = "accent", f"STRONG 등급 · 제한 {o['limited']}"
    else:
        rel_tone = "gray"
        rel_sub = "표본 제한(peer 부족)" if o["peer_short"] else f"제한 {o['limited']}"
    cards = "".join([
        _kpi_card("분석 비율", f'{o["computable"]} / {o["total"]}', "계산 가능 · 전체", "accent"),
        _kpi_card("상대판정 · 높음", str(o["high"]), f'낮음 {o["low"]} · 정상 {o["normal"]}', high_tone),
        _kpi_card("절대판정 · 경고", str(o["warn"]), f'주의 {o["caution"]}', warn_tone),
        _kpi_card("벤치마크 신뢰도", f'{o["strong"]} / {o["total"]}', rel_sub, rel_tone),
    ])
    st.markdown(f'<div class="dl-grid">{cards}</div>', unsafe_allow_html=True)


def render_judgment_pills(o):
    """상대·절대 판정 분포를 색 배지 행으로. 태영 케이스: 정상(회색) 옆 경고(앰버)가 나란히."""
    st.markdown("**판정 요약**")
    if o["rel"]:
        pills = "".join(_pill(k, v, absolute=False) for k, v in o["rel"])
        st.markdown(f'<div class="dl-pillrow"><span class="dl-pilllabel">상대판정</span>{pills}</div>',
                    unsafe_allow_html=True)
    if o["abs"]:
        pills = "".join(_pill(k, v, absolute=True) for k, v in o["abs"])
        st.markdown(f'<div class="dl-pillrow"><span class="dl-pilllabel">절대판정</span>{pills}</div>',
                    unsafe_allow_html=True)
    if not o["rel"] and not o["abs"]:
        st.caption("판정 데이터를 읽지 못했습니다.")


def _style_ratio(df):
    """비율 표: 상대판정·절대판정 셀에 배지 색, 짝수행 zebra. 숫자·값은 그대로(st.dataframe 렌더)."""
    if not getattr(df.columns, "is_unique", True):
        return df
    jcol = _col(df, "상대판정", "판정")
    acol = _col(df, "절대판정(red flag)")

    def _row(row):
        base = _ZEBRA_BG if (row.name % 2 == 1) else ""
        out = []
        for col in df.columns:
            if col == jcol:
                bg, fg, _bd = PILL[_kind_for(row.get(jcol, ""), absolute=False)]
                out.append(f"background-color:{bg};color:{fg};font-weight:600")
            elif col == acol:
                bg, fg, _bd = PILL[_kind_for(row.get(acol, ""), absolute=True)]
                out.append(f"background-color:{bg};color:{fg};font-weight:600")
            else:
                out.append(base)
        return out

    try:
        return df.style.apply(_row, axis=1)
    except Exception:
        return df


def _zebra(df, highlight_col=None, highlight_val=None):
    """일반 표: 짝수행 zebra + (선택) 특정 행 강조. 값 불변, 배경만."""
    if not getattr(df.columns, "is_unique", True):
        return df

    def _row(row):
        if highlight_col and highlight_col in df.columns and str(row.get(highlight_col, "")) == highlight_val:
            return ["background-color:#E4F0F4;font-weight:600"] * len(df.columns)
        bg = _ZEBRA_BG if (row.name % 2 == 1) else ""
        return [bg] * len(df.columns)

    try:
        return df.style.apply(_row, axis=1)
    except Exception:
        return df


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
    """상단 브랜드 밴드 — DARTLens 워드마크 + 얇은 구분선 + 간결한 부제(절제된 금융 톤)."""
    st.markdown(
        '<div class="dl-band">'
        '<span class="dl-logo">DART<span class="dl-dot">Lens</span></span>'
        f'<span class="dl-sub-inline">{_html.escape(APP_SUBTITLE)}</span>'
        '<span class="dl-badge-brand">OpenDART · 연결(CFS)</span>'
        '</div>'
        f'<div class="dl-sub">{_html.escape(APP_DESC)}</div>',
        unsafe_allow_html=True)


def render_feature_cards():
    """기능 카드 4개(작고 단정하게) — 반응형 그리드."""
    cards = "".join(
        f'<div class="dl-fcard"><div class="dl-ft">{_html.escape(t)}</div>'
        f'<div class="dl-fd">{_html.escape(d)}</div></div>'
        for t, d in FEATURE_CARDS)
    st.markdown(f'<div class="dl-feat">{cards}</div>', unsafe_allow_html=True)


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
        o = _overview(final_path)
        status_txt = uih.status_display(uih.report_status_token(final_path))
        st.markdown(
            '<div class="dl-summary-head">'
            f'<span class="dl-sh-name">{_html.escape(s.get("company") or "-")}</span>'
            f'<span class="dl-sh-year">{_html.escape(str(s.get("year") or "-"))} 사업연도</span>'
            f'<span class="dl-status">{_html.escape(status_txt)}</span>'
            '</div>', unsafe_allow_html=True)

        render_dashboard(o)

        st.markdown(
            f'<div class="dl-context">peer 후보 <b>{_fmt(s.get("peer_candidates"))}</b>'
            f' &nbsp;·&nbsp; CFS 성공 <b>{_fmt(s.get("cfs_success"))}</b>'
            f' &nbsp;·&nbsp; CFS 실패 <b>{_fmt(s.get("cfs_fail"))}</b></div>',
            unsafe_allow_html=True)

        if uih.has_sparse_sheet(final_path):
            st.info(SPARSE_NOTICE)

        render_judgment_pills(o)

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
        _show_sheet(final_path, "06_Peer_List", "기업코드",
                    highlight_col="대상여부", highlight_val="대상")

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
        st.dataframe(_style_ratio(df), width="stretch")
    except Exception:
        st.dataframe(df, width="stretch")


def _show_sheet(final_path, sheet, header_key, highlight_col=None, highlight_val=None):
    try:
        df = uih.sheet_to_df(final_path, sheet, header_contains=header_key)
    except Exception as e:
        st.warning(f"시트를 읽지 못했습니다: {sheet} ({type(e).__name__})")
        return
    if df.empty:
        st.caption("표시할 데이터가 없습니다.")
        return
    try:
        st.dataframe(_zebra(df, highlight_col, highlight_val), width="stretch")
    except Exception:
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
    inject_theme()
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
