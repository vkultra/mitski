"""
Handlers de menu dos blocos de entregável
"""

from typing import Any, Dict

from core.config import settings
from database.repos import OfferDeliverableBlockRepository, OfferRepository


async def handle_deliverable_blocks_menu(user_id: int, offer_id: int) -> Dict[str, Any]:
    """Menu dos blocos de entregável"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    offer = await OfferRepository.get_offer_by_id(offer_id)
    if not offer:
        return {"text": "❌ Oferta não encontrada.", "keyboard": None}

    # Buscar blocos existentes
    blocks = await OfferDeliverableBlockRepository.get_blocks_by_offer(offer_id)

    # Montar botões dos blocos
    block_buttons = []
    for i, block in enumerate(blocks, 1):
        # Linha com 5 botões para cada bloco
        buttons_row = [
            {"text": f"{i}️⃣", "callback_data": f"deliv_block_view:{block.id}"},
            {"text": "Efeitos", "callback_data": f"deliv_block_effects:{block.id}"},
            {"text": "Mídia", "callback_data": f"deliv_block_media:{block.id}"},
            {"text": "Texto/Legenda", "callback_data": f"deliv_block_text:{block.id}"},
            {"text": "❌", "callback_data": f"deliv_block_delete:{block.id}"},
        ]
        block_buttons.append(buttons_row)

    # Botões finais
    keyboard_buttons = block_buttons + [
        [{"text": "➕ Criar Bloco", "callback_data": f"deliv_block_add:{offer_id}"}],
        [
            {
                "text": "👀 Pré-visualizar",
                "callback_data": f"deliv_block_preview:{offer_id}",
            }
        ],
        [
            {"text": "🔙 Voltar", "callback_data": f"offer_edit:{offer_id}"},
            {"text": "💾 Salvar", "callback_data": f"offer_edit:{offer_id}"},
        ],
    ]

    keyboard = {"inline_keyboard": keyboard_buttons}

    value_text = f" ({offer.value})" if offer.value else ""

    return {
        "text": f"📦 *Entregável (Blocos): {offer.name}{value_text}*\n\n"
        f"Cada linha representa uma mensagem que será enviada após o pagamento.\n\n"
        f"Total de blocos: {len(blocks)}",
        "keyboard": keyboard,
    }


async def handle_create_deliverable_block(
    user_id: int, offer_id: int
) -> Dict[str, Any]:
    """Adiciona novo bloco ao entregável"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    # Calcular próxima ordem
    blocks = await OfferDeliverableBlockRepository.get_blocks_by_offer(offer_id)
    next_order = len(blocks) + 1

    # Criar bloco vazio
    await OfferDeliverableBlockRepository.create_block(
        offer_id=offer_id,
        order=next_order,
        text="",
        delay_seconds=0,
        auto_delete_seconds=0,
    )

    # Voltar ao menu
    return await handle_deliverable_blocks_menu(user_id, offer_id)


async def handle_delete_deliverable_block(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    """Deleta bloco do entregável"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await OfferDeliverableBlockRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    offer_id = block.offer_id
    await OfferDeliverableBlockRepository.delete_block(block_id)

    return await handle_deliverable_blocks_menu(user_id, offer_id)


async def handle_preview_deliverable(user_id: int, offer_id: int) -> Dict[str, Any]:
    """Pré-visualiza o entregável enviando as mensagens reais"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    offer = await OfferRepository.get_offer_by_id(offer_id)
    blocks = await OfferDeliverableBlockRepository.get_blocks_by_offer(offer_id)

    if not blocks:
        return {
            "text": "❌ Nenhum bloco criado ainda.\n\nCrie pelo menos um bloco para visualizar.",
            "keyboard": None,
        }

    # Importar DeliverableSender para enviar as mensagens
    from services.offers.deliverable_sender import DeliverableSender

    # Criar instância com token do bot gerenciador
    deliverable_sender = DeliverableSender(settings.MANAGER_BOT_TOKEN)

    # Enviar entregável completo (preview_mode=False para mostrar tudo)
    await deliverable_sender.send_deliverable(
        offer_id=offer_id, chat_id=user_id, preview_mode=False
    )

    # Enviar nova mensagem com o menu (não editar mensagem anterior)
    from workers.api_clients import TelegramAPI

    api = TelegramAPI()
    menu_data = await handle_deliverable_blocks_menu(user_id, offer_id)

    await api.send_message(
        token=settings.MANAGER_BOT_TOKEN,
        chat_id=user_id,
        text=menu_data["text"],
        parse_mode="Markdown",
        reply_markup=menu_data["keyboard"],
    )

    # Retornar confirmação para editar mensagem do botão preview
    return {
        "text": "✅ Pré-visualização enviada! Veja os blocos abaixo.",
        "keyboard": None,
    }
