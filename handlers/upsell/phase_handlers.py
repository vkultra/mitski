"""
Handlers para configuração de fase do upsell
"""

from typing import Any, Dict

from core.config import settings
from database.repos import UpsellPhaseConfigRepository, UpsellRepository
from services.conversation_state import ConversationStateManager


async def handle_phase_menu(user_id: int, upsell_id: int) -> Dict[str, Any]:
    """Menu de configuração de fase"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    upsell = await UpsellRepository.get_upsell_by_id(upsell_id)
    if not upsell:
        return {"text": "❌ Upsell não encontrado.", "keyboard": None}

    phase_config = await UpsellPhaseConfigRepository.get_phase_config(upsell_id)

    text = f"🎭 **Fase - {upsell.name}**\n\n"
    if phase_config and phase_config.phase_prompt:
        text += f"Prompt atual:\n{phase_config.phase_prompt[:200]}...\n\n"
    else:
        text += "⚠️ Prompt não configurado\n\n"

    text += "O prompt define como a IA deve se comportar durante este upsell."

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "✏️ Editar Prompt",
                    "callback_data": f"upsell_phase_edit:{upsell_id}",
                }
            ],
            [{"text": "🔙 Voltar", "callback_data": f"upsell_select:{upsell_id}"}],
        ]
    }

    return {"text": text, "keyboard": keyboard}


async def handle_phase_edit_click(user_id: int, upsell_id: int) -> Dict[str, Any]:
    """Solicita prompt da fase"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_upsell_phase_prompt",
        {"upsell_id": upsell_id},
    )

    return {
        "text": '🎭 Digite o prompt da fase:\n\nExemplo: "Você está oferecendo o pacote premium. Seja direto e destaque os benefícios exclusivos."',
        "keyboard": None,
    }


async def handle_phase_prompt_input(
    user_id: int, upsell_id: int, prompt: str
) -> Dict[str, Any]:
    """Salva prompt da fase"""
    await UpsellPhaseConfigRepository.create_or_update_phase(upsell_id, prompt)
    ConversationStateManager.clear_state(user_id)

    return {
        "text": "✅ Prompt da fase atualizado!",
        "keyboard": {
            "inline_keyboard": [
                [{"text": "🔙 Voltar", "callback_data": f"upsell_phase:{upsell_id}"}]
            ]
        },
    }
