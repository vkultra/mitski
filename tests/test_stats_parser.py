"""Tests for statistics input parsers."""

from datetime import date

import pytest

from services.stats.parser import parse_brl_to_cents, parse_date_range


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("100", 10000),
        ("R$ 1.234,56", 123456),
        ("1.234,56", 123456),
        ("2,5", 250),
    ],
)
def test_parse_brl_to_cents(raw: str, expected: int) -> None:
    assert parse_brl_to_cents(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "R$", "1,2,3"])
def test_parse_brl_to_cents_invalid(raw: str) -> None:
    with pytest.raises(Exception):
        parse_brl_to_cents(raw)


def test_parse_date_range() -> None:
    start, end = parse_date_range("2025-10-01 a 2025-10-07")
    assert start == date(2025, 10, 1)
    assert end == date(2025, 10, 7)


def test_parse_date_range_swap() -> None:
    start, end = parse_date_range("07/10/2025 até 01/10/2025")
    assert start == date(2025, 10, 1)
    assert end == date(2025, 10, 7)
