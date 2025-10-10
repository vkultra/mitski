"""Inline day picker used for statistics filters."""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Dict, List, Optional

from services.stats.callbacks import encode_callback
from services.stats.schemas import StatsWindow, StatsWindowMode


def window_to_dict(window: StatsWindow) -> Dict[str, str]:
    payload = {
        "mode": window.mode.value,
        "start": window.start_date.isoformat(),
        "end": window.end_date.isoformat(),
    }
    if window.mode == StatsWindowMode.DAY and window.day is not None:
        payload["day"] = window.day.isoformat()
    return payload


def _month_start(anchor: date) -> date:
    return anchor.replace(day=1)


def _shift_month(anchor: date, value: int) -> date:
    month_index = anchor.year * 12 + anchor.month - 1 + value
    year = month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _default_anchor(window: StatsWindow, selected_start: Optional[date]) -> date:
    if selected_start:
        return _month_start(selected_start)
    reference = (
        window.end_date
        if window.mode == StatsWindowMode.RANGE
        else window.day or date.today()
    )
    return _month_start(reference)


def _build_nav_row(
    user_id: int,
    view: str,
    stage: str,
    window_dict: Dict[str, str],
    anchor: date,
    selected_start: Optional[date],
) -> List[Dict[str, str]]:
    prev_anchor = _shift_month(anchor, -1)
    next_anchor = _shift_month(anchor, 1)

    base_payload = {
        "scope": "stats",
        "view": view,
        "window": window_dict,
    }
    if selected_start is not None:
        base_payload["start"] = selected_start.isoformat()

    prev_payload = {
        **base_payload,
        "action": f"{stage}_nav",
        "anchor": prev_anchor.isoformat(),
    }
    next_payload = {
        **base_payload,
        "action": f"{stage}_nav",
        "anchor": next_anchor.isoformat(),
    }
    label = anchor.strftime("%b %Y").title()

    return [
        {"text": "◀️", "callback_data": encode_callback(user_id, prev_payload)},
        {"text": label, "callback_data": "noop"},
        {"text": "▶️", "callback_data": encode_callback(user_id, next_payload)},
    ]


def build_day_picker(
    user_id: int,
    *,
    window: StatsWindow,
    view: str,
    stage: str,
    selected_start: Optional[date] = None,
    anchor: Optional[date] = None,
) -> Dict[str, List[List[Dict[str, str]]]]:
    """Return keyboard representing a monthly calendar for date selection."""

    window_dict = window_to_dict(window)
    anchor_month = _month_start(anchor or _default_anchor(window, selected_start))
    days_in_month = calendar.monthrange(anchor_month.year, anchor_month.month)[1]
    month_days = [anchor_month + timedelta(days=i) for i in range(days_in_month)]

    rows: List[List[Dict[str, str]]] = []
    rows.append(
        _build_nav_row(
            user_id,
            view,
            stage,
            window_dict,
            anchor_month,
            selected_start,
        )
    )

    # build day rows (7 per row)
    week: List[Dict[str, str]] = []
    for current in month_days:
        if stage == "filter_end" and selected_start and current < selected_start:
            week.append({"text": "  ", "callback_data": "noop"})
            if len(week) == 7:
                rows.append(week)
                week = []
            continue

        label = f"{current.day:02d}"
        if selected_start:
            if stage == "filter_start" and current == selected_start:
                label = f"✅ {current.day:02d}"
            elif stage == "filter_end" and current == selected_start:
                label = f"🏁 {current.day:02d}"

        payload: Dict[str, object] = {
            "scope": "stats",
            "action": stage,
            "date": current.isoformat(),
            "view": view,
            "window": window_dict,
        }
        if selected_start is not None:
            payload["start"] = selected_start.isoformat()

        week.append(
            {
                "text": label,
                "callback_data": encode_callback(user_id, payload),
            }
        )
        if len(week) == 7:
            rows.append(week)
            week = []

    if week:
        # pad with no-op buttons to keep grid aligned
        while len(week) < 7:
            week.append({"text": "  ", "callback_data": "noop"})
        rows.append(week)

    cancel_payload = {
        "scope": "stats",
        "action": "cancel_filter",
        "view": view,
        "window": window_dict,
    }
    rows.append(
        [
            {
                "text": "↩️ Cancelar",
                "callback_data": encode_callback(user_id, cancel_payload),
            }
        ]
    )

    return {"inline_keyboard": rows}


__all__ = ["build_day_picker", "window_to_dict"]
