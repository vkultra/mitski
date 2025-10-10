"""Validação e utilidades do fluxo de notificações."""

from __future__ import annotations

import re
from typing import Dict, Iterable, Optional

from core.config import settings
from core.notifications.dispatcher import TelegramNotificationClient
from core.notifications.renderer import SaleMessageData, render_sale_message
from core.telemetry import logger
from database.notifications.models import NotificationSettings
from database.notifications.repos import NotificationSettingsRepository
from database.repos import BotRepository

CHANNEL_PATTERN = re.compile(r"(-?\d+)|(?:@?[A-Za-z0-9_]{5,})")


class NotificationValidationError(Exception):
    """Erro controlado para validação de notificações."""


def format_settings_summary(
    settings_list: Iterable[NotificationSettings], bots: Iterable
) -> str:
    bot_map = {bot.id: bot for bot in bots}
    summary_lines: list[str] = []

    default_setting = next(
        (setting for setting in settings_list if setting.bot_id is None), None
    )
    if default_setting:
        status = (
            "Ativo"
            if default_setting.enabled and default_setting.channel_id
            else "Inativo"
        )
        channel = (
            f"`{default_setting.channel_id}`" if default_setting.channel_id else "—"
        )
        summary_lines.append(f"• Padrão: {status} (canal {channel})")
    else:
        summary_lines.append("• Padrão: não configurado")

    for setting in settings_list:
        if setting.bot_id is None:
            continue
        bot = bot_map.get(setting.bot_id)
        bot_label = bot.display_name or (
            f"@{bot.username}" if bot and bot.username else f"Bot {setting.bot_id}"
        )
        status = "Ativo" if setting.enabled and setting.channel_id else "Inativo"
        channel = f"`{setting.channel_id}`" if setting.channel_id else "—"
        summary_lines.append(f"• {bot_label}: {status} (canal {channel})")

    return "\n".join(summary_lines)


def _parse_channel_identifier(raw: str) -> str | int:
    cleaned = raw.strip()
    if cleaned.startswith("https://t.me/"):
        cleaned = cleaned.split("/", maxsplit=3)[-1]
    match = CHANNEL_PATTERN.fullmatch(cleaned)
    if not match:
        raise NotificationValidationError(
            "Informe apenas o ID numérico (ex.: -1001234567890) ou @username do canal."
        )
    if cleaned.lstrip("-").isdigit():
        return int(cleaned)
    if not cleaned.startswith("@"):
        cleaned = f"@{cleaned}"
    return cleaned


def _back_keyboard() -> Dict[str, list[list[dict[str, str]]]]:
    return {
        "inline_keyboard": [
            [{"text": "⬅️ Voltar", "callback_data": "notifications_menu"}]
        ]
    }


async def validate_and_save_channel(
    user_id: int, bot_id: Optional[int], raw_channel: str
) -> Dict[str, any]:
    if not settings.MANAGER_BOT_TOKEN:
        raise NotificationValidationError(
            "Configure a variável MANAGER_BOT_TOKEN antes de definir notificações."
        )

    identifier = _parse_channel_identifier(raw_channel)
    client = TelegramNotificationClient(settings.MANAGER_BOT_TOKEN)

    try:
        chat = client.get_chat(identifier)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to fetch chat for notifications",
            extra={"user_id": user_id, "channel": raw_channel, "error": str(exc)},
        )
        raise NotificationValidationError(
            "Não foi possível encontrar esse canal. Verifique o identificador."
        )

    if chat.get("type") != "channel":
        raise NotificationValidationError("Informe um canal público ou privado válido.")

    channel_id = chat["id"]

    preview_text = "✅ Canal validado! As próximas vendas aprovadas aparecerão aqui."
    try:
        client.send_message(int(channel_id), preview_text)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to send validation message",
            extra={"channel_id": channel_id, "error": str(exc)},
        )
        raise NotificationValidationError(
            "Não consegui enviar mensagem no canal. Verifique se este bot é administrador."
        )

    record = await NotificationSettingsRepository.upsert_channel(
        owner_user_id=user_id,
        channel_id=channel_id,
        bot_id=bot_id,
    )

    scope = "padrão" if bot_id is None else f"bot {bot_id}"
    text = (
        f"✅ Canal salvo para notificações ({scope}).\n"
        f"ID: `{channel_id}`\n\n"
        "O canal já recebeu uma mensagem de confirmação."
    )

    return {"text": text, "keyboard": _back_keyboard(), "parse_mode": "Markdown"}


async def send_test_notification(
    user_id: int,
    bot_id: Optional[int],
    settings_obj: NotificationSettings,
) -> None:
    if not settings.MANAGER_BOT_TOKEN:
        raise NotificationValidationError("Token do bot gerenciador não configurado.")

    bot_username = None
    if bot_id is not None:
        bot = BotRepository.get_bot_by_id_sync(bot_id)
        if not bot or bot.admin_id != user_id:
            raise NotificationValidationError("Você não tem acesso a este bot.")
        bot_username = bot.username

    message = render_sale_message(
        SaleMessageData(
            amount_cents=1990,
            buyer_username="cliente_teste",
            buyer_user_id=999999,
            bot_username=bot_username or "bot_gerenciador",
            is_upsell=False,
        )
    )

    client = TelegramNotificationClient(settings.MANAGER_BOT_TOKEN)
    try:
        client.send_message(int(settings_obj.channel_id), message)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Failed to deliver test notification",
            extra={
                "channel_id": settings_obj.channel_id,
                "bot_id": bot_id,
                "error": str(exc),
            },
        )
        raise NotificationValidationError(
            "Não foi possível enviar a mensagem de teste. Verifique permissões do canal."
        )


__all__ = [
    "NotificationValidationError",
    "format_settings_summary",
    "validate_and_save_channel",
    "send_test_notification",
]
