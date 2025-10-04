"""
Handlers para configuração de IA
"""

from typing import Any, Dict

from core.config import settings
from services.ai.config import AIConfigService
from services.bot_registration import BotRegistrationService
from services.conversation_state import ConversationStateManager


async def handle_ai_menu_click(user_id: int) -> Dict[str, Any]:
    """Handler quando usuário clica no botão IA"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    return await handle_select_bot_for_ai(user_id, page=1)


async def handle_select_bot_for_ai(user_id: int, page: int = 1) -> Dict[str, Any]:
    """Lista bots para seleção (3 por página)"""
    bots = await BotRegistrationService.list_bots(user_id)

    if not bots:
        return {
            "text": "📭 Você não tem bots registrados.\n\nAdicione um bot primeiro.",
            "keyboard": None,
        }

    per_page = 3
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    bots_page = bots[start_idx:end_idx]

    buttons = []
    for bot in bots_page:
        display = (
            f"{bot.display_name} (@{bot.username})"
            if bot.display_name
            else f"@{bot.username}"
        )
        buttons.append([{"text": display, "callback_data": f"ai_select_bot:{bot.id}"}])

    nav_buttons = []
    if page > 1:
        nav_buttons.append(
            {"text": "← Anterior", "callback_data": f"ai_bots_page:{page-1}"}
        )
    if end_idx < len(bots):
        nav_buttons.append(
            {"text": "Próxima →", "callback_data": f"ai_bots_page:{page+1}"}
        )

    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([{"text": "🔙 Voltar", "callback_data": "back_to_main"}])

    return {
        "text": f"🤖 Selecione um bot para configurar a IA:\n\n(Página {page})",
        "keyboard": {"inline_keyboard": buttons},
    }


async def handle_bot_selected_for_ai(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Menu de configuração de IA do bot"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    config = await AIConfigService.get_or_create_config(bot_id)

    model_label = (
        "🧠 Reasoning" if config.model_type == "reasoning" else "⚡ Non-Reasoning"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "📝 Comportamento Geral",
                    "callback_data": f"ai_general_prompt:{bot_id}",
                }
            ],
            [{"text": "📋 Gerenciar Fases", "callback_data": f"ai_list_phases:{bot_id}"}],
            [
                {
                    "text": f"🔄 Modelo: {model_label}",
                    "callback_data": f"ai_toggle_model:{bot_id}",
                }
            ],
            [{"text": "🔙 Voltar", "callback_data": "ai_menu"}],
        ]
    }

    return {
        "text": f"⚙️ Configuração de IA\n\nModelo: {model_label}\nStatus: {'✅ Ativo' if config.is_enabled else '❌ Inativo'}",
        "keyboard": keyboard,
    }


async def handle_general_prompt_click(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Solicita prompt de comportamento geral"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id, "awaiting_general_prompt", {"bot_id": bot_id}
    )

    return {
        "text": '📝 *Comportamento Geral da IA*\n\nDigite o prompt que define como a IA deve se comportar:\n\nExemplo: "Você é um assistente de vendas educado. Sempre ofereça produtos relacionados."',
        "keyboard": None,
    }


async def handle_general_prompt_input(
    user_id: int, bot_id: int, prompt: str
) -> Dict[str, Any]:
    """Salva prompt geral"""
    await AIConfigService.update_general_prompt(bot_id, prompt)
    ConversationStateManager.clear_state(user_id)

    return {"text": "✅ Comportamento geral atualizado!", "keyboard": None}


async def handle_create_phase_click(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Inicia criação de fase"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id, "awaiting_phase_name", {"bot_id": bot_id}
    )

    return {
        "text": "➕ *Criar Nova Fase*\n\nDigite o nome da fase:\n\nExemplo: `Negociação`, `Fechamento`, `Suporte`",
        "keyboard": None,
    }


async def handle_phase_name_input(
    user_id: int, bot_id: int, name: str
) -> Dict[str, Any]:
    """Processa nome da fase"""
    name = name.strip()

    if len(name) < 3:
        return {
            "text": "❌ Nome muito curto. Use pelo menos 3 caracteres.\n\nTente novamente:",
            "keyboard": None,
        }

    ConversationStateManager.set_state(
        user_id, "awaiting_phase_trigger", {"bot_id": bot_id, "name": name}
    )

    return {
        "text": f'✅ Nome: `{name}`\n\nAgora digite um termo único (gatilho):\n\n⚠️ Preferir termos não comuns:\n• `fcf4`\n• `eko3`\n• `zx9p`\n\nQuando a IA retornar este termo, a fase mudará automaticamente.',
        "keyboard": None,
    }


async def handle_phase_trigger_input(
    user_id: int, bot_id: int, name: str, trigger: str
) -> Dict[str, Any]:
    """Processa trigger da fase"""
    trigger = trigger.strip()

    if len(trigger) < 3:
        return {
            "text": "❌ Trigger muito curto. Use pelo menos 3 caracteres.\n\nTente novamente:",
            "keyboard": None,
        }

    from database.repos import AIPhaseRepository

    existing = await AIPhaseRepository.get_phase_by_trigger(bot_id, trigger)

    if existing:
        return {
            "text": f"❌ O trigger `{trigger}` já existe.\n\nEscolha outro termo:",
            "keyboard": None,
        }

    ConversationStateManager.set_state(
        user_id,
        "awaiting_phase_prompt",
        {"bot_id": bot_id, "name": name, "trigger": trigger},
    )

    return {
        "text": f'✅ Nome: `{name}`\n✅ Trigger: `{trigger}`\n\nAgora digite o prompt desta fase:\n\nExemplo: "Agora você está na fase de fechamento. Seja direto ao oferecer o produto."',
        "keyboard": None,
    }


async def handle_phase_prompt_input(
    user_id: int, bot_id: int, name: str, trigger: str, prompt: str
) -> Dict[str, Any]:
    """Salva prompt da fase"""
    await AIConfigService.create_phase(bot_id, name, prompt, trigger, is_initial=False)
    ConversationStateManager.clear_state(user_id)

    return {
        "text": f"✅ Fase `{name}` criada!\n\nQuando a IA retornar `{trigger}`, esta fase será ativada.",
        "keyboard": None,
    }


async def handle_toggle_model(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Alterna entre reasoning e non-reasoning"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    new_type = await AIConfigService.toggle_model(bot_id)

    label = "🧠 Reasoning" if new_type == "reasoning" else "⚡ Non-Reasoning"

    return {
        "text": f"✅ Modelo alterado para: {label}\n\nAs próximas mensagens usarão este modelo.\nO histórico foi mantido.",
        "keyboard": None,
    }
