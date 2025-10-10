"""
Handlers de edição de ofertas com menu centralizado
"""

from typing import Any, Dict

from core.config import settings
from database.repos import (
    OfferDeliverableBlockRepository,
    OfferDeliverableRepository,
    OfferDiscountBlockRepository,
    OfferManualVerificationBlockRepository,
    OfferPitchRepository,
    OfferRepository,
)
from services.conversation_state import ConversationStateManager

from .discount_utils import build_menu_token, escape_markdown


async def handle_offer_edit_menu(user_id: int, offer_id: int) -> Dict[str, Any]:
    """Menu principal de edição da oferta"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    offer = await OfferRepository.get_offer_by_id(offer_id)
    if not offer:
        return {"text": "❌ Oferta não encontrada.", "keyboard": None}

    # Verificar completude de cada seção
    has_value = bool(offer.value and offer.value.strip())
    pitch_blocks = await OfferPitchRepository.get_blocks_by_offer(offer_id)
    has_pitch = len(pitch_blocks) > 0
    deliverables = await OfferDeliverableRepository.get_deliverables_by_offer(offer_id)
    has_deliverable = len(deliverables) > 0
    deliverable_blocks = await OfferDeliverableBlockRepository.get_blocks_by_offer(
        offer_id
    )
    has_deliverable_blocks = len(deliverable_blocks) > 0
    manual_verification_blocks = (
        await OfferManualVerificationBlockRepository.get_blocks_by_offer(offer_id)
    )
    has_manual_verification = (
        bool(offer.manual_verification_trigger) and len(manual_verification_blocks) > 0
    )
    discount_blocks = await OfferDiscountBlockRepository.get_blocks_by_offer(offer_id)
    has_discount = bool(offer.discount_trigger and len(discount_blocks) > 0)

    # Emojis de completude
    value_emoji = "✅ " if has_value else ""
    pitch_emoji = "✅ " if has_pitch else ""
    deliverable_emoji = "✅ " if has_deliverable else ""
    deliverable_blocks_emoji = "✅ " if has_deliverable_blocks else ""
    verification_emoji = "✅ " if has_manual_verification else ""
    discount_emoji = "✅ " if has_discount else ""

    # Texto do botão Valor com valor entre parênteses
    value_button_text = f"{value_emoji}💰 Valor"
    if has_value:
        value_button_text += f" ({offer.value})"

    # Construir teclado
    keyboard = {
        "inline_keyboard": [
            # Linha 1: Valor
            [
                {
                    "text": value_button_text,
                    "callback_data": f"offer_value_click:{offer_id}",
                }
            ],
            # Linha 2: Pitch e Entregável
            [
                {
                    "text": f"{pitch_emoji}📋 Pitch da Oferta",
                    "callback_data": f"offer_pitch:{offer_id}",
                },
                {
                    "text": f"{deliverable_blocks_emoji}📦 Entregável",
                    "callback_data": f"deliv_blocks:{offer_id}",
                },
            ],
            # Linha 3: Descontos e Verificação Manual
            [
                {
                    "text": f"{discount_emoji}🏷️ Descontos",
                    "callback_data": f"disc_m:{build_menu_token(user_id, offer_id)}",
                },
                {
                    "text": f"{verification_emoji}🔍 Verificação Manual",
                    "callback_data": f"manver_menu:{offer_id}",
                },
            ],
            # Linha 5: Voltar e Salvar
            [
                {
                    "text": "🔙 Voltar",
                    "callback_data": f"offer_menu:{offer.bot_id}",
                },
                {
                    "text": "💾 SALVAR",
                    "callback_data": f"offer_save_final:{offer_id}",
                },
            ],
        ]
    }

    value_text = f" ({offer.value})" if has_value else ""

    display_offer_name = escape_markdown(offer.name)
    manual_trigger_display = (
        escape_markdown(offer.manual_verification_trigger)
        if offer.manual_verification_trigger
        else "Não definido"
    )
    discount_trigger_display = (
        escape_markdown(offer.discount_trigger)
        if offer.discount_trigger
        else "Não definido"
    )

    return {
        "text": f"✏️ *Editando: {display_offer_name}{value_text}*\n\n"
        f"Configure sua oferta:\n\n"
        f"{'✅' if has_value else '⬜'} Valor definido\n"
        f"{'✅' if has_pitch else '⬜'} Pitch configurado ({len(pitch_blocks)} blocos)\n"
        f"{'✅' if has_deliverable_blocks else '⬜'} Entregável configurado ({len(deliverable_blocks)} blocos)\n"
        f"{'✅' if has_discount else '⬜'} Descontos configurados (Termo: {discount_trigger_display}, {len(discount_blocks)} blocos)\n"
        f"{'✅' if has_manual_verification else '⬜'} Verificação manual configurada (Termo: {manual_trigger_display}, {len(manual_verification_blocks)} blocos)\n\n"
        f"Clique em SALVAR quando terminar.",
        "keyboard": keyboard,
    }


async def handle_offer_value_click(user_id: int, offer_id: int) -> Dict[str, Any]:
    """Solicita valor da oferta"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    offer = await OfferRepository.get_offer_by_id(offer_id)
    if not offer:
        return {"text": "❌ Oferta não encontrada.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id, "awaiting_offer_value_edit", {"offer_id": offer_id}
    )

    current_value = f"\n\nValor atual: `{offer.value}`" if offer.value else ""

    return {
        "text": f"💰 *Valor da Oferta*{current_value}\n\n"
        f"Digite o valor da oferta:\n\n"
        f"Exemplo: `R$ 97,00`, `R$ 497,00`, `US$ 29.90`",
        "keyboard": None,
    }


async def handle_offer_value_edit_input(
    user_id: int, offer_id: int, value: str
) -> Dict[str, Any]:
    """Salva valor da oferta e retorna ao menu de edição"""
    value = value.strip()

    if not value:
        return {
            "text": "❌ Valor não pode estar vazio.\n\nTente novamente:",
            "keyboard": None,
        }

    # Atualizar valor
    await OfferRepository.update_offer(offer_id, value=value)

    ConversationStateManager.clear_state(user_id)

    return await handle_offer_edit_menu(user_id, offer_id)


async def handle_offer_manual_verification_toggle(
    user_id: int, offer_id: int
) -> Dict[str, Any]:
    """Alterna verificação manual da oferta"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    offer = await OfferRepository.get_offer_by_id(offer_id)
    if not offer:
        return {"text": "❌ Oferta não encontrada.", "keyboard": None}

    # Alternar valor
    new_value = not offer.requires_manual_verification

    await OfferRepository.update_offer(offer_id, requires_manual_verification=new_value)

    return await handle_offer_edit_menu(user_id, offer_id)


async def handle_offer_save_final(user_id: int, offer_id: int) -> Dict[str, Any]:
    """Finaliza e salva a oferta"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    offer = await OfferRepository.get_offer_by_id(offer_id)
    if not offer:
        return {"text": "❌ Oferta não encontrada.", "keyboard": None}

    # Verificar se tem pitch configurado
    pitch_blocks = await OfferPitchRepository.get_blocks_by_offer(offer_id)

    if len(pitch_blocks) == 0:
        return {
            "text": "⚠️ *Atenção*\n\n"
            "Você ainda não configurou o pitch desta oferta.\n\n"
            "Recomendamos adicionar pelo menos um bloco ao pitch antes de salvar.",
            "keyboard": {
                "inline_keyboard": [
                    [
                        {
                            "text": "🔙 Voltar para Edição",
                            "callback_data": f"offer_edit:{offer_id}",
                        }
                    ]
                ]
            },
        }

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "🔙 Voltar ao Menu de Ofertas",
                    "callback_data": f"offer_menu:{offer.bot_id}",
                }
            ]
        ]
    }

    value_text = f" ({offer.value})" if offer.value else ""

    # Verificar configuração de verificação manual
    manual_verification_blocks = (
        await OfferManualVerificationBlockRepository.get_blocks_by_offer(offer_id)
    )
    deliverable_blocks = await OfferDeliverableBlockRepository.get_blocks_by_offer(
        offer_id
    )

    if offer.manual_verification_trigger and len(manual_verification_blocks) > 0:
        verification_text = (
            f"\n🔍 Verificação manual ativa "
            f"(Termo: `{offer.manual_verification_trigger}`, "
            f"{len(manual_verification_blocks)} blocos)"
        )
    else:
        verification_text = "\n⬜ Verificação manual não configurada"

    return {
        "text": f"✅ *Oferta Salva com Sucesso!*\n\n"
        f"📋 Nome: `{offer.name}`{value_text}\n"
        f"📦 Pitch: {len(pitch_blocks)} blocos\n"
        f"📦 Entregável: {len(deliverable_blocks)} blocos"
        f"{verification_text}\n\n"
        f"Quando a IA mencionar `{offer.name}` (case-insensitive), "
        f"o pitch será automaticamente enviado ao usuário.",
        "keyboard": keyboard,
    }
