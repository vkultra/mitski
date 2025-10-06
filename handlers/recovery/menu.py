"""Menus principais da funcionalidade de recuperação."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, cast

from core.config import settings
from core.recovery import (
    ScheduleParseError,
    decode_schedule,
    encode_schedule,
    format_schedule_definition,
    parse_schedule_expression,
)
from database.recovery import (
    RecoveryBlockRepository,
    RecoveryCampaignRepository,
    RecoveryStepRepository,
)
from services.bot_registration import BotRegistrationService
from services.conversation_state import ConversationStateManager

from .callbacks import build_callback

_NUMBER_EMOJI = {
    1: "1️⃣",
    2: "2️⃣",
    3: "3️⃣",
    4: "4️⃣",
    5: "5️⃣",
    6: "6️⃣",
    7: "7️⃣",
    8: "8️⃣",
    9: "9️⃣",
    10: "🔟",
}


def _ensure_int(value: Any) -> int:
    """Return value as int, raising if None to retain type safety."""

    if isinstance(value, int):
        return value
    if value is None:
        raise ValueError("expected integer value")
    return cast(int, value)


def _ensure_str(value: Any) -> str:
    """Return value as str, raising if None to retain type safety."""

    if isinstance(value, str):
        return value
    if value is None:
        raise ValueError("expected string value")
    return cast(str, value)


def _optional_str(value: Any) -> Optional[str]:
    """Cast helper that gracefully handles optional textual fields."""

    if value is None or isinstance(value, str):
        return value
    return cast(str, value)


def _ensure_admin(user_id: int) -> bool:
    return user_id in settings.allowed_admin_ids_list


async def handle_recovery_entry(user_id: int, page: int = 1) -> Dict[str, Any]:
    if not _ensure_admin(user_id):
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    bots = await BotRegistrationService.list_bots(user_id)
    if not bots:
        return {
            "text": "📭 Você ainda não tem bots registrados.\n\nUse ➕ Adicionar Bot primeiro.",
            "keyboard": None,
        }

    per_page = 3
    start = (page - 1) * per_page
    end = start + per_page
    bots_page = bots[start:end]

    keyboard: List[List[Dict[str, str]]] = []
    for bot in bots_page:
        bot_id = _ensure_int(bot.id)
        display_name = _optional_str(getattr(bot, "display_name", None))
        username = _optional_str(getattr(bot, "username", None))
        display = display_name or (f"@{username}" if username else f"Bot #{bot_id}")
        keyboard.append(
            [
                {
                    "text": display,
                    "callback_data": build_callback("select_bot", bot_id=bot_id),
                }
            ]
        )

    nav_row: List[Dict[str, str]] = []
    if page > 1:
        nav_row.append(
            {
                "text": "← Anterior",
                "callback_data": build_callback("menu", page=page - 1),
            }
        )
    if end < len(bots):
        nav_row.append(
            {
                "text": "Próxima →",
                "callback_data": build_callback("menu", page=page + 1),
            }
        )
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([{"text": "🔙 Voltar", "callback_data": "back_to_main"}])

    return {
        "text": f"🔁 *Recuperação*\n\nSelecione o bot para configurar.\n\n(Página {page})",
        "keyboard": {"inline_keyboard": keyboard},
    }


def _order_to_emoji(order: int) -> str:
    return _NUMBER_EMOJI.get(order, f"#{order}")


async def handle_recovery_bot_menu(user_id: int, bot_id: int) -> Dict[str, Any]:
    if not _ensure_admin(user_id):
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    campaign = await RecoveryCampaignRepository.get_or_create(
        bot_id, created_by=user_id
    )
    campaign_id = _ensure_int(campaign.id)
    steps = await RecoveryStepRepository.list_steps(campaign_id)

    inline_keyboard: List[List[Dict[str, str]]] = []
    for idx, step in enumerate(steps, start=1):
        step_id = _ensure_int(step.id)
        schedule = decode_schedule(
            _ensure_str(step.schedule_type), _ensure_str(step.schedule_value)
        )
        schedule_text = format_schedule_definition(schedule)
        inline_keyboard.append(
            [
                {
                    "text": _order_to_emoji(idx),
                    "callback_data": build_callback("step_view", step_id=step_id),
                },
                {
                    "text": "Visualizar",
                    "callback_data": build_callback("step_view", step_id=step_id),
                },
                {
                    "text": f"⏱ {schedule_text}",
                    "callback_data": build_callback("step_schedule", step_id=step_id),
                },
                {
                    "text": "❌",
                    "callback_data": build_callback(
                        "step_delete_confirm", step_id=step_id
                    ),
                },
            ]
        )

    inline_keyboard.append(
        [
            {
                "text": "➕ Adicionar Recuperação",
                "callback_data": build_callback("step_add", bot_id=bot_id),
            }
        ]
    )
    inline_keyboard.append(
        [
            {
                "text": "⚙️ Configurações",
                "callback_data": build_callback("settings", bot_id=bot_id),
            }
        ]
    )
    inline_keyboard.append(
        [{"text": "🔙 Voltar", "callback_data": build_callback("menu")}]
    )

    status_emoji = "✅" if bool(campaign.is_active) else "❌"
    inactivity_seconds = _ensure_int(campaign.inactivity_threshold_seconds)
    skip_paid_users = bool(campaign.skip_paid_users)
    campaign_bot_id = _ensure_int(campaign.bot_id)
    info_text = (
        f"{status_emoji} *Recuperação do Bot #{campaign_bot_id}*\n"
        f"Inatividade: {inactivity_seconds // 60} min\n"
        f"Ignorar pagantes: {'Sim' if skip_paid_users else 'Não'}\n"
        f"Total de mensagens: {len(steps)}"
    )

    return {"text": info_text, "keyboard": {"inline_keyboard": inline_keyboard}}


async def handle_recovery_add_step(user_id: int, bot_id: int) -> Dict[str, Any]:
    if not _ensure_admin(user_id):
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    campaign = await RecoveryCampaignRepository.get_or_create(
        bot_id, created_by=user_id
    )
    campaign_id = _ensure_int(campaign.id)
    default_schedule = encode_schedule(parse_schedule_expression("10m"))
    step = await RecoveryStepRepository.create_step(
        campaign_id, default_schedule[0], default_schedule[1]
    )
    await RecoveryCampaignRepository.increment_version(campaign_id)
    await RecoveryBlockRepository.create_block(_ensure_int(step.id))
    return await handle_recovery_bot_menu(user_id, bot_id)


async def handle_recovery_schedule_prompt(user_id: int, step_id: int) -> Dict[str, Any]:
    if not _ensure_admin(user_id):
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    step = await RecoveryStepRepository.get_step(step_id)
    if not step:
        return {"text": "❌ Recuperação não encontrada.", "keyboard": None}

    schedule = decode_schedule(
        _ensure_str(step.schedule_type), _ensure_str(step.schedule_value)
    )
    current_text = format_schedule_definition(schedule)

    ConversationStateManager.set_state(
        user_id,
        "awaiting_recovery_schedule",
        {"step_id": step_id, "campaign_id": _ensure_int(step.campaign_id)},
    )

    return {
        "text": (
            "⏱️ *Horário da Recuperação*\n\n"
            "Envie o momento em que este passo deve ser disparado após a inatividade.\n"
            "Você pode usar:\n"
            "• Delays relativos: `10m`, `45 minutos`, `2h`, `1 dia`\n"
            "• Amanhã em horário fixo: `amanhã 09:00`\n"
            "• Dias à frente: `+2d18:00` (depois de amanhã às 18h), `+3d 08:30`, `+7d12:00`\n"
            "• Horário no mesmo dia (se ainda não passou): `14:15`\n\n"
            "Dica: os delays são relativos ao momento em que o usuário se torna inativo.\n"
            f"Atual: `{current_text}`"
        ),
        "keyboard": None,
    }


async def handle_recovery_schedule_input(
    user_id: int, step_id: int, campaign_id: int, text: str
) -> Dict[str, Any]:
    if not _ensure_admin(user_id):
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    try:
        definition = parse_schedule_expression(text)
    except ScheduleParseError as error:
        return {"text": f"❌ {error}", "keyboard": None}

    schedule_type, schedule_value = encode_schedule(definition)
    step = await RecoveryStepRepository.update_schedule(
        step_id, schedule_type, schedule_value
    )
    if step:
        await RecoveryCampaignRepository.increment_version(
            _ensure_int(step.campaign_id)
        )
    ConversationStateManager.clear_state(user_id)

    campaign = await RecoveryCampaignRepository.get_by_id(campaign_id)
    if campaign:
        return await handle_recovery_bot_menu(user_id, _ensure_int(campaign.bot_id))

    return {
        "text": "✅ Horário atualizado.",
        "keyboard": None,
    }


async def handle_recovery_delete_confirm(user_id: int, step_id: int) -> Dict[str, Any]:
    if not _ensure_admin(user_id):
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    step = await RecoveryStepRepository.get_step(step_id)
    if not step:
        return {"text": "❌ Recuperação não encontrada.", "keyboard": None}

    step_id_real = _ensure_int(step.id)
    cancel_cb = build_callback("step_view", step_id=step_id_real)
    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Sim, excluir",
                    "callback_data": build_callback(
                        "step_delete", step_id=step_id_real
                    ),
                },
                {"text": "🔙 Cancelar", "callback_data": cancel_cb},
            ]
        ]
    }
    return {
        "text": "🗑️ Deseja realmente excluir esta recuperação?",
        "keyboard": keyboard,
    }


async def handle_recovery_delete_step(user_id: int, step_id: int) -> Dict[str, Any]:
    if not _ensure_admin(user_id):
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    campaign_id = await RecoveryStepRepository.delete_step(step_id)
    if not campaign_id:
        return {"text": "❌ Recuperação não encontrada.", "keyboard": None}

    await RecoveryCampaignRepository.increment_version(campaign_id)
    campaign = await RecoveryCampaignRepository.get_by_id(campaign_id)
    if campaign:
        return await handle_recovery_bot_menu(user_id, _ensure_int(campaign.bot_id))

    return {
        "text": "✅ Recuperação removida.",
        "keyboard": None,
    }
