"""
Handlers de configuração de blocos do pitch
"""

from typing import Any, Dict

from core.config import settings
from database.repos import OfferPitchRepository
from services.conversation_state import ConversationStateManager


async def handle_block_text_click(user_id: int, block_id: int) -> Dict[str, Any]:
    """Solicita texto/legenda do bloco"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await OfferPitchRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_block_text",
        {"block_id": block_id, "offer_id": block.offer_id},
    )

    current_text = f"\n\nTexto atual: `{block.text[:100]}...`" if block.text else ""

    return {
        "text": f"💬 *Texto/Legenda do Bloco*{current_text}\n\nDigite o texto da mensagem:\n\n"
        f"Se houver mídia, será usado como legenda. Se não, será uma mensagem de texto.",
        "keyboard": None,
    }


async def handle_block_text_input(
    user_id: int, block_id: int, offer_id: int, text: str
) -> Dict[str, Any]:
    """Salva texto do bloco"""
    # Import aqui para evitar circular import
    from .pitch_menu_handlers import handle_offer_pitch_menu

    await OfferPitchRepository.update_block(block_id, text=text)
    ConversationStateManager.clear_state(user_id)

    return await handle_offer_pitch_menu(user_id, offer_id)


async def handle_block_media_click(user_id: int, block_id: int) -> Dict[str, Any]:
    """Solicita mídia do bloco"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await OfferPitchRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_block_media",
        {"block_id": block_id, "offer_id": block.offer_id},
    )

    current_media = (
        f"\n\nMídia atual: {block.media_type}" if block.media_file_id else ""
    )

    return {
        "text": f"📎 *Mídia do Bloco*{current_media}\n\nEnvie uma mídia (foto, vídeo, áudio, gif ou documento):\n\n"
        f"A mídia será reutilizada sempre que o pitch for enviado.",
        "keyboard": None,
    }


async def handle_block_media_input(
    user_id: int,
    block_id: int,
    offer_id: int,
    media_file_id: str,
    media_type: str,
) -> Dict[str, Any]:
    """Salva mídia do bloco"""
    # Import aqui para evitar circular import
    from .pitch_menu_handlers import handle_offer_pitch_menu

    await OfferPitchRepository.update_block(
        block_id, media_file_id=media_file_id, media_type=media_type
    )
    ConversationStateManager.clear_state(user_id)

    return await handle_offer_pitch_menu(user_id, offer_id)


async def handle_block_effects_click(user_id: int, block_id: int) -> Dict[str, Any]:
    """Menu de efeitos do bloco"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await OfferPitchRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "⏰ Delay", "callback_data": f"pitch_delay:{block_id}"},
                {
                    "text": "🗑️ Auto-deletar",
                    "callback_data": f"pitch_autodel:{block_id}",
                },
            ],
            [{"text": "🔙 Voltar", "callback_data": f"offer_pitch:{block.offer_id}"}],
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
        "text": f"⏱️ *Efeitos do Bloco*\n\n{delay_text}\n{auto_del_text}\n\nEscolha o efeito para configurar:",
        "keyboard": keyboard,
    }


async def handle_block_delay_click(user_id: int, block_id: int) -> Dict[str, Any]:
    """Solicita delay do bloco"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await OfferPitchRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_block_delay",
        {"block_id": block_id, "offer_id": block.offer_id},
    )

    return {
        "text": f"⏰ *Delay do Bloco*\n\nDigite o tempo de espera em segundos (0-300):\n\n"
        f"Exemplo: `5` para 5 segundos\n\nDelay atual: {block.delay_seconds}s",
        "keyboard": None,
    }


async def handle_block_delay_input(
    user_id: int, block_id: int, offer_id: int, delay: str
) -> Dict[str, Any]:
    """Salva delay do bloco"""
    try:
        delay_seconds = int(delay)
        if delay_seconds < 0 or delay_seconds > 300:
            return {
                "text": "❌ Delay deve estar entre 0 e 300 segundos.\n\nTente novamente:",
                "keyboard": None,
            }
    except ValueError:
        return {
            "text": "❌ Digite apenas números.\n\nTente novamente:",
            "keyboard": None,
        }

    await OfferPitchRepository.update_block(block_id, delay_seconds=delay_seconds)
    ConversationStateManager.clear_state(user_id)

    return await handle_block_effects_click(user_id, block_id)


async def handle_block_autodel_click(user_id: int, block_id: int) -> Dict[str, Any]:
    """Solicita tempo de auto-exclusão"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await OfferPitchRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_block_autodel",
        {"block_id": block_id, "offer_id": block.offer_id},
    )

    return {
        "text": f"🗑️ *Auto-exclusão do Bloco*\n\nDigite o tempo em segundos para auto-deletar (0-3600):\n\n"
        f"Exemplo: `30` para deletar após 30 segundos\n`0` para não deletar\n\n"
        f"Tempo atual: {block.auto_delete_seconds}s",
        "keyboard": None,
    }


async def handle_block_autodel_input(
    user_id: int, block_id: int, offer_id: int, autodel: str
) -> Dict[str, Any]:
    """Salva auto-exclusão do bloco"""
    try:
        auto_delete_seconds = int(autodel)
        if auto_delete_seconds < 0 or auto_delete_seconds > 3600:
            return {
                "text": "❌ Tempo deve estar entre 0 e 3600 segundos.\n\nTente novamente:",
                "keyboard": None,
            }
    except ValueError:
        return {
            "text": "❌ Digite apenas números.\n\nTente novamente:",
            "keyboard": None,
        }

    await OfferPitchRepository.update_block(
        block_id, auto_delete_seconds=auto_delete_seconds
    )
    ConversationStateManager.clear_state(user_id)

    return await handle_block_effects_click(user_id, block_id)
