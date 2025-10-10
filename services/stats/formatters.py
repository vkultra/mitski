"""Formatting helpers for statistics rendering."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Tuple

BR_WEEKDAYS = [
    "Seg",
    "Ter",
    "Qua",
    "Qui",
    "Sex",
    "Sáb",
    "Dom",
]


def format_brl(amount_cents: int | Decimal | None) -> str:
    value = Decimal(amount_cents or 0) / Decimal(100)
    quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    formatted = (
        f"{quantized:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )
    return f"R$ {formatted}"


def format_percent(ratio: float | None) -> str:
    if ratio is None or ratio != ratio:  # check for NaN
        return "0%"
    return f"{ratio * 100:.1f}%"


def format_day_label(day: date) -> str:
    weekday = BR_WEEKDAYS[day.weekday()]
    return f"📅 {day.strftime('%d/%m/%Y')} ({weekday})"


def format_hour(hour: int) -> str:
    hour = max(0, min(23, hour))
    return f"{hour:02d}h"


def format_top_hours(entries: Iterable[Tuple[int, int]]) -> str:
    parts = [f"{format_hour(hour)} — {count} vendas" for hour, count in entries]
    return "\n".join(parts)


def format_count(value: int | None) -> str:
    return f"{value or 0:,}".replace(",", ".")


__all__ = [
    "format_brl",
    "format_percent",
    "format_day_label",
    "format_hour",
    "format_top_hours",
    "format_count",
]
