"""
Handlers de CRUD (delete, preview) para ações
"""

from typing import Any, Dict

from core.config import settings
from database.repos import AIActionBlockRepository, AIActionRepository


async def handle_delete_action_block(user_id: int, block_id: int) -> Dict[str, Any]:
    """Deleta bloco da ação"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await AIActionBlockRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    action_id = block.action_id
    await AIActionBlockRepository.delete_block(block_id)

    from .action_menu_handlers import handle_action_edit_menu

    return await handle_action_edit_menu(user_id, action_id)


async def handle_delete_action(user_id: int, action_id: int) -> Dict[str, Any]:
    """Confirma e deleta ação"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    action = await AIActionRepository.get_action_by_id(action_id)
    if not action:
        return {"text": "❌ Ação não encontrada.", "keyboard": None}

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Sim, deletar",
                    "callback_data": f"action_delete_confirm:{action_id}",
                },
                {"text": "❌ Cancelar", "callback_data": f"action_edit:{action_id}"},
            ]
        ]
    }

    return {
        "text": f"⚠️ *Confirmar Exclusão*\n\n"
        f"Deseja realmente deletar a ação '{action.action_name}'?\n\n"
        f"Esta ação não pode ser desfeita!",
        "keyboard": keyboard,
    }


async def handle_delete_action_confirm(user_id: int, action_id: int) -> Dict[str, Any]:
    """Executa deleção da ação"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    action = await AIActionRepository.get_action_by_id(action_id)
    if not action:
        return {"text": "❌ Ação não encontrada.", "keyboard": None}

    bot_id = action.bot_id
    action_name = action.action_name

    # Deletar ação e seus blocos (cascade)
    await AIActionRepository.delete_action(action_id)

    # Voltar ao menu de ações
    from .action_menu_handlers import handle_action_menu_click

    result = await handle_action_menu_click(user_id, bot_id)
    result["text"] = f"✅ Ação '{action_name}' deletada!\n\n" + result["text"]

    return result


async def handle_preview_action(user_id: int, action_id: int) -> Dict[str, Any]:
    """Pré-visualiza a ação enviando os blocos"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    action = await AIActionRepository.get_action_by_id(action_id)
    blocks = await AIActionBlockRepository.get_blocks_by_action(action_id)

    if not blocks:
        return {
            "text": "❌ Nenhum bloco criado ainda.\n\nCrie pelo menos um bloco para visualizar.",
            "keyboard": None,
        }

    # Importar ActionSenderService
    from services.ai.actions import ActionSenderService

    # Criar instância do serviço com o token do bot gerenciador
    action_sender = ActionSenderService(settings.MANAGER_BOT_TOKEN)

    # Enviar os blocos da ação
    await action_sender.send_action_blocks(
        action_id=action_id, chat_id=user_id, preview_mode=True
    )

    # Enviar nova mensagem com o menu
    from workers.api_clients import TelegramAPI

    api = TelegramAPI()
    from .action_menu_handlers import handle_action_edit_menu

    menu_data = await handle_action_edit_menu(user_id, action_id)

    await api.send_message(
        token=settings.MANAGER_BOT_TOKEN,
        chat_id=user_id,
        text=menu_data["text"],
        parse_mode="Markdown",
        reply_markup=menu_data["keyboard"],
    )

    return {
        "text": "✅ Pré-visualização enviada! Veja os blocos abaixo.",
        "keyboard": None,
    }
