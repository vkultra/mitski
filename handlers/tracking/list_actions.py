"""List interactions for tracking handlers."""

from __future__ import annotations

from datetime import date
from typing import Dict, Sequence

from handlers.tracking.tokens import build_token
from handlers.tracking.utils import (
    clamp_next_day,
    encode_day_page,
    escape_md,
    format_day,
    per_page,
    prev_day,
    total_pages,
)
from services.stats.formatters import format_brl
from services.tracking.service import TrackerService
from services.tracking.types import TrackerView


def render_list(
    service: TrackerService, user_id: int, day: date, page: int
) -> Dict[str, object]:
    trackers, total = service.list(page=page, per_page=per_page(), day=day)
    pages = total_pages(total)
    lines = [
        f"📋 *Meus Rastreios* — {format_day(day)} (página {page}/{pages})",
        "",
    ]
    if not trackers:
        lines.append("Nenhum rastreio ativo neste dia.")
    for item in trackers:
        lines.append(
            f"🎯 *{escape_md(item.name)}* (@{item.bot_username})\n"
            f"   👤 {item.starts} • 🛒 {item.sales} • 💰 {format_brl(item.revenue_cents)}"
        )
    keyboard = _list_keyboard(user_id, trackers, day, page, pages)
    return {"text": "\n".join(lines), "keyboard": keyboard, "parse_mode": "Markdown"}


def _list_keyboard(
    user_id: int,
    trackers: Sequence[TrackerView],
    day: date,
    page: int,
    pages: int,
) -> Dict[str, object]:
    rows = []
    day_token = day.strftime("%Y%m%d")
    for item in trackers:
        rows.append(
            [
                {
                    "text": "🔗 Link",
                    "callback_data": build_token(
                        "k", user_id=user_id, tracker_id=item.id
                    ),
                },
                {
                    "text": "📊 Ver",
                    "callback_data": build_token(
                        "d", user_id=user_id, tracker_id=item.id, extra=day_token
                    ),
                },
                {
                    "text": "🗑️ Apagar",
                    "callback_data": build_token(
                        "x", user_id=user_id, tracker_id=item.id, extra=day_token
                    ),
                },
            ]
        )
    nav_row = []
    if page > 1:
        nav_row.append(
            {
                "text": "◀️ Página",
                "callback_data": build_token(
                    "l", user_id=user_id, extra=encode_day_page(day, page - 1)
                ),
            }
        )
    if page < pages:
        nav_row.append(
            {
                "text": "Página ▶️",
                "callback_data": build_token(
                    "l", user_id=user_id, extra=encode_day_page(day, page + 1)
                ),
            }
        )
    if nav_row:
        rows.append(nav_row)
    rows.append(
        [
            {
                "text": "⬅️ Dia",
                "callback_data": build_token(
                    "l", user_id=user_id, extra=encode_day_page(prev_day(day), 1)
                ),
            },
            {
                "text": "Hoje",
                "callback_data": build_token(
                    "l", user_id=user_id, extra=encode_day_page(date.today(), 1)
                ),
            },
            {
                "text": "Dia ➡️",
                "callback_data": build_token(
                    "l",
                    user_id=user_id,
                    extra=encode_day_page(clamp_next_day(day), 1),
                ),
            },
        ]
    )
    rows.append(
        [{"text": "⬅️ Menu", "callback_data": build_token("m", user_id=user_id)}]
    )
    return {"inline_keyboard": rows}


__all__ = ["render_list"]
