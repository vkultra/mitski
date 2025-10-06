"""Fluxos do menu de notificações no bot gerenciador."""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from core.telemetry import logger
from database.notifications.repos import NotificationSettingsRepository
from database.notifications.models import NotificationSettings
from database.repos import BotRepository
from services.bot_registration import BotRegistrationService
from services.conversation_state import ConversationStateManager

from .validation import (
    NotificationValidationError,
    format_settings_summary,
    send_test_notification,
    validate_and_save_channel,
)

def _build_keyboard(rows: List[List[Dict[str, str]]]) -> Dict[str, List[List[Dict[str, str]]]]:
    return {"inline_keyboard": rows}


async def handle_notifications_menu(user_id: int) -> Dict[str, any]:
    bots = await BotRegistrationService.list_bots(user_id)
    settings_list = await NotificationSettingsRepository.list_for_owner(user_id)
    summary = format_settings_summary(settings_list, bots)
    text = (
        "🔔 *Notificações de Vendas*\n\n"
        "Configure um canal para receber alertas sempre que uma venda for aprovada.\n"
        "Adicione este bot gerenciador como administrador do canal, conceda permissão de enviar mensagens e informe o identificador abaixo.\n\n"
        f"{summary}\n\n"
        "Escolha uma das opções para continuar."
    )
    keyboard = _build_keyboard(
        [
            [{"text": "📡 Definir/Alterar Canal", "callback_data": "notifications_configure"}],
            [{"text": "👁 Ver Configuração", "callback_data": "notifications_view"}],
            [{"text": "🚫 Desativar", "callback_data": "notifications_disable"}],
            [{"text": "🧪 Enviar Teste", "callback_data": "notifications_test"}],
        ]
    )
    return {"text": text, "keyboard": keyboard, "parse_mode": "Markdown"}


async def handle_notifications_view(user_id: int) -> Dict[str, any]:
    bots = await BotRegistrationService.list_bots(user_id)
    settings_list = await NotificationSettingsRepository.list_for_owner(user_id)

    if not settings_list:
        text = (
            "📭 Nenhuma configuração de notificação encontrada.\n\n"
            "Use a opção *Definir/Alterar Canal* para cadastrar um canal."
        )
    else:
        summary = format_settings_summary(settings_list, bots)
        text = f"📊 *Resumo das notificações*\n\n{summary}"
    keyboard = _build_keyboard(
        [[{"text": "⬅️ Voltar", "callback_data": "notifications_menu"}]]
    )
    return {"text": text, "keyboard": keyboard, "parse_mode": "Markdown"}


async def handle_notifications_configure(user_id: int) -> Dict[str, any]:
    bots = await BotRegistrationService.list_bots(user_id)

    rows: List[List[Dict[str, str]]] = [
        [
            {
                "text": "🌐 Padrão (todos os bots)",
                "callback_data": "notifications_configure_default",
            }
        ]
    ]

    for bot in bots:
        label = bot.display_name or (
            f"@{bot.username}" if bot.username else f"Bot {bot.id}"
        )
        rows.append(
            [
                {
                    "text": f"🤖 {label}",
                    "callback_data": f"notifications_configure_bot:{bot.id}",
                }
            ]
        )

    rows.append([{"text": "⬅️ Voltar", "callback_data": "notifications_menu"}])

    text = (
        "Selecione para qual bot deseja definir o canal.\n"
        "A configuração padrão é usada quando um bot não possui canal específico."
    )
    return {"text": text, "keyboard": _build_keyboard(rows)}


async def _ensure_bot_ownership(user_id: int, bot_id: Optional[int]) -> Optional[int]:
    if bot_id is None:
        return None

    bot = BotRepository.get_bot_by_id_sync(bot_id)
    if not bot or bot.admin_id != user_id:
        raise NotificationValidationError("Você não pode alterar notificações deste bot.")
    return bot_id


async def handle_notifications_configure_scope(
    user_id: int, bot_id: Optional[int]
) -> Dict[str, any]:
    await _ensure_bot_ownership(user_id, bot_id)

    ConversationStateManager.set_state(
        user_id,
        "notifications:awaiting_channel",
        {"bot_id": bot_id},
    )

    target = "padrão para todos os bots" if bot_id is None else f"bot {bot_id}"

    text = (
        f"📡 *Configurar canal ({target})*\n\n"
        "1. Adicione este bot gerenciador como administrador do canal.\n"
        "2. Garanta permissão de enviar mensagens.\n"
        "3. Envie aqui o ID numérico (ex.: -1001234567890) ou @username do canal.\n\n"
        "Assim que validarmos, o canal receberá uma mensagem de confirmação."
    )

    return {
        "text": text,
        "keyboard": None,
        "parse_mode": "Markdown",
    }


async def handle_notifications_disable(user_id: int) -> Dict[str, any]:
    bots = await BotRegistrationService.list_bots(user_id)

    rows: List[List[Dict[str, str]]] = [
        [
            {
                "text": "🌐 Desativar padrão",
                "callback_data": "notifications_disable_default",
            }
        ]
    ]

    for bot in bots:
        label = bot.display_name or (
            f"@{bot.username}" if bot.username else f"Bot {bot.id}"
        )
        rows.append(
            [
                {
                    "text": f"🚫 {label}",
                    "callback_data": f"notifications_disable_bot:{bot.id}",
                }
            ]
        )

    rows.append([{"text": "⬅️ Voltar", "callback_data": "notifications_menu"}])
    text = "Selecione a configuração que deseja desativar."
    return {"text": text, "keyboard": _build_keyboard(rows)}


async def handle_notifications_disable_scope(
    user_id: int, bot_id: Optional[int]
) -> Dict[str, any]:
    await _ensure_bot_ownership(user_id, bot_id)

    updated = await NotificationSettingsRepository.disable(user_id, bot_id)

    if updated:
        target = "padrão" if bot_id is None else f"bot {bot_id}"
        text = f"✅ Notificações do {target} desativadas."
    else:
        text = "ℹ️ Não havia notificações ativas para esse escopo."

    keyboard = _build_keyboard(
        [[{"text": "⬅️ Voltar", "callback_data": "notifications_menu"}]]
    )
    return {"text": text, "keyboard": keyboard}


async def handle_notifications_test(user_id: int) -> Dict[str, any]:
    bots = await BotRegistrationService.list_bots(user_id)

    rows: List[List[Dict[str, str]]] = [
        [
            {
                "text": "🌐 Testar padrão",
                "callback_data": "notifications_test_default",
            }
        ]
    ]

    for bot in bots:
        label = bot.display_name or (
            f"@{bot.username}" if bot.username else f"Bot {bot.id}"
        )
        rows.append(
            [
                {
                    "text": f"🧪 {label}",
                    "callback_data": f"notifications_test_bot:{bot.id}",
                }
            ]
        )

    rows.append([{"text": "⬅️ Voltar", "callback_data": "notifications_menu"}])
    text = "Escolha qual configuração deseja testar."
    return {"text": text, "keyboard": _build_keyboard(rows)}


async def handle_notifications_test_scope(
    user_id: int, bot_id: Optional[int]
) -> Dict[str, any]:
    await _ensure_bot_ownership(user_id, bot_id)

    settings_obj: Optional[NotificationSettings]
    if bot_id is None:
        settings_obj = await NotificationSettingsRepository.get_default(user_id)
    else:
        settings_obj = await NotificationSettingsRepository.get_for_owner(user_id, bot_id)

    if not settings_obj or not settings_obj.enabled or not settings_obj.channel_id:
        return {
            "text": "⚠️ Configure um canal ativo antes de executar o teste.",
            "keyboard": _build_keyboard(
                [[{"text": "Configurar agora", "callback_data": "notifications_configure"}]]
            ),
        }

    try:
        await send_test_notification(user_id, bot_id, settings_obj)
        text = "✅ Mensagem de teste enviada para o canal configurado."
    except NotificationValidationError as exc:
        text = f"❌ Não foi possível enviar o teste: {exc}"

    keyboard = _build_keyboard(
        [[{"text": "⬅️ Voltar", "callback_data": "notifications_menu"}]]
    )
    return {"text": text, "keyboard": keyboard}


async def handle_notifications_text_input(
    user_id: int, text: str, state_data: Dict[str, any]
) -> Dict[str, any]:
    bot_id = state_data.get("data", {}).get("bot_id")

    try:
        await _ensure_bot_ownership(user_id, bot_id)
        response = await validate_and_save_channel(user_id, bot_id, text)
        ConversationStateManager.clear_state(user_id)
        return response
    except NotificationValidationError as exc:
        logger.warning(
            "Notification configuration failed",
            extra={"user_id": user_id, "error": str(exc)},
        )
        return {
            "text": f"❌ {exc}\n\nEnvie outro ID de canal ou toque em ⬅️ Voltar.",
            "keyboard": _build_keyboard(
                [[{"text": "⬅️ Voltar", "callback_data": "notifications_menu"}]]
            ),
        }


__all__ = [
    "handle_notifications_menu",
    "handle_notifications_view",
    "handle_notifications_configure",
    "handle_notifications_configure_scope",
    "handle_notifications_disable",
    "handle_notifications_disable_scope",
    "handle_notifications_test",
    "handle_notifications_test_scope",
    "handle_notifications_text_input",
]
