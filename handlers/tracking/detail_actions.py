"""Detail-oriented actions for tracking handlers."""

from __future__ import annotations

from datetime import date
from typing import Dict

from handlers.tracking.tokens import build_token
from handlers.tracking.utils import (
    clamp_next_day,
    encode_day_page,
    escape_md,
    format_day,
    prev_day,
)
from services.stats.formatters import format_brl
from services.tracking.service import TrackerNotFoundError, TrackerService
from services.tracking.types import TrackerDetail


def render_detail(
    service: TrackerService, user_id: int, tracker_id: int, day: date
) -> Dict[str, object]:
    try:
        detail = service.detail(tracker_id, day=day)
    except TrackerNotFoundError:
        return {"text": "⚠️ Não encontrei esse rastreio."}
    return {
        "text": _detail_text(detail, day),
        "keyboard": _detail_keyboard(user_id, detail, day),
        "parse_mode": "Markdown",
    }


def render_link_alert(service: TrackerService, tracker_id: int) -> Dict[str, object]:
    try:
        tracker = service.detail(tracker_id, day=date.today()).tracker
    except TrackerNotFoundError:
        return {"callback_alert": {"text": "⚠️ Rastreo inválido.", "show_alert": True}}
    return {"callback_alert": {"text": f"🔗 {tracker.link}", "show_alert": True}}


def render_delete_prompt(
    service: TrackerService, user_id: int, tracker_id: int, day: date
) -> Dict[str, object]:
    try:
        detail = service.detail(tracker_id, day=day)
    except TrackerNotFoundError:
        return {"text": "⚠️ Não encontrei esse rastreio."}
    tracker = detail.tracker
    day_token = day.strftime("%Y%m%d")
    return {
        "text": (
            "🗑️ *Remover rastreio*\n"
            f"Deseja excluir *{escape_md(tracker.name)}*? O link deixará de funcionar imediatamente."
        ),
        "keyboard": {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Confirmar",
                        "callback_data": build_token(
                            "c", user_id=user_id, tracker_id=tracker.id, extra=day_token
                        ),
                    },
                    {
                        "text": "❌ Cancelar",
                        "callback_data": build_token(
                            "d", user_id=user_id, tracker_id=tracker.id, extra=day_token
                        ),
                    },
                ]
            ]
        },
        "parse_mode": "Markdown",
    }


def render_deletion_feedback(user_id: int, day: date) -> Dict[str, object]:
    return {
        "text": "🗑️ Rastreio removido com sucesso.",
        "keyboard": {
            "inline_keyboard": [
                [
                    {
                        "text": "⬅️ Voltar",
                        "callback_data": build_token(
                            "l", user_id=user_id, extra=encode_day_page(day, 1)
                        ),
                    }
                ]
            ]
        },
    }


def _detail_text(detail: TrackerDetail, day: date) -> str:
    lines = [
        f"📊 *{escape_md(detail.tracker.name)}* (@{detail.tracker.bot_username})",
        f"Dia {format_day(day)}",
        "",
        f"👤 Starts: {detail.tracker.starts}",
        f"🛒 Vendas: {detail.tracker.sales}",
        f"💰 Faturamento: {format_brl(detail.tracker.revenue_cents)}",
        "",
        "📆 Últimos dias:",
    ]
    for entry_day, starts, sales, revenue in detail.timeline:
        lines.append(
            f"• {entry_day.strftime('%d/%m')}: 👤 {starts} • 🛒 {sales} • 💰 {format_brl(revenue)}"
        )
    return "\n".join(lines)


def _detail_keyboard(
    user_id: int, detail: TrackerDetail, day: date
) -> Dict[str, object]:
    prev_token = prev_day(day).strftime("%Y%m%d")
    next_token = clamp_next_day(day).strftime("%Y%m%d")
    day_token = day.strftime("%Y%m%d")
    return {
        "inline_keyboard": [
            [
                {
                    "text": "◀️ Dia",
                    "callback_data": build_token(
                        "d",
                        user_id=user_id,
                        tracker_id=detail.tracker.id,
                        extra=prev_token,
                    ),
                },
                {
                    "text": "Dia ➡️",
                    "callback_data": build_token(
                        "d",
                        user_id=user_id,
                        tracker_id=detail.tracker.id,
                        extra=next_token,
                    ),
                },
            ],
            [
                {
                    "text": "🔗 Link",
                    "callback_data": build_token(
                        "k", user_id=user_id, tracker_id=detail.tracker.id
                    ),
                },
                {
                    "text": "🗑️ Apagar",
                    "callback_data": build_token(
                        "x",
                        user_id=user_id,
                        tracker_id=detail.tracker.id,
                        extra=day_token,
                    ),
                },
            ],
            [
                {
                    "text": "⬅️ Listar",
                    "callback_data": build_token(
                        "l", user_id=user_id, extra=encode_day_page(day, 1)
                    ),
                },
                {
                    "text": "⬅️ Menu",
                    "callback_data": build_token("m", user_id=user_id),
                },
            ],
        ]
    }


__all__ = [
    "render_detail",
    "render_link_alert",
    "render_delete_prompt",
    "render_deletion_feedback",
]
