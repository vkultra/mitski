"""Inline keyboards for the statistics UX."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional

from services.stats.callbacks import encode_callback
from services.stats.schemas import StatsWindow, StatsWindowMode


def _callback(user_id: int, data: Dict[str, object]) -> str:
    return encode_callback(user_id, data)


def _day_delta(day: date, delta: int) -> date:
    return day + timedelta(days=delta)


def _window_dict_for(
    window: StatsWindow, day_override: Optional[date] = None
) -> Dict[str, str]:
    if day_override is not None:
        iso = day_override.isoformat()
        return {"mode": "day", "day": iso, "start": iso, "end": iso}

    payload = {
        "mode": window.mode.value,
        "start": window.start_date.isoformat(),
        "end": window.end_date.isoformat(),
    }
    if window.mode == StatsWindowMode.DAY and window.day is not None:
        payload["day"] = window.day.isoformat()
    return payload


def _view_button(
    user_id: int,
    window: StatsWindow,
    *,
    label: str,
    view_name: str,
    active_view: str,
) -> Dict[str, str]:
    is_active = active_view == view_name
    target_view = "summary" if is_active and view_name != "summary" else view_name
    text = f"{label}{' ✅' if is_active else ''}"

    payload = _window_dict_for(window)
    payload.update({"scope": "stats", "action": "navigate", "view": target_view})
    return {"text": text, "callback_data": _callback(user_id, payload)}


def build_main_keyboard(
    window: StatsWindow,
    *,
    user_id: int,
    active_view: str = "summary",
    filter_active: bool = False,
) -> Dict[str, List[List[Dict[str, str]]]]:
    rows: List[List[Dict[str, str]]] = []

    if window.mode == StatsWindowMode.DAY:
        base_window = _window_dict_for(window)
        prev_payload = {
            **_window_dict_for(window, _day_delta(window.day, -1)),  # type: ignore[arg-type]
            "scope": "stats",
            "action": "navigate",
            "view": active_view,
            "window": base_window,
        }
        next_payload = {
            **_window_dict_for(window, _day_delta(window.day, 1)),  # type: ignore[arg-type]
            "scope": "stats",
            "action": "navigate",
            "view": active_view,
            "window": base_window,
        }
        today_payload = {
            **_window_dict_for(window, date.today()),
            "scope": "stats",
            "action": "navigate",
            "view": "summary",
            "window": base_window,
        }
        rows.append(
            [
                {
                    "text": "◀️ Dia anterior",
                    "callback_data": _callback(user_id, prev_payload),
                },
                {
                    "text": "📍 Hoje",
                    "callback_data": _callback(user_id, today_payload),
                },
                {
                    "text": "▶️ Próximo dia",
                    "callback_data": _callback(user_id, next_payload),
                },
            ]
        )
    else:
        reset_payload = _window_dict_for(
            StatsWindow(mode=StatsWindowMode.DAY, day=date.today())
        )
        reset_payload.update(
            {"scope": "stats", "action": "navigate", "view": "summary"}
        )
        rows.append(
            [
                {
                    "text": "📅 Voltar ao dia atual",
                    "callback_data": _callback(user_id, reset_payload),
                }
            ]
        )

    button_rows = [
        [
            _view_button(
                user_id,
                window,
                label="🏆 Top bots",
                view_name="top",
                active_view=active_view,
            ),
            _view_button(
                user_id,
                window,
                label="⏰ Horários",
                view_name="hours",
                active_view=active_view,
            ),
        ],
        [
            _view_button(
                user_id,
                window,
                label="📉 Abandono",
                view_name="phases",
                active_view=active_view,
            ),
            _view_button(
                user_id,
                window,
                label="🧾 Custos",
                view_name="costs",
                active_view=active_view,
            ),
        ],
    ]

    rows.extend(button_rows)

    filter_payload = {
        "scope": "stats",
        "action": "filter",
        "mode": window.mode.value,
        "day": (window.day.isoformat() if window.mode == StatsWindowMode.DAY else None),
        "start": (window.start_date.isoformat()),
        "end": (window.end_date.isoformat()),
        "window": _window_dict_for(window),
    }
    refresh_payload = {
        "scope": "stats",
        "action": "refresh",
        "view": active_view,
        "mode": window.mode.value,
        "day": (window.day.isoformat() if window.mode == StatsWindowMode.DAY else None),
        "start": (window.start_date.isoformat()),
        "end": (window.end_date.isoformat()),
        "window": _window_dict_for(window),
    }

    rows.append(
        [
            {
                "text": "🔎 Filtro ativo" if filter_active else "🔎 Filtros",
                "callback_data": _callback(user_id, filter_payload),
            },
            {
                "text": "🔄 Atualizar",
                "callback_data": _callback(user_id, refresh_payload),
            },
        ]
    )

    return {"inline_keyboard": rows}


def build_cost_actions(
    window: StatsWindow, *, user_id: int
) -> Dict[str, List[List[Dict[str, str]]]]:
    rows: List[List[Dict[str, str]]] = []

    add_general = {
        "scope": "stats",
        "action": "cost_add",
        "scope_type": "general",
        "mode": window.mode.value,
        "day": (
            window.day.isoformat()
            if window.mode == StatsWindowMode.DAY
            else window.end_date.isoformat()
        ),
        "window": _window_dict_for(window),
    }
    add_bot = {
        "scope": "stats",
        "action": "cost_add",
        "scope_type": "bot",
        "mode": window.mode.value,
        "day": (
            window.day.isoformat()
            if window.mode == StatsWindowMode.DAY
            else window.end_date.isoformat()
        ),
        "window": _window_dict_for(window),
    }
    rows.append(
        [
            {
                "text": "➕ Custo Geral",
                "callback_data": _callback(user_id, add_general),
            },
            {
                "text": "➕ Custo por Bot",
                "callback_data": _callback(user_id, add_bot),
            },
        ]
    )

    return {"inline_keyboard": rows}


__all__ = ["build_main_keyboard", "build_cost_actions"]
