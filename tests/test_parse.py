"""Practical tests for the risky parse paths (Loop 1). Not exhaustive."""
from decimal import Decimal

from src.parse import detect_key_accounts, parse_amount


def test_parse_amount_basic():
    assert parse_amount("1,234,567") == Decimal("1234567")
    assert parse_amount("-5,000") == Decimal("-5000")
    assert parse_amount("(2,000)") == Decimal("-2000")  # parentheses = negative


def test_parse_amount_blank_is_none_not_zero():
    # blank/'-' must be None (missing), never silently 0
    assert parse_amount("") is None
    assert parse_amount("-") is None
    assert parse_amount(None) is None
    assert parse_amount("abc") is None


def _row(account_id="", account_nm="", amount=None, rcept_no="R1"):
    return {"account_id": account_id, "account_nm": account_nm, "amount": amount,
            "rcept_no": rcept_no}


def test_detect_key_accounts_by_id_and_missing():
    rows = [
        _row("ifrs-full_Assets", "자산총계", Decimal("100")),
        _row("ifrs-full_Liabilities", "부채총계", Decimal("40")),
        _row("ifrs-full_Equity", "자본총계", Decimal("60")),
        _row("ifrs-full_Revenue", "수익(매출액)", Decimal("200")),
        _row("dart_OperatingIncomeLoss", "영업이익", Decimal("30")),
        # 당기순이익 intentionally absent -> must be MISSING, not hidden/zero
    ]
    got = detect_key_accounts(rows)
    assert got["자산총계"]["match"] == "account_id"
    assert got["자산총계"]["amount"] == Decimal("100")
    assert got["당기순이익"]["match"] == "MISSING"
    assert got["당기순이익"]["amount"] is None
