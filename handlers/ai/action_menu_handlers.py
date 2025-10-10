"""
Handlers para menus de ações da IA
"""

from typing import Any, Dict

from core.config import settings
from database.repos import AIActionBlockRepository, AIActionRepository
from services.ai.actions import ActionService
from services.conversation_state import ConversationStateManager

from .audio_menu_handlers import build_audio_buttons


async def handle_action_menu_click(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Menu principal de ações"""
    audio_callbacks = build_audio_buttons(user_id, bot_id)
    audio_row = [
        {"text": "🎧 Áudios", "callback_data": audio_callbacks["info"]},
        {"text": "⚙️ Configurar", "callback_data": audio_callbacks["menu"]},
    ]

    if user_id not in settings.allowed_admin_ids_list:
        keyboard = {
            "inline_keyboard": [
                audio_row,
                [{"text": "🔙 Voltar", "callback_data": f"ai_select_bot:{bot_id}"}],
            ]
        }
        return {
            "text": (
                "🎧 *Áudios*\n\n"
                "Use os botões abaixo para configurar a resposta padrão ou o reconhecimento via Whisper."
            ),
            "keyboard": keyboard,
        }

    # Buscar ações do bot
    actions = await AIActionRepository.get_actions_by_bot(bot_id)

    # Montar botões das ações (3 por linha)
    action_buttons = []
    row = []
    for i, action in enumerate(actions):
        # Indicador de rastreamento
        track_icon = "🧭" if action.track_usage else ""
        button_text = f"{action.action_name} {track_icon}"

        row.append({"text": button_text, "callback_data": f"action_edit:{action.id}"})

        # Se completou 3 na linha ou é o último
        if (i + 1) % 3 == 0 or i == len(actions) - 1:
            action_buttons.append(row)
            row = []

    # Linha inicial com atalhos de /start
    keyboard_buttons = [
        [
            {"text": "🚀 /start", "callback_data": f"start_template_info:{bot_id}"},
            {"text": "⚙️ Configurar", "callback_data": f"start_template_menu:{bot_id}"},
        ],
        audio_row,
    ]

    # Botão de adicionar sempre abaixo dos atalhos
    keyboard_buttons.append(
        [{"text": "➕ Adicionar Ação", "callback_data": f"action_add:{bot_id}"}]
    )

    # Adicionar botões das ações
    keyboard_buttons.extend(action_buttons)

    # Botão voltar
    keyboard_buttons.append(
        [{"text": "🔙 Voltar", "callback_data": f"ai_select_bot:{bot_id}"}]
    )

    keyboard = {"inline_keyboard": keyboard_buttons}

    return {
        "text": f"🎬 *Ações Configuradas*\n\n"
        f"Total: {len(actions)} ações\n"
        f"🧭 = Rastreamento ativo\n\n"
        f"Clique em uma ação para editar ou adicione uma nova.",
        "keyboard": keyboard,
    }


async def handle_add_action_click(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Inicia criação de nova ação"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id, "awaiting_action_name", {"bot_id": bot_id}
    )

    return {
        "text": "➕ *Criar Nova Ação*\n\n"
        "Digite o nome da ação:\n\n"
        "⚠️ O nome será o gatilho que a IA usará para acionar a ação.\n\n"
        "Exemplo: `promocao`, `contato`, `horarios`",
        "keyboard": None,
    }


async def handle_action_name_input(
    user_id: int, bot_id: int, action_name: str
) -> Dict[str, Any]:
    """Processa nome da ação e cria"""
    action_name = action_name.strip()

    # Validar nome
    validation = await ActionService.validate_action_creation(bot_id, action_name)

    if not validation["valid"]:
        return {
            "text": f"❌ {validation['error']}\n\nTente novamente:",
            "keyboard": None,
        }

    # Criar ação
    action = await AIActionRepository.create_action(
        bot_id=bot_id,
        action_name=action_name,
        track_usage=False,  # Desabilitado por padrão
        is_active=True,
    )

    ConversationStateManager.clear_state(user_id)

    # Ir para menu de edição da ação
    return await handle_action_edit_menu(user_id, action.id)


async def handle_action_edit_menu(user_id: int, action_id: int) -> Dict[str, Any]:
    """Menu de edição de ação"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    action = await AIActionRepository.get_action_by_id(action_id)
    if not action:
        return {"text": "❌ Ação não encontrada.", "keyboard": None}

    # Buscar blocos existentes
    blocks = await AIActionBlockRepository.get_blocks_by_action(action_id)

    # Montar botões dos blocos
    block_buttons = []
    for i, block in enumerate(blocks, 1):
        # Linha com 5 botões para cada bloco
        buttons_row = [
            {"text": f"{i}️⃣", "callback_data": f"action_block_view:{block.id}"},
            {"text": "Efeitos", "callback_data": f"action_block_effects:{block.id}"},
            {"text": "Mídia", "callback_data": f"action_block_media:{block.id}"},
            {"text": "Texto/Legenda", "callback_data": f"action_block_text:{block.id}"},
            {"text": "❌", "callback_data": f"action_block_delete:{block.id}"},
        ]
        block_buttons.append(buttons_row)

    # Toggle de rastreamento
    track_toggle = "✅" if action.track_usage else "❌"
    track_text = f"Rastrear Uso: {track_toggle}"

    # Botões principais
    keyboard_buttons = block_buttons + [
        [{"text": "➕ Criar Bloco", "callback_data": f"action_block_add:{action_id}"}],
        [{"text": "👀 Pré-visualizar", "callback_data": f"action_preview:{action_id}"}],
        [{"text": track_text, "callback_data": f"action_toggle_track:{action_id}"}],
    ]

    # Botões finais (Voltar/Salvar/Deletar)
    # Se é uma ação nova (sem blocos ainda), mostrar Salvar ao invés de Deletar
    if len(blocks) == 0:
        keyboard_buttons.append(
            [
                {"text": "🔙 Voltar", "callback_data": f"action_menu:{action.bot_id}"},
                {"text": "💾 Salvar", "callback_data": f"action_menu:{action.bot_id}"},
            ]
        )
    else:
        # Ação existente - mostrar Deletar
        keyboard_buttons.append(
            [
                {"text": "🔙 Voltar", "callback_data": f"action_menu:{action.bot_id}"},
                {
                    "text": "🗑️ Deletar Ação",
                    "callback_data": f"action_delete:{action_id}",
                },
            ]
        )

    keyboard = {"inline_keyboard": keyboard_buttons}

    track_info = (
        "\n🧭 Rastreamento: ATIVO - Status será enviado no prompt da IA"
        if action.track_usage
        else "\n🧭 Rastreamento: INATIVO"
    )

    return {
        "text": f"⚡ *Ação: {action.action_name}*{track_info}\n\n"
        f"Cada linha representa uma mensagem que será enviada quando a IA mencionar '{action.action_name}'.\n\n"
        f"Total de blocos: {len(blocks)}",
        "keyboard": keyboard,
    }


async def handle_toggle_track(user_id: int, action_id: int) -> Dict[str, Any]:
    """Alterna rastreamento de uso da ação"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    action = await AIActionRepository.get_action_by_id(action_id)
    if not action:
        return {"text": "❌ Ação não encontrada.", "keyboard": None}

    # Alternar status
    new_track = not action.track_usage
    await AIActionRepository.update_action(action_id, track_usage=new_track)

    status = "ATIVADO" if new_track else "DESATIVADO"
    info = (
        "\n\n✅ Agora o status dessa ação será incluído no prompt da IA como INACTIVE/ACTIVATED."
        if new_track
        else "\n\n❌ O status dessa ação NÃO será enviado para a IA."
    )

    # Voltar ao menu
    result = await handle_action_edit_menu(user_id, action_id)

    # Adicionar mensagem de confirmação
    result["text"] = f"🧭 Rastreamento {status}!{info}\n\n" + result["text"]

    return result


async def handle_create_action_block(user_id: int, action_id: int) -> Dict[str, Any]:
    """Adiciona novo bloco à ação"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    # Calcular próxima ordem
    blocks = await AIActionBlockRepository.get_blocks_by_action(action_id)
    next_order = len(blocks) + 1

    # Criar bloco vazio
    block = await AIActionBlockRepository.create_block(
        action_id=action_id,
        order=next_order,
        text="",
        delay_seconds=0,
        auto_delete_seconds=0,
    )

    # Voltar ao menu da ação
    return await handle_action_edit_menu(user_id, action_id)
