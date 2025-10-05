"""
Handlers para configuração de trigger do upsell #1
"""

from typing import Any, Dict

from core.config import settings
from database.repos import UpsellRepository
from services.conversation_state import ConversationStateManager
from services.upsell import UpsellService


async def handle_trigger_menu(user_id: int, upsell_id: int) -> Dict[str, Any]:
    """Menu de configuração de trigger"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    upsell = await UpsellRepository.get_upsell_by_id(upsell_id)
    if not upsell:
        return {"text": "❌ Upsell não encontrado.", "keyboard": None}

    # Apenas upsell #1 tem trigger
    if not upsell.is_pre_saved:
        return {
            "text": "⚠️ Apenas o upsell #1 usa trigger. Upsells #2+ usam agendamento.",
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

    text = f"🎯 **Trigger - {upsell.name}**\n\n"
    if upsell.upsell_trigger:
        text += f"Trigger atual: `{upsell.upsell_trigger}`\n\n"
    else:
        text += "⚠️ Trigger não configurado\n\n"

    text += (
        "Quando a IA mencionar este termo, o anúncio será enviado automaticamente.\n\n"
    )
    text += "💡 Dica: Use termos únicos que não aparecem em conversas normais (ex: `premium-kit`, `vip2024`)."

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "✏️ Editar Trigger",
                    "callback_data": f"upsell_trigger_edit:{upsell_id}",
                }
            ],
            [{"text": "🔙 Voltar", "callback_data": f"upsell_select:{upsell_id}"}],
        ]
    }

    return {"text": text, "keyboard": keyboard}


async def handle_trigger_edit_click(user_id: int, upsell_id: int) -> Dict[str, Any]:
    """Solicita trigger"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_upsell_trigger",
        {"upsell_id": upsell_id},
    )

    return {
        "text": "🎯 Digite o termo trigger (mínimo 3 caracteres):\n\nExemplo: `premium-kit`, `vip-upgrade`, `bonus2024`",
        "keyboard": None,
    }


async def handle_trigger_input(
    user_id: int, upsell_id: int, bot_id: int, trigger: str
) -> Dict[str, Any]:
    """Salva trigger"""
    # Validar trigger
    validation = await UpsellService.validate_trigger(
        bot_id, trigger, exclude_upsell_id=upsell_id
    )

    if not validation["valid"]:
        return {
            "text": f"❌ {validation['error']}\n\nTente novamente:",
            "keyboard": None,
        }

    await UpsellRepository.update_upsell(upsell_id, upsell_trigger=trigger)
    ConversationStateManager.clear_state(user_id)

    return {
        "text": f"✅ Trigger configurado: `{trigger}`\n\nQuando a IA mencionar este termo, o anúncio será enviado.",
        "keyboard": {
            "inline_keyboard": [
                [{"text": "🔙 Voltar", "callback_data": f"upsell_trigger:{upsell_id}"}]
            ]
        },
    }
