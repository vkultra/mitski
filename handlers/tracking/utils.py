"""Utility helpers for tracking handlers."""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta
from typing import Optional, Tuple

_PER_PAGE = 5
_DATE_FMT = "%Y%m%d"
_MD_ESCAPE = re.compile(r"([_\\*\[\]()~`>#+\-=|{}.!])")


def per_page() -> int:
    return _PER_PAGE


def format_day(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def encode_day_page(d: date, page: int) -> str:
    return f"{d.strftime(_DATE_FMT)}-{page}"


def decode_day_page(extra: Optional[str]) -> Tuple[date, int]:
    if not extra:
        return date.today(), 1
    day_s, page_s = extra.split("-", 1)
    return decode_day(day_s), max(1, int(page_s))


def decode_day(extra: Optional[str]) -> date:
    if not extra:
        return date.today()
    return datetime.strptime(extra, _DATE_FMT).date()


def clamp_next_day(d: date) -> date:
    return min(d + timedelta(days=1), date.today())


def prev_day(d: date) -> date:
    return d - timedelta(days=1)


def total_pages(total_items: int) -> int:
    return max(1, math.ceil(total_items / _PER_PAGE))


def escape_md(text: str) -> str:
    return _MD_ESCAPE.sub(r"\\\1", text)


__all__ = [
    "per_page",
    "format_day",
    "encode_day_page",
    "decode_day_page",
    "decode_day",
    "clamp_next_day",
    "prev_day",
    "total_pages",
    "escape_md",
]
