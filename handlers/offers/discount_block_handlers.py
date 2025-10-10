"""Handlers dos blocos configuráveis do menu de descontos."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from database.repos import OfferDiscountBlockRepository
from services.conversation_state import ConversationStateManager

from .discount_menu_handlers import handle_discount_menu
from .discount_utils import (
    PREFIX_BLOCK,
    decode_int_base36,
    encode_int_base36,
    encode_token,
    escape_markdown,
    validate_token,
)


def _invalid_callback_response() -> Dict[str, Any]:
    return {
        "callback_alert": {
            "text": "⚠️ Ação inválida ou expirada.",
            "show_alert": True,
        }
    }


BLOCK_NOT_FOUND_RESPONSE: Dict[str, Any] = {
    "text": "❌ Bloco não encontrado.",
    "keyboard": None,
}


async def _get_block(block_id: int):
    return await OfferDiscountBlockRepository.get_block_by_id(block_id)


async def _resolve_block_from_token(
    user_id: int, token: str, expected_action: str
) -> Tuple[Optional[Any], Optional[int], Optional[Any]]:
    data = await validate_token(user_id, token, expected_action)
    if not data:
        return _invalid_callback_response(), None, None

    block_id = decode_int_base36(data.extra or "0")
    block = await _get_block(block_id)
    if not block:
        return BLOCK_NOT_FOUND_RESPONSE, None, None

    return data, block_id, block


async def handle_discount_block_view(user_id: int, token: str) -> Dict[str, Any]:
    resolved, block_id, block = await _resolve_block_from_token(user_id, token, "v")
    if isinstance(resolved, dict) and block is None:
        return resolved
    data = resolved  # type: ignore[assignment]

    text_preview = (
        (block.text[:200] + "…") if block.text and len(block.text) > 200 else block.text
    )
    display_text = escape_markdown(text_preview) if text_preview else "_(vazio)_"
    media_info = escape_markdown(block.media_type) if block.media_type else "Nenhuma"

    return {
        "text": (
            f"📄 *Bloco #{block.order}*\n\n"
            f"Texto: {display_text}\n"
            f"Mídia: {media_info}\n"
            f"Delay: {block.delay_seconds}s | Auto-delete: {block.auto_delete_seconds}s"
        ),
        "keyboard": {
            "inline_keyboard": [
                [
                    {
                        "text": "🔙 Voltar",
                        "callback_data": f"disc_m:{encode_token('m', user_id, data.offer_id)}",
                    }
                ]
            ]
        },
    }


async def handle_discount_block_text_click(user_id: int, token: str) -> Dict[str, Any]:
    resolved, block_id, block = await _resolve_block_from_token(user_id, token, "t")
    if isinstance(resolved, dict) and block is None:
        return resolved
    data = resolved  # type: ignore[assignment]

    ConversationStateManager.set_state(
        user_id,
        "awaiting_disc_block_text",
        {"offer_id": data.offer_id, "block_id": block_id},
    )

    preview = (
        (block.text[:200] + "…") if block.text and len(block.text) > 200 else block.text
    )
    preview_display = escape_markdown(preview)

    base_text = (
        "💬 *Texto do bloco*\n\n"
        "Digite a mensagem ou legenda para este bloco.\n"
        "Use `{pix}` para inserir a chave PIX Copia e Cola automaticamente."
    )
    if preview:
        base_text += f"\n\nAtual: {preview_display}"

    return {
        "text": base_text,
        "keyboard": None,
    }


async def handle_discount_block_media_click(user_id: int, token: str) -> Dict[str, Any]:
    resolved, block_id, block = await _resolve_block_from_token(user_id, token, "m")
    if isinstance(resolved, dict) and block is None:
        return resolved
    data = resolved  # type: ignore[assignment]

    ConversationStateManager.set_state(
        user_id,
        "awaiting_disc_block_media",
        {"offer_id": data.offer_id, "block_id": block_id},
    )

    file_id_label = r"file\_id"
    return {
        "text": (
            "📎 *Mídia do bloco*\n\n"
            "Envie foto, vídeo, áudio, GIF ou documento. "
            f"O {file_id_label} será reutilizado."
        ),
        "keyboard": None,
    }


async def handle_discount_block_effects_click(
    user_id: int, token: str
) -> Dict[str, Any]:
    resolved, block_id, block = await _resolve_block_from_token(user_id, token, "e")
    if isinstance(resolved, dict) and block is None:
        return resolved
    data = resolved  # type: ignore[assignment]

    delay_token = encode_token("l", user_id, data.offer_id, encode_int_base36(block_id))
    auto_token = encode_token("o", user_id, data.offer_id, encode_int_base36(block_id))
    back_token = encode_token("m", user_id, data.offer_id)

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "⏰ Delay", "callback_data": f"{PREFIX_BLOCK}{delay_token}"},
                {
                    "text": "🗑️ Auto-deletar",
                    "callback_data": f"{PREFIX_BLOCK}{auto_token}",
                },
            ],
            [
                {"text": "🔙 Voltar", "callback_data": f"disc_m:{back_token}"},
            ],
        ]
    }

    return {
        "text": (
            "⏱️ *Efeitos do bloco*\n\n"
            f"Delay atual: {block.delay_seconds}s\n"
            f"Auto-delete: {block.auto_delete_seconds}s"
        ),
        "keyboard": keyboard,
    }


async def handle_discount_block_delay_click(user_id: int, token: str) -> Dict[str, Any]:
    resolved, block_id, block = await _resolve_block_from_token(user_id, token, "l")
    if isinstance(resolved, dict) and block is None:
        return resolved
    data = resolved  # type: ignore[assignment]

    ConversationStateManager.set_state(
        user_id,
        "awaiting_disc_block_delay",
        {"offer_id": data.offer_id, "block_id": block_id},
    )

    return {
        "text": f"⏰ *Delay*\n\nInforme o tempo em segundos (0-300). Atual: {block.delay_seconds}s",
        "keyboard": None,
    }


async def handle_discount_block_autodel_click(
    user_id: int, token: str
) -> Dict[str, Any]:
    resolved, block_id, block = await _resolve_block_from_token(user_id, token, "o")
    if isinstance(resolved, dict) and block is None:
        return resolved
    data = resolved  # type: ignore[assignment]

    ConversationStateManager.set_state(
        user_id,
        "awaiting_disc_block_autodel",
        {"offer_id": data.offer_id, "block_id": block_id},
    )

    return {
        "text": f"🗑️ *Auto-delete*\n\nInforme o tempo em segundos (0-3600). Atual: {block.auto_delete_seconds}s",
        "keyboard": None,
    }


async def handle_discount_block_delete(user_id: int, token: str) -> Dict[str, Any]:
    resolved, block_id, _ = await _resolve_block_from_token(user_id, token, "d")
    if isinstance(resolved, dict) and block_id is None:
        return resolved
    data = resolved  # type: ignore[assignment]

    await OfferDiscountBlockRepository.delete_block(block_id)

    return await handle_discount_menu(user_id, data.offer_id)
