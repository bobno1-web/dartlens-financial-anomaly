"""Loop 26: web_engine 표시 전용 헬퍼 테스트 — explain_ratio(쉬운 설명) · format_ratio_value(09시트 숫자).

표시 layer 전용이며 엔진 값·판정을 바꾸지 않는다(INV-7). explain_ratio 의 부호 기반 문구
("손실"·유동<1 "적음"·운전자본<0 "마이너스" 등)는 **분모가 항상 양수**일 때만 재무적으로 참인데,
그 전제는 엔진(`src/ratio_input.py`의 `d_val <= 0 → invalid_denominator`)이 비양수 분모를
NOT_COMPUTABLE 로 배제해 보장한다. 아래 테스트는 그 문구와 전제를 회귀 잠금한다(cr1 Loop 26 지적).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import web_engine  # noqa: E402  (sys.path 조정 후 import)


# ── explain_ratio: 부호 기반 문구가 값에 맞게(재무적으로 정확히) 나오는지 ──────────────
def test_explain_ratio_loss_phrasing_on_negative():
    """분모>0 이 보장된 상태에서 순이익 계열이 음수면 '손실/적자' 문구."""
    assert "손실" in web_engine.explain_ratio(-0.055, "ROE")
    assert "손실" in web_engine.explain_ratio(-0.014, "ROA")
    assert "적자" in web_engine.explain_ratio(-0.046, "순이익률")
    assert "손실" in web_engine.explain_ratio(-0.027, "영업이익률")


def test_explain_ratio_neutral_phrasing_on_positive():
    """양수면 결론적 '손실' 문구 없이 중립 '무엇을 재는지' 설명."""
    for name in ("ROE", "ROA", "순이익률", "영업이익률"):
        txt = web_engine.explain_ratio(0.12, name)
        assert txt and "손실" not in txt and "적자" not in txt


def test_explain_ratio_threshold_directions():
    """유동비율<1·운전자본<0·이자보상<1 의 방향성 문구(분모>0 전제하 항상 참)."""
    assert "적음" in web_engine.explain_ratio(0.67, "유동비율")            # <1
    assert "감당하는 정도" in web_engine.explain_ratio(1.5, "유동비율")     # >=1 중립
    assert "마이너스" in web_engine.explain_ratio(-0.36, "운전자본비율")    # <0
    assert "플러스" not in web_engine.explain_ratio(-0.36, "운전자본비율")
    assert "다 감당하지 못함" in web_engine.explain_ratio(0.5, "이자보상배율")  # <1


def test_explain_ratio_debt_multiple_from_raw_value():
    """부채비율 raw 5.4195(=541.95%) → '약 5.4배' (raw=부채/자본, ×100 아님)."""
    assert "5.4배" in web_engine.explain_ratio(5.4195, "부채비율")


def test_explain_ratio_no_value_gives_neutral_not_loss():
    """계산 불가/빈/NaN 값은 중립 설명만 — 부호 기반(손실 등) 결론을 절대 만들지 않는다."""
    for raw in (None, "", "nan", "계산 불가"):
        txt = web_engine.explain_ratio(raw, "ROE")
        assert "손실" not in txt          # 값 없음 → 결론 금지
        assert txt == "주주가 낸 자본으로 이익을 얼마나 내는지"


def test_explain_ratio_unknown_ratio_returns_empty():
    assert web_engine.explain_ratio(1.0, "존재하지_않는_비율") == ""
    assert web_engine.explain_ratio(1.0, None) == ""


# ── 검증방 Loop 26 반송: 운전자본 계정 3비율 분모(매출액/매출원가) 문구 잠금 ─────────────
# 산식(화면 표시): 매출채권비율=매출채권/매출액 · 재고자산비율=재고자산/매출액 ·
# 매입채무비율=매입채무/매출원가. 설명에 '자산'(총자산 분모)이 들어가면 화면 산식과 모순 → 금지.
def test_explain_ratio_receivable_ratio_denominator_is_sales():
    txt = web_engine.explain_ratio(0.1, "매출채권비율")   # = 매출채권 / 매출액
    assert "매출 대비" in txt          # 분모=매출액을 반영
    assert "매출원가" not in txt        # 매입채무비율(분모=매출원가)과 구분
    assert "자산" not in txt            # '자산 대비'(총자산 분모) 비율과 혼동 금지


def test_explain_ratio_inventory_ratio_denominator_is_sales():
    txt = web_engine.explain_ratio(0.1, "재고자산비율")   # = 재고자산 / 매출액
    assert "매출 대비" in txt           # 분모=매출액을 반영
    assert "자산" not in txt            # 이름은 '재고자산'이지만 설명 분모는 '자산'이 아님


def test_explain_ratio_payable_ratio_denominator_is_cogs():
    txt = web_engine.explain_ratio(0.1, "매입채무비율")   # = 매입채무 / 매출원가
    assert "매출원가 대비" in txt        # 분모=매출원가를 반영(매출액 아님)
    assert "자산" not in txt


def test_explain_ratio_asset_based_ratios_keep_asset_wording():
    """대조군: 총자산 분모 비율(부채비중·차입금의존도)은 '자산' 표현 유지 — 위 3비율과 혼동 방지 잠금."""
    assert "자산" in web_engine.explain_ratio(0.6, "부채비중")      # = 부채총계 / 자산총계
    assert "자산" in web_engine.explain_ratio(0.2, "차입금의존도")  # = 이자부차입금 / 자산총계


# ── format_ratio_value: 09시트/카드 숫자 정리(2자리 + 성격별 단위) ─────────────────────
def test_format_ratio_value_units_and_rounding():
    assert web_engine.format_ratio_value("5.801885981351322", "이자보상배율") == "5.80배"  # mult
    assert web_engine.format_ratio_value("0.04601005823312791", "이자보상배율") == "0.05배"
    assert web_engine.format_ratio_value("5.4195", "부채비율") == "541.95%"                # pct ×100
    assert web_engine.format_ratio_value("-0.3645", "운전자본비율") == "-0.36"             # plain 무단위
    assert web_engine.format_ratio_value("", "이자보상배율") == ""                          # 빈 값 안전


# ── 전제 잠금: explain_ratio 부호 문구를 떠받치는 엔진 가드(비양수 분모 → 계산 불가) ────────
def test_engine_nonpositive_denominator_guard_present():
    """`src/ratio_input.py` 의 비양수 분모 배제 가드가 남아 있는지 확인.

    이 가드가 완화되면(예: `== 0`) 자본잠식(자기자본<0) 시 ROE 가 계산되어 explain_ratio 의
    'ROE<0=손실' 문구가 틀어질 수 있다. 소스 수준에서 얇게 잠근다(무거운 픽스처 없이 전제 고정).
    """
    src = (ROOT / "src" / "ratio_input.py").read_text(encoding="utf-8")
    assert "d_val <= 0" in src and "invalid_denominator" in src
