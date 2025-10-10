"""Input parsing utilities for statistics interactions."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Tuple

DATE_REGEX = re.compile(r"(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})")
DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y")


def parse_brl_to_cents(raw: str) -> int:
    cleaned = raw.strip().lower()
    if not cleaned:
        raise ValueError("valor vazio")

    cleaned = cleaned.replace("r$", "").replace(" ", "")
    cleaned = cleaned.replace(".", "").replace(",", ".")

    value = Decimal(cleaned)
    cents = (value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def parse_date_candidate(raw: str) -> date:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"data inválida: {raw}")


def parse_date_range(raw: str) -> Tuple[date, date]:
    matches = DATE_REGEX.findall(raw)
    if len(matches) != 2:
        raise ValueError("Informe duas datas (início e fim)")

    start_dt = parse_date_candidate(matches[0])
    end_dt = parse_date_candidate(matches[1])
    if start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt
    return start_dt, end_dt


__all__ = ["parse_brl_to_cents", "parse_date_range", "parse_date_candidate"]
