"""
Handlers para configuração de agendamento do upsell
"""

from typing import Any, Dict

from core.config import settings
from database.repos import UpsellRepository, UpsellScheduleRepository
from services.conversation_state import ConversationStateManager


async def handle_schedule_menu(user_id: int, upsell_id: int) -> Dict[str, Any]:
    """Menu de configuração de agendamento"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    upsell = await UpsellRepository.get_upsell_by_id(upsell_id)
    if not upsell:
        return {"text": "❌ Upsell não encontrado.", "keyboard": None}

    # Upsell #1 não tem agendamento editável
    if upsell.is_pre_saved:
        return {
            "text": "⚠️ O upsell #1 é disparado por trigger da IA, não por agendamento.",
            "keyboard": {
                "inline_keyboard": [
                    [
                        {
                            "text": "🔙 Voltar",
                            "callback_data": f"upsell_select:{upsell_id}",
                        }
                    ]
                ]
            },
        }

    schedule = await UpsellScheduleRepository.get_schedule(upsell_id)

    text = f"📅 **Agendamento - {upsell.name}**\n\n"
    if schedule:
        text += f"Dias após último pagamento: {schedule.days_after}\n"
        text += f"Horas: {schedule.hours}\n"
        text += f"Minutos: {schedule.minutes}\n\n"
        total_hours = schedule.days_after * 24 + schedule.hours
        total_minutes = total_hours * 60 + schedule.minutes
        text += f"Total: ~{total_minutes} minutos ({total_hours}h)"
    else:
        text += "⚠️ Agendamento não configurado"

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "📆 Dias",
                    "callback_data": f"upsell_sched_days:{upsell_id}",
                },
                {
                    "text": "🕐 Horas",
                    "callback_data": f"upsell_sched_hours:{upsell_id}",
                },
                {
                    "text": "⏱️ Minutos",
                    "callback_data": f"upsell_sched_minutes:{upsell_id}",
                },
            ],
            [{"text": "🔙 Voltar", "callback_data": f"upsell_select:{upsell_id}"}],
        ]
    }

    return {"text": text, "keyboard": keyboard}


async def handle_schedule_days_click(user_id: int, upsell_id: int) -> Dict[str, Any]:
    """Solicita dias"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_upsell_sched_days",
        {"upsell_id": upsell_id},
    )

    return {
        "text": "📆 Digite o número de dias após o último pagamento (0-365):",
        "keyboard": None,
    }


async def handle_schedule_days_input(
    user_id: int, upsell_id: int, days: int
) -> Dict[str, Any]:
    """Salva dias"""
    await UpsellScheduleRepository.update_schedule(upsell_id, days_after=days)
    ConversationStateManager.clear_state(user_id)

    return await handle_schedule_menu(user_id, upsell_id)


async def handle_schedule_hours_click(user_id: int, upsell_id: int) -> Dict[str, Any]:
    """Solicita horas"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_upsell_sched_hours",
        {"upsell_id": upsell_id},
    )

    return {
        "text": "🕐 Digite o número de horas adicionais (0-23):",
        "keyboard": None,
    }


async def handle_schedule_hours_input(
    user_id: int, upsell_id: int, hours: int
) -> Dict[str, Any]:
    """Salva horas"""
    await UpsellScheduleRepository.update_schedule(upsell_id, hours=hours)
    ConversationStateManager.clear_state(user_id)

    return await handle_schedule_menu(user_id, upsell_id)


async def handle_schedule_minutes_click(user_id: int, upsell_id: int) -> Dict[str, Any]:
    """Solicita minutos"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_upsell_sched_minutes",
        {"upsell_id": upsell_id},
    )

    return {
        "text": "⏱️ Digite o número de minutos adicionais (0-59):",
        "keyboard": None,
    }


async def handle_schedule_minutes_input(
    user_id: int, upsell_id: int, minutes: int
) -> Dict[str, Any]:
    """Salva minutos"""
    await UpsellScheduleRepository.update_schedule(upsell_id, minutes=minutes)
    ConversationStateManager.clear_state(user_id)

    return await handle_schedule_menu(user_id, upsell_id)
