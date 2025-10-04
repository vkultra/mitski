"""
Handlers de configuração de blocos de ação
"""

from typing import Any, Dict

from core.config import settings
from database.repos import AIActionBlockRepository
from services.conversation_state import ConversationStateManager


async def handle_action_block_text_click(user_id: int, block_id: int) -> Dict[str, Any]:
    """Solicita texto/legenda do bloco"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await AIActionBlockRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_action_block_text",
        {"block_id": block_id, "action_id": block.action_id},
    )

    current_text = f"\n\nTexto atual: `{block.text[:100]}...`" if block.text else ""

    return {
        "text": f"💬 *Texto/Legenda do Bloco*{current_text}\n\n"
        f"Digite o texto da mensagem:\n\n"
        f"Se houver mídia, será usado como legenda. Se não, será uma mensagem de texto.",
        "keyboard": None,
    }


async def handle_action_block_text_input(
    user_id: int, block_id: int, action_id: int, text: str
) -> Dict[str, Any]:
    """Salva texto do bloco"""
    from .action_menu_handlers import handle_action_edit_menu

    await AIActionBlockRepository.update_block(block_id, text=text)
    ConversationStateManager.clear_state(user_id)

    return await handle_action_edit_menu(user_id, action_id)


async def handle_action_block_media_click(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    """Solicita mídia do bloco"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await AIActionBlockRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_action_block_media",
        {"block_id": block_id, "action_id": block.action_id},
    )

    current_media = (
        f"\n\nMídia atual: {block.media_type}" if block.media_file_id else ""
    )

    return {
        "text": f"📎 *Mídia do Bloco*{current_media}\n\n"
        f"Envie uma mídia (foto, vídeo, áudio, gif ou documento):\n\n"
        f"A mídia será reutilizada sempre que a ação for acionada.",
        "keyboard": None,
    }


async def handle_action_block_media_input(
    user_id: int,
    block_id: int,
    action_id: int,
    media_file_id: str,
    media_type: str,
) -> Dict[str, Any]:
    """Salva mídia do bloco"""
    from .action_menu_handlers import handle_action_edit_menu

    await AIActionBlockRepository.update_block(
        block_id, media_file_id=media_file_id, media_type=media_type
    )
    ConversationStateManager.clear_state(user_id)

    return await handle_action_edit_menu(user_id, action_id)


async def handle_action_block_effects_click(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    """Menu de efeitos do bloco"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await AIActionBlockRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "⏰ Delay", "callback_data": f"action_block_delay:{block_id}"},
                {
                    "text": "🗑️ Auto-deletar",
                    "callback_data": f"action_block_autodel:{block_id}",
                },
            ],
            [{"text": "🔙 Voltar", "callback_data": f"action_edit:{block.action_id}"}],
        ]
    }

    delay_text = (
        f"Delay: {block.delay_seconds}s" if block.delay_seconds else "Sem delay"
    )
    auto_del_text = (
        f"Auto-deletar: {block.auto_delete_seconds}s"
        if block.auto_delete_seconds
        else "Sem auto-exclusão"
    )

    return {
        "text": f"⏱️ *Efeitos do Bloco*\n\n{delay_text}\n{auto_del_text}\n\n"
        f"Escolha o efeito para configurar:",
        "keyboard": keyboard,
    }


async def handle_action_block_delay_click(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    """Solicita delay do bloco"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await AIActionBlockRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_action_block_delay",
        {"block_id": block_id, "action_id": block.action_id},
    )

    return {
        "text": f"⏰ *Delay do Bloco*\n\n"
        f"Digite o tempo de espera em segundos (0-300):\n\n"
        f"Exemplo: `5` para 5 segundos\n\n"
        f"Delay atual: {block.delay_seconds}s",
        "keyboard": None,
    }


async def handle_action_block_delay_input(
    user_id: int, block_id: int, action_id: int, delay_text: str
) -> Dict[str, Any]:
    """Salva delay do bloco"""
    try:
        delay = int(delay_text.strip())
        if delay < 0 or delay > 300:
            raise ValueError("Delay fora do intervalo")
    except ValueError:
        return {
            "text": "❌ Valor inválido. Digite um número entre 0 e 300:",
            "keyboard": None,
        }

    from .action_menu_handlers import handle_action_edit_menu

    await AIActionBlockRepository.update_block(block_id, delay_seconds=delay)
    ConversationStateManager.clear_state(user_id)

    result = await handle_action_edit_menu(user_id, action_id)
    result["text"] = f"✅ Delay configurado: {delay}s\n\n" + result["text"]

    return result


async def handle_action_block_autodel_click(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    """Solicita tempo de auto-delete do bloco"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await AIActionBlockRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_action_block_autodel",
        {"block_id": block_id, "action_id": block.action_id},
    )

    return {
        "text": f"🗑️ *Auto-deletar Bloco*\n\n"
        f"Digite o tempo em segundos para deletar a mensagem (0-300):\n\n"
        f"Exemplo: `10` para deletar após 10 segundos\n"
        f"Digite `0` para desabilitar\n\n"
        f"Auto-delete atual: {block.auto_delete_seconds}s",
        "keyboard": None,
    }


async def handle_action_block_autodel_input(
    user_id: int, block_id: int, action_id: int, autodel_text: str
) -> Dict[str, Any]:
    """Salva auto-delete do bloco"""
    try:
        autodel = int(autodel_text.strip())
        if autodel < 0 or autodel > 300:
            raise ValueError("Auto-delete fora do intervalo")
    except ValueError:
        return {
            "text": "❌ Valor inválido. Digite um número entre 0 e 300:",
            "keyboard": None,
        }

    from .action_menu_handlers import handle_action_edit_menu

    await AIActionBlockRepository.update_block(block_id, auto_delete_seconds=autodel)
    ConversationStateManager.clear_state(user_id)

    result = await handle_action_edit_menu(user_id, action_id)

    if autodel > 0:
        result["text"] = f"✅ Auto-delete configurado: {autodel}s\n\n" + result["text"]
    else:
        result["text"] = "✅ Auto-delete desabilitado\n\n" + result["text"]

    return result


async def handle_action_block_view(user_id: int, block_id: int) -> Dict[str, Any]:
    """Visualiza detalhes do bloco"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await AIActionBlockRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    # Montar informações do bloco
    info = f"📦 *Bloco #{block.order}*\n\n"

    if block.text:
        info += f"💬 Texto: `{block.text[:100]}{'...' if len(block.text) > 100 else ''}`\n\n"
    else:
        info += "💬 Texto: _vazio_\n\n"

    if block.media_file_id:
        info += f"📎 Mídia: {block.media_type}\n\n"
    else:
        info += "📎 Mídia: _nenhuma_\n\n"

    if block.delay_seconds:
        info += f"⏰ Delay: {block.delay_seconds}s\n"

    if block.auto_delete_seconds:
        info += f"🗑️ Auto-delete: {block.auto_delete_seconds}s\n"

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "💬 Texto", "callback_data": f"action_block_text:{block_id}"},
                {"text": "📎 Mídia", "callback_data": f"action_block_media:{block_id}"},
                {
                    "text": "⏱️ Efeitos",
                    "callback_data": f"action_block_effects:{block_id}",
                },
            ],
            [
                {
                    "text": "❌ Deletar",
                    "callback_data": f"action_block_delete:{block_id}",
                },
                {
                    "text": "🔙 Voltar",
                    "callback_data": f"action_edit:{block.action_id}",
                },
            ],
        ]
    }

    return {"text": info, "keyboard": keyboard}
