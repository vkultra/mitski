"""
Handlers para configuração de valor do upsell
"""

from typing import Any, Dict

from core.config import settings
from database.repos import UpsellRepository
from services.conversation_state import ConversationStateManager


async def handle_value_click(user_id: int, upsell_id: int) -> Dict[str, Any]:
    """Solicita valor do upsell"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    upsell = await UpsellRepository.get_upsell_by_id(upsell_id)
    if not upsell:
        return {"text": "❌ Upsell não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_upsell_value",
        {"upsell_id": upsell_id},
    )

    current_value = f"\n\nValor atual: {upsell.value}" if upsell.value else ""

    return {
        "text": f"💰 **Configurar Valor**{current_value}\n\nDigite o valor do upsell:\n\nExemplo: `R$ 47,00` ou `47.00`",
        "keyboard": None,
    }


async def handle_value_input(
    user_id: int, upsell_id: int, value: str
) -> Dict[str, Any]:
    """Salva valor do upsell"""
    await UpsellRepository.update_upsell(upsell_id, value=value)
    ConversationStateManager.clear_state(user_id)

    return {
        "text": f"✅ Valor atualizado para: {value}",
        "keyboard": {
            "inline_keyboard": [
                [{"text": "🔙 Voltar", "callback_data": f"upsell_select:{upsell_id}"}]
            ]
        },
    }
