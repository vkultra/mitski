"""Handlers responsáveis por persistir inputs dos blocos de descontos."""

from __future__ import annotations

from typing import Any, Dict

from database.repos import OfferDiscountBlockRepository
from services.conversation_state import ConversationStateManager

from .discount_menu_handlers import handle_discount_menu
from .discount_utils import encode_int_base36, encode_token


async def handle_discount_block_text_input(
    user_id: int,
    offer_id: int,
    block_id: int,
    text: str,
) -> Dict[str, Any]:
    await OfferDiscountBlockRepository.update_block(block_id, text=text.strip())
    ConversationStateManager.clear_state(user_id)
    return await handle_discount_menu(user_id, offer_id)


async def handle_discount_block_media_input(
    user_id: int,
    offer_id: int,
    block_id: int,
    media_file_id: str,
    media_type: str,
) -> Dict[str, Any]:
    await OfferDiscountBlockRepository.update_block(
        block_id,
        media_file_id=media_file_id,
        media_type=media_type,
    )
    ConversationStateManager.clear_state(user_id)
    return await handle_discount_menu(user_id, offer_id)


async def handle_discount_block_delay_input(
    user_id: int,
    offer_id: int,
    block_id: int,
    value: str,
) -> Dict[str, Any]:
    try:
        delay_seconds = int(value)
        if delay_seconds < 0 or delay_seconds > 300:
            raise ValueError
    except ValueError:
        return {
            "text": "❌ Valor inválido. Informe um número entre 0 e 300:",
            "keyboard": None,
        }

    await OfferDiscountBlockRepository.update_block(
        block_id, delay_seconds=delay_seconds
    )
    ConversationStateManager.clear_state(user_id)

    block_token = encode_token("e", user_id, offer_id, encode_int_base36(block_id))
    from .discount_block_handlers import handle_discount_block_effects_click

    return await handle_discount_block_effects_click(user_id, block_token)


async def handle_discount_block_autodel_input(
    user_id: int,
    offer_id: int,
    block_id: int,
    value: str,
) -> Dict[str, Any]:
    try:
        autodel_seconds = int(value)
        if autodel_seconds < 0 or autodel_seconds > 3600:
            raise ValueError
    except ValueError:
        return {
            "text": "❌ Valor inválido. Informe um número entre 0 e 3600:",
            "keyboard": None,
        }

    await OfferDiscountBlockRepository.update_block(
        block_id, auto_delete_seconds=autodel_seconds
    )
    ConversationStateManager.clear_state(user_id)

    block_token = encode_token("e", user_id, offer_id, encode_int_base36(block_id))
    from .discount_block_handlers import handle_discount_block_effects_click

    return await handle_discount_block_effects_click(user_id, block_token)


__all__ = [
    "handle_discount_block_text_input",
    "handle_discount_block_media_input",
    "handle_discount_block_delay_input",
    "handle_discount_block_autodel_input",
]
