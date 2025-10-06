"""Handlers para configurações da recuperação."""

from __future__ import annotations

from typing import Any, Dict

try:  # Python 3.9+
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo  # type: ignore

from core.config import settings
from database.recovery import RecoveryCampaignRepository
from services.conversation_state import ConversationStateManager

from .callbacks import build_callback


def _ensure_admin(user_id: int) -> bool:
    return user_id in settings.allowed_admin_ids_list


async def handle_recovery_settings_menu(user_id: int, bot_id: int) -> Dict[str, Any]:
    if not _ensure_admin(user_id):
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    campaign = await RecoveryCampaignRepository.get_or_create(
        bot_id, created_by=user_id
    )

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "⏱ Inatividade",
                    "callback_data": build_callback(
                        "setting_inactivity", bot_id=bot_id
                    ),
                },
                {
                    "text": "🌍 Timezone",
                    "callback_data": build_callback("setting_timezone", bot_id=bot_id),
                },
            ],
            [
                {
                    "text": "✅ Ativo" if campaign.is_active else "❌ Inativo",
                    "callback_data": build_callback("setting_toggle", bot_id=bot_id),
                }
            ],
            [
                {
                    "text": (
                        "✅ Ignorar pagantes"
                        if campaign.skip_paid_users
                        else "❌ Ignorar pagantes"
                    ),
                    "callback_data": build_callback("setting_skip_paid", bot_id=bot_id),
                }
            ],
            [
                {
                    "text": "🔙 Voltar",
                    "callback_data": build_callback("select_bot", bot_id=bot_id),
                }
            ],
        ]
    }

    minutes = max(1, campaign.inactivity_threshold_seconds // 60)
    text = (
        "⚙️ *Configurações de Recuperação*\n\n"
        f"• Status: {'Ativo' if campaign.is_active else 'Inativo'}\n"
        f"• Inatividade: {minutes} min\n"
        f"• Timezone: {campaign.timezone}\n"
        f"• Ignorar clientes pagantes: {'Sim' if campaign.skip_paid_users else 'Não'}\n\n"
        "Use os botões para ajustar."
    )
    return {"text": text, "keyboard": keyboard}


async def handle_recovery_setting_toggle(user_id: int, bot_id: int) -> Dict[str, Any]:
    if not _ensure_admin(user_id):
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    campaign = await RecoveryCampaignRepository.get_or_create(
        bot_id, created_by=user_id
    )
    await RecoveryCampaignRepository.update_campaign(
        campaign.id, is_active=not campaign.is_active
    )
    await RecoveryCampaignRepository.increment_version(campaign.id)
    return await handle_recovery_settings_menu(user_id, bot_id)


async def handle_recovery_setting_inactivity(
    user_id: int, bot_id: int
) -> Dict[str, Any]:
    if not _ensure_admin(user_id):
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    campaign = await RecoveryCampaignRepository.get_or_create(
        bot_id, created_by=user_id
    )
    ConversationStateManager.set_state(
        user_id,
        "awaiting_recovery_inactivity",
        {"campaign_id": campaign.id, "bot_id": bot_id},
    )

    minutes = max(1, campaign.inactivity_threshold_seconds // 60)
    return {
        "text": (
            "⏱️ *Inatividade*\n\nDigite minutos para considerar o usuário inativo."
            f"\nAtual: {minutes} min"
        ),
        "keyboard": None,
    }


async def handle_recovery_inactivity_input(
    user_id: int, campaign_id: int, bot_id: int, text: str
) -> Dict[str, Any]:
    try:
        minutes = int(text.replace("min", "").strip())
        if minutes < 1 or minutes > 1440:
            raise ValueError
    except ValueError:
        return {"text": "❌ Informe minutos entre 1 e 1440.", "keyboard": None}

    seconds = minutes * 60
    await RecoveryCampaignRepository.update_campaign(
        campaign_id, inactivity_threshold_seconds=seconds
    )
    await RecoveryCampaignRepository.increment_version(campaign_id)
    ConversationStateManager.clear_state(user_id)
    return await handle_recovery_settings_menu(user_id, bot_id)


async def handle_recovery_setting_timezone(user_id: int, bot_id: int) -> Dict[str, Any]:
    if not _ensure_admin(user_id):
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    campaign = await RecoveryCampaignRepository.get_or_create(
        bot_id, created_by=user_id
    )
    ConversationStateManager.set_state(
        user_id,
        "awaiting_recovery_timezone",
        {"campaign_id": campaign.id, "bot_id": bot_id},
    )

    return {
        "text": (
            "🌍 *Timezone*\n\nInforme o fuso (ex.: `America/Sao_Paulo`, `UTC`)."
            f"\nAtual: {campaign.timezone}"
        ),
        "keyboard": None,
    }


async def handle_recovery_timezone_input(
    user_id: int, campaign_id: int, bot_id: int, text: str
) -> Dict[str, Any]:
    tz = text.strip()
    try:
        ZoneInfo(tz)
    except Exception:
        return {
            "text": "❌ Timezone inválido. Exemplo: America/Sao_Paulo",
            "keyboard": None,
        }

    await RecoveryCampaignRepository.update_campaign(campaign_id, timezone=tz)
    await RecoveryCampaignRepository.increment_version(campaign_id)
    ConversationStateManager.clear_state(user_id)
    return await handle_recovery_settings_menu(user_id, bot_id)


async def handle_recovery_setting_skip_paid(
    user_id: int, bot_id: int
) -> Dict[str, Any]:
    if not _ensure_admin(user_id):
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    campaign = await RecoveryCampaignRepository.get_or_create(
        bot_id, created_by=user_id
    )
    await RecoveryCampaignRepository.update_campaign(
        campaign.id,
        skip_paid_users=not campaign.skip_paid_users,
    )
    await RecoveryCampaignRepository.increment_version(campaign.id)
    return await handle_recovery_settings_menu(user_id, bot_id)
