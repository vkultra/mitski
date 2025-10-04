"""
Handlers de configuração de blocos de verificação manual
"""

from typing import Any, Dict

from core.config import settings
from database.repos import OfferManualVerificationBlockRepository
from services.conversation_state import ConversationStateManager


async def handle_manual_verification_block_text_click(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    """Solicita texto/legenda do bloco de verificação manual"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await OfferManualVerificationBlockRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_manver_block_text",
        {"block_id": block_id, "offer_id": block.offer_id},
    )

    current_text = f"\n\nTexto atual: `{block.text[:100]}...`" if block.text else ""

    return {
        "text": f"💬 *Texto/Legenda do Bloco (Verificação Manual)*{current_text}\n\n"
        f"Digite o texto da mensagem que será enviada quando o pagamento não for encontrado:\n\n"
        f"Se houver mídia, será usado como legenda. Se não, será uma mensagem de texto.",
        "keyboard": None,
    }


async def handle_manual_verification_block_text_input(
    user_id: int, block_id: int, offer_id: int, text: str
) -> Dict[str, Any]:
    """Salva texto do bloco de verificação manual"""
    from .manual_verification_menu_handlers import handle_manual_verification_menu

    await OfferManualVerificationBlockRepository.update_block(block_id, text=text)
    ConversationStateManager.clear_state(user_id)

    return await handle_manual_verification_menu(user_id, offer_id)


async def handle_manual_verification_block_media_click(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    """Solicita mídia do bloco de verificação manual"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await OfferManualVerificationBlockRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_manver_block_media",
        {"block_id": block_id, "offer_id": block.offer_id},
    )

    current_media = (
        f"\n\nMídia atual: {block.media_type}" if block.media_file_id else ""
    )

    return {
        "text": f"📎 *Mídia do Bloco (Verificação Manual)*{current_media}\n\n"
        f"Envie uma mídia (foto, vídeo, áudio, gif ou documento):\n\n"
        f"Esta mídia será enviada quando o pagamento não for encontrado.",
        "keyboard": None,
    }


async def handle_manual_verification_block_media_input(
    user_id: int,
    block_id: int,
    offer_id: int,
    media_file_id: str,
    media_type: str,
) -> Dict[str, Any]:
    """Salva mídia do bloco de verificação manual"""
    from .manual_verification_menu_handlers import handle_manual_verification_menu

    await OfferManualVerificationBlockRepository.update_block(
        block_id, media_file_id=media_file_id, media_type=media_type
    )
    ConversationStateManager.clear_state(user_id)

    return await handle_manual_verification_menu(user_id, offer_id)


async def handle_manual_verification_block_effects_click(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    """Menu de efeitos do bloco de verificação manual"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await OfferManualVerificationBlockRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "⏰ Delay", "callback_data": f"manver_block_delay:{block_id}"},
                {
                    "text": "🗑️ Auto-deletar",
                    "callback_data": f"manver_block_autodel:{block_id}",
                },
            ],
            [{"text": "🔙 Voltar", "callback_data": f"manver_menu:{block.offer_id}"}],
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
        "text": f"⏱️ *Efeitos do Bloco (Verificação Manual)*\n\n{delay_text}\n{auto_del_text}\n\n"
        f"Escolha o efeito para configurar:",
        "keyboard": keyboard,
    }


async def handle_manual_verification_block_delay_click(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    """Solicita delay do bloco de verificação manual"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await OfferManualVerificationBlockRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_manver_block_delay",
        {"block_id": block_id, "offer_id": block.offer_id},
    )

    return {
        "text": f"⏰ *Delay do Bloco (Verificação Manual)*\n\n"
        f"Digite o tempo de espera em segundos (0-300):\n\n"
        f"Exemplo: `5` para 5 segundos\n\nDelay atual: {block.delay_seconds}s",
        "keyboard": None,
    }


async def handle_manual_verification_block_delay_input(
    user_id: int, block_id: int, offer_id: int, delay: str
) -> Dict[str, Any]:
    """Salva delay do bloco de verificação manual"""
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

    await OfferManualVerificationBlockRepository.update_block(
        block_id, delay_seconds=delay_seconds
    )
    ConversationStateManager.clear_state(user_id)

    return await handle_manual_verification_block_effects_click(user_id, block_id)


async def handle_manual_verification_block_autodel_click(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    """Solicita tempo de auto-exclusão do bloco de verificação manual"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await OfferManualVerificationBlockRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_manver_block_autodel",
        {"block_id": block_id, "offer_id": block.offer_id},
    )

    return {
        "text": f"🗑️ *Auto-exclusão do Bloco (Verificação Manual)*\n\n"
        f"Digite o tempo em segundos para auto-deletar (0-3600):\n\n"
        f"Exemplo: `30` para deletar após 30 segundos\n`0` para não deletar\n\n"
        f"Tempo atual: {block.auto_delete_seconds}s",
        "keyboard": None,
    }


async def handle_manual_verification_block_autodel_input(
    user_id: int, block_id: int, offer_id: int, autodel: str
) -> Dict[str, Any]:
    """Salva auto-exclusão do bloco de verificação manual"""
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

    await OfferManualVerificationBlockRepository.update_block(
        block_id, auto_delete_seconds=auto_delete_seconds
    )
    ConversationStateManager.clear_state(user_id)

    return await handle_manual_verification_block_effects_click(user_id, block_id)
