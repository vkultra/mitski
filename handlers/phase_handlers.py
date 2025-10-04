"""
Handlers para gerenciamento de fases de IA

Responsável por:
- Criar fase inicial
- Listar fases
- Visualizar fase
- Editar fase
- Deletar fase
- Definir fase inicial
"""

from typing import Any, Dict

from core.config import settings
from services.ai.phase_service import AIPhaseService
from services.conversation_state import ConversationStateManager


async def handle_create_initial_phase_click(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Inicia criação de fase inicial (pede apenas o prompt)"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    # Verificar se já existe fase inicial
    existing_initial = await AIPhaseService.get_initial_phase(bot_id)
    if existing_initial:
        return {
            "text": f"⚠️ Já existe uma fase inicial: `{existing_initial.phase_name}`\n\nDelete-a primeiro para criar uma nova.",
            "keyboard": None,
        }

    ConversationStateManager.set_state(
        user_id, "awaiting_initial_phase_prompt", {"bot_id": bot_id}
    )

    return {
        "text": "⭐ *Criar Fase Inicial*\n\nA fase inicial sempre começa quando um novo usuário interage com o bot.\n\nDigite o prompt desta fase:\n\nExemplo: \"Você está na fase de boas-vindas. Seja amigável e pergunte como pode ajudar.\"",
        "keyboard": None,
    }


async def handle_initial_phase_prompt_input(
    user_id: int, bot_id: int, prompt: str
) -> Dict[str, Any]:
    """Salva fase inicial com nome fixo 'Inicial'"""
    try:
        await AIPhaseService.create_phase(
            bot_id=bot_id, name="Inicial", prompt=prompt, trigger=None, is_initial=True
        )
        ConversationStateManager.clear_state(user_id)

        return {
            "text": "✅ Fase inicial criada!\n\nTodos os novos usuários começarão nesta fase.",
            "keyboard": None,
        }
    except ValueError as e:
        return {"text": f"❌ Erro: {str(e)}", "keyboard": None}


async def handle_list_phases(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Lista todas as fases do bot"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    phases = await AIPhaseService.list_phases(bot_id)

    if not phases:
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "⭐ Criar Fase Inicial",
                        "callback_data": f"ai_create_initial:{bot_id}",
                    }
                ],
                [
                    {
                        "text": "➕ Criar Fase",
                        "callback_data": f"ai_create_phase:{bot_id}",
                    }
                ],
                [{"text": "🔙 Voltar", "callback_data": f"ai_select_bot:{bot_id}"}],
            ]
        }

        return {
            "text": "📭 Nenhuma fase criada ainda.\n\n⭐ Crie primeiro uma **fase inicial** para novos usuários.\n\n➕ Depois crie fases adicionais com triggers.",
            "keyboard": keyboard,
        }

    buttons = []

    # Separar fase inicial das demais
    initial_phase = next((p for p in phases if p.is_initial), None)
    regular_phases = [p for p in phases if not p.is_initial]

    # Mostrar fase inicial primeiro
    if initial_phase:
        buttons.append(
            [
                {
                    "text": f"⭐ {initial_phase.phase_name} (Inicial)",
                    "callback_data": f"ai_view_phase:{initial_phase.id}",
                }
            ]
        )

    # Mostrar fases regulares
    for phase in regular_phases:
        buttons.append(
            [
                {
                    "text": f"{phase.phase_name} ({phase.phase_trigger})",
                    "callback_data": f"ai_view_phase:{phase.id}",
                }
            ]
        )

    # Botões de ação
    if not initial_phase:
        buttons.append(
            [
                {
                    "text": "⭐ Criar Fase Inicial",
                    "callback_data": f"ai_create_initial:{bot_id}",
                }
            ]
        )

    buttons.append(
        [{"text": "➕ Criar Fase", "callback_data": f"ai_create_phase:{bot_id}"}]
    )
    buttons.append([{"text": "🔙 Voltar", "callback_data": f"ai_select_bot:{bot_id}"}])

    return {
        "text": f"📋 **Fases Criadas** ({len(phases)} total)\n\n{'⭐ Fase inicial configurada' if initial_phase else '⚠️ Sem fase inicial'}",
        "keyboard": {"inline_keyboard": buttons},
    }


async def handle_view_phase(user_id: int, phase_id: int) -> Dict[str, Any]:
    """Visualiza detalhes de uma fase"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    phase = await AIPhaseService.get_phase_by_id(phase_id)

    if not phase:
        return {"text": "❌ Fase não encontrada.", "keyboard": None}

    # Texto descritivo
    if phase.is_initial:
        text = f"⭐ **{phase.phase_name}** (Fase Inicial)\n\n"
        text += "📝 **Prompt:**\n{}\n\n".format(phase.phase_prompt)
        text += "ℹ️ Todos os novos usuários começam nesta fase."
    else:
        text = f"📋 **{phase.phase_name}**\n\n"
        text += f"🔑 **Trigger:** `{phase.phase_trigger}`\n\n"
        text += "📝 **Prompt:**\n{}\n\n".format(phase.phase_prompt)
        text += f"ℹ️ Quando a IA retornar `{phase.phase_trigger}`, esta fase será ativada."

    # Botões de ação
    buttons = []

    if not phase.is_initial:
        buttons.append(
            [
                {
                    "text": "⭐ Definir como Inicial",
                    "callback_data": f"ai_set_initial:{phase.id}",
                }
            ]
        )

    buttons.append(
        [
            {
                "text": "🗑 Excluir Fase",
                "callback_data": f"ai_confirm_delete:{phase.id}",
            }
        ]
    )
    buttons.append(
        [{"text": "🔙 Voltar", "callback_data": f"ai_list_phases:{phase.bot_id}"}]
    )

    return {"text": text, "keyboard": {"inline_keyboard": buttons}}


async def handle_set_initial_phase(user_id: int, phase_id: int) -> Dict[str, Any]:
    """Define fase como inicial"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    phase = await AIPhaseService.get_phase_by_id(phase_id)

    if not phase:
        return {"text": "❌ Fase não encontrada.", "keyboard": None}

    success = await AIPhaseService.set_initial_phase(phase.bot_id, phase_id)

    if success:
        return {
            "text": f"✅ Fase `{phase.phase_name}` definida como inicial!\n\nNovos usuários começarão nesta fase.",
            "keyboard": None,
        }
    else:
        return {"text": "❌ Erro ao definir fase inicial.", "keyboard": None}


async def handle_confirm_delete_phase(
    user_id: int, phase_id: int
) -> Dict[str, Any]:
    """Confirmação antes de deletar fase"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    phase = await AIPhaseService.get_phase_by_id(phase_id)

    if not phase:
        return {"text": "❌ Fase não encontrada.", "keyboard": None}

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Sim, excluir",
                    "callback_data": f"ai_delete_phase:{phase_id}",
                }
            ],
            [
                {
                    "text": "❌ Cancelar",
                    "callback_data": f"ai_view_phase:{phase_id}",
                }
            ],
        ]
    }

    return {
        "text": f"⚠️ **Confirmar Exclusão**\n\nTem certeza que deseja excluir a fase `{phase.phase_name}`?\n\n{'⚠️ Esta é a fase inicial! Novos usuários não terão fase inicial.' if phase.is_initial else 'Esta ação não pode ser desfeita.'}",
        "keyboard": keyboard,
    }


async def handle_delete_phase(user_id: int, phase_id: int) -> Dict[str, Any]:
    """Deleta fase"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    phase = await AIPhaseService.get_phase_by_id(phase_id)

    if not phase:
        return {"text": "❌ Fase não encontrada.", "keyboard": None}

    bot_id = phase.bot_id
    success = await AIPhaseService.delete_phase(phase_id)

    if success:
        # Redirecionar para lista de fases
        return await handle_list_phases(user_id, bot_id)
    else:
        return {"text": "❌ Erro ao excluir fase.", "keyboard": None}
