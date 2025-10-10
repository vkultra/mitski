"""Handlers de menu para configuração de descontos dinâmicos."""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.config import settings
from core.telemetry import logger
from database.repos import OfferDiscountBlockRepository, OfferRepository
from services.conversation_state import ConversationStateManager
from services.offers.discount_sender import DiscountSender
from services.offers.discount_service import _MAX_VALUE_CENTS, _MIN_VALUE_CENTS
from workers.api_clients import TelegramAPI

from .discount_utils import (
    PREFIX_ADD,
    PREFIX_BLOCK,
    PREFIX_PREVIEW,
    PREFIX_TRIGGER,
    build_menu_token,
    encode_int_base36,
    encode_token,
    escape_markdown,
    get_token_action,
    validate_token,
)


async def handle_discount_menu(user_id: int, offer_id: int) -> Dict[str, Any]:
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    offer = await OfferRepository.get_offer_by_id(offer_id)
    if not offer:
        return {"text": "❌ Oferta não encontrada.", "keyboard": None}

    blocks = await OfferDiscountBlockRepository.get_blocks_by_offer(offer_id)
    block_rows = []
    for index, block in enumerate(blocks, start=1):
        encoded_id = encode_int_base36(block.id)
        block_rows.append(
            [
                {
                    "text": f"{index}️⃣",
                    "callback_data": f"{PREFIX_BLOCK}{encode_token('v', user_id, offer_id, encoded_id)}",
                },
                {
                    "text": "Efeitos",
                    "callback_data": f"{PREFIX_BLOCK}{encode_token('e', user_id, offer_id, encoded_id)}",
                },
                {
                    "text": "Mídia",
                    "callback_data": f"{PREFIX_BLOCK}{encode_token('m', user_id, offer_id, encoded_id)}",
                },
                {
                    "text": "Texto",
                    "callback_data": f"{PREFIX_BLOCK}{encode_token('t', user_id, offer_id, encoded_id)}",
                },
                {
                    "text": "❌",
                    "callback_data": f"{PREFIX_BLOCK}{encode_token('d', user_id, offer_id, encoded_id)}",
                },
            ]
        )

    trigger_button_label = (
        f"🔑 {offer.discount_trigger}"
        if offer.discount_trigger
        else "🔑 Definir termo de desconto"
    )
    trigger_button = encode_token("t", user_id, offer_id)
    add_button = encode_token("a", user_id, offer_id)
    preview_button = encode_token("p", user_id, offer_id)

    keyboard_rows = [
        [
            {
                "text": trigger_button_label,
                "callback_data": f"{PREFIX_TRIGGER}{trigger_button}",
            }
        ],
        *block_rows,
        [
            {
                "text": "➕ Criar Bloco",
                "callback_data": f"{PREFIX_ADD}{add_button}",
            }
        ],
        [
            {
                "text": "👀 Pré-visualizar",
                "callback_data": f"{PREFIX_PREVIEW}{preview_button}",
            }
        ],
        [
            {"text": "🔙 Voltar", "callback_data": f"offer_edit:{offer_id}"},
            {"text": "💾 Salvar", "callback_data": f"offer_edit:{offer_id}"},
        ],
    ]

    name_display = escape_markdown(offer.name)
    value_display = escape_markdown(offer.value) if offer.value else ""
    trigger_display = (
        escape_markdown(offer.discount_trigger)
        if offer.discount_trigger
        else "Não definido"
    )
    min_value = _MIN_VALUE_CENTS / 100
    max_value = _MAX_VALUE_CENTS / 100

    description = (
        "🏷️ *Descontos*: personalize respostas para negociações.\n\n"
        "Assim que a IA enviar `{termo}{valor}`, o sistema gera um PIX com o valor recebido, "
        "substitui a mensagem da IA por estes blocos e segue com as mesmas regras de entrega.\n\n"
        "Use `{pix}` dentro dos blocos para inserir automaticamente a chave PIX Copia e Cola.\n\n"
        f"Intervalo permitido: R$ {min_value:.2f} — R$ {max_value:.2f}."
    )

    summary = (
        f"🏷️ *Descontos: {name_display}{f' ({value_display})' if value_display else ''}*\n\n"
        f"Termo configurado: {trigger_display}\n"
        f"Total de blocos: {len(blocks)}"
    )

    return {
        "text": f"{summary}\n\n{description}",
        "keyboard": {"inline_keyboard": keyboard_rows},
    }


async def handle_discount_menu_from_token(user_id: int, token: str) -> Dict[str, Any]:
    data = await validate_token(user_id, token, "m")
    if not data:
        return {
            "callback_alert": {
                "text": "⚠️ Ação inválida ou expirada.",
                "show_alert": True,
            }
        }
    return await handle_discount_menu(user_id, data.offer_id)


def build_discount_menu_token(user_id: int, offer_id: int) -> str:
    return build_menu_token(user_id, offer_id)


def get_discount_token_action(token: str) -> Optional[str]:
    return get_token_action(token)


async def handle_discount_trigger_prompt(user_id: int, token: str) -> Dict[str, Any]:
    data = await validate_token(user_id, token, "t")
    if not data:
        return {
            "callback_alert": {
                "text": "⚠️ Ação inválida ou expirada.",
                "show_alert": True,
            }
        }

    ConversationStateManager.set_state(
        user_id,
        "awaiting_disc_trigger",
        {"offer_id": data.offer_id},
    )

    return {
        "text": (
            "🔑 *Termo de desconto*\n\n"
            "Digite o termo que a IA deve enviar antes do valor negociado.\n"
            "Exemplos: `fechoupack`, `promofinal`.\n\n"
            "O sistema reconhecerá mensagens como `fechoupack15` ou `PromoFinal 19,90`."
        ),
        "keyboard": None,
    }


async def handle_discount_trigger_input(
    user_id: int, offer_id: int, trigger: str
) -> Dict[str, Any]:
    cleaned = (trigger or "").strip()
    if not cleaned:
        return {
            "text": "❌ Termo não pode estar vazio.\n\nDigite o termo novamente:",
            "keyboard": None,
        }

    if len(cleaned) > 128:
        return {
            "text": f"❌ Termo muito longo ({len(cleaned)} caracteres). Máximo: 128.",
            "keyboard": None,
        }

    await OfferRepository.update_offer(offer_id, discount_trigger=cleaned)
    ConversationStateManager.clear_state(user_id)
    return await handle_discount_menu(user_id, offer_id)


async def handle_discount_block_create(user_id: int, token: str) -> Dict[str, Any]:
    data = await validate_token(user_id, token, "a")
    if not data:
        return {
            "callback_alert": {
                "text": "⚠️ Ação inválida ou expirada.",
                "show_alert": True,
            }
        }

    blocks = await OfferDiscountBlockRepository.get_blocks_by_offer(data.offer_id)
    await OfferDiscountBlockRepository.create_block(
        offer_id=data.offer_id,
        order=len(blocks) + 1,
        text="",
        delay_seconds=0,
        auto_delete_seconds=0,
    )

    return await handle_discount_menu(user_id, data.offer_id)


async def handle_discount_preview(user_id: int, token: str) -> Dict[str, Any]:
    data = await validate_token(user_id, token, "p")
    if not data:
        return {
            "callback_alert": {
                "text": "⚠️ Ação inválida ou expirada.",
                "show_alert": True,
            }
        }

    sender = DiscountSender(settings.MANAGER_BOT_TOKEN)
    await sender.send_discount_blocks(
        offer_id=data.offer_id,
        chat_id=user_id,
        pix_code=None,
        preview_mode=True,
        bot_id=None,
    )

    api = TelegramAPI()
    menu = await handle_discount_menu(user_id, data.offer_id)
    await api.send_message(
        token=settings.MANAGER_BOT_TOKEN,
        chat_id=user_id,
        text=menu["text"],
        parse_mode="Markdown",
        reply_markup=menu["keyboard"],
    )

    logger.info(
        "Discount preview sent",
        extra={"offer_id": data.offer_id, "user_id": user_id},
    )

    return {"text": "✅ Pré-visualização enviada!", "keyboard": None}


__all__ = [
    "handle_discount_menu",
    "handle_discount_menu_from_token",
    "handle_discount_trigger_prompt",
    "handle_discount_trigger_input",
    "handle_discount_block_create",
    "handle_discount_preview",
    "build_discount_menu_token",
    "get_discount_token_action",
]
