"""Entry points for tracking menu callbacks."""

from __future__ import annotations

from typing import Any, Dict

from core.config import settings
from handlers.tracking import detail_actions, list_actions, main_actions
from handlers.tracking.tokens import parse_token
from handlers.tracking.utils import decode_day, decode_day_page
from services.tracking.service import TrackerService


async def handle_tracking_menu(user_id: int) -> Dict[str, Any]:
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado."}
    service = TrackerService(user_id)
    return await main_actions.render_main_menu(user_id, service)


async def handle_tracking_callback(user_id: int, callback_data: str) -> Dict[str, Any]:
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado."}
    if callback_data == "tracking_menu":
        return await handle_tracking_menu(user_id)

    token = parse_token(callback_data)
    if not token or token.user_id != user_id:
        return {
            "callback_alert": {
                "text": "⚠️ Ação inválida ou expirada.",
                "show_alert": True,
            }
        }

    service = TrackerService(user_id)
    action = token.action

    if action == "m":
        return await handle_tracking_menu(user_id)
    if action == "n":
        return await main_actions.start_creation(user_id)
    if action == "b" and token.bot_id:
        return main_actions.prompt_name(user_id, token.bot_id)
    if action == "t":
        return await main_actions.render_toggle_menu(service, user_id)
    if action == "g" and token.bot_id:
        enable = token.extra == "on"
        return main_actions.apply_toggle(service, user_id, token.bot_id, enable)
    if action in {"l", "p"}:
        day, page = decode_day_page(token.extra)
        return list_actions.render_list(service, user_id, day, page)
    if action == "d" and token.tracker_id:
        day = decode_day(token.extra)
        return detail_actions.render_detail(service, user_id, token.tracker_id, day)
    if action == "k" and token.tracker_id:
        return detail_actions.render_link_alert(service, token.tracker_id)
    if action == "x" and token.tracker_id:
        day = decode_day(token.extra)
        return detail_actions.render_delete_prompt(
            service, user_id, token.tracker_id, day
        )
    if action == "c" and token.tracker_id:
        day = decode_day(token.extra)
        if service.delete(tracker_id=token.tracker_id):
            return detail_actions.render_deletion_feedback(user_id, day)
        return {"text": "⚠️ Não consegui excluir esse rastreio."}

    return {"text": "⚠️ Ação não reconhecida."}


async def handle_tracking_text_input(
    user_id: int, text: str, state: Dict[str, Any]
) -> Dict[str, Any]:
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado."}
    return await main_actions.handle_text_input(user_id, text, state)


__all__ = [
    "handle_tracking_menu",
    "handle_tracking_callback",
    "handle_tracking_text_input",
]
