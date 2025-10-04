"""
Handlers de menu do pitch de vendas
"""

from typing import Any, Dict

from core.config import settings
from database.repos import OfferPitchRepository, OfferRepository


async def handle_offer_pitch_menu(user_id: int, offer_id: int) -> Dict[str, Any]:
    """Menu do pitch de vendas"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    offer = await OfferRepository.get_offer_by_id(offer_id)
    if not offer:
        return {"text": "❌ Oferta não encontrada.", "keyboard": None}

    # Buscar blocos existentes
    blocks = await OfferPitchRepository.get_blocks_by_offer(offer_id)

    # Montar botões dos blocos
    block_buttons = []
    for i, block in enumerate(blocks, 1):
        # Linha com 5 botões para cada bloco
        buttons_row = [
            {"text": f"{i}️⃣", "callback_data": f"pitch_view:{block.id}"},
            {"text": "Efeitos", "callback_data": f"pitch_effects:{block.id}"},
            {"text": "Mídia", "callback_data": f"pitch_media:{block.id}"},
            {"text": "Texto/Legenda", "callback_data": f"pitch_text:{block.id}"},
            {"text": "❌", "callback_data": f"pitch_delete:{block.id}"},
        ]
        block_buttons.append(buttons_row)

    # Botão criar bloco sempre no final
    keyboard_buttons = block_buttons + [
        [{"text": "➕ Criar Bloco", "callback_data": f"pitch_add:{offer_id}"}],
        [{"text": "👀 Pré-visualizar", "callback_data": f"pitch_preview:{offer_id}"}],
        [
            {"text": "🔙 Voltar", "callback_data": f"offer_edit:{offer_id}"},
            {"text": "💾 Salvar", "callback_data": f"offer_edit:{offer_id}"},
        ],
    ]

    keyboard = {"inline_keyboard": keyboard_buttons}

    value_text = f" ({offer.value})" if offer.value else ""

    return {
        "text": f"📋 *Pitch da Oferta: {offer.name}{value_text}*\n\n"
        f"Cada linha representa uma mensagem que será enviada quando a oferta for acionada.\n\n"
        f"Total de blocos: {len(blocks)}",
        "keyboard": keyboard,
    }


async def handle_create_pitch_block(user_id: int, offer_id: int) -> Dict[str, Any]:
    """Adiciona novo bloco ao pitch"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    # Calcular próxima ordem
    blocks = await OfferPitchRepository.get_blocks_by_offer(offer_id)
    next_order = len(blocks) + 1

    # Criar bloco vazio
    block = await OfferPitchRepository.create_block(
        offer_id=offer_id,
        order=next_order,
        text="",
        delay_seconds=0,
        auto_delete_seconds=0,
    )

    # Voltar ao menu do pitch
    return await handle_offer_pitch_menu(user_id, offer_id)


async def handle_delete_block(user_id: int, block_id: int) -> Dict[str, Any]:
    """Deleta bloco do pitch"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await OfferPitchRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    offer_id = block.offer_id
    await OfferPitchRepository.delete_block(block_id)

    return await handle_offer_pitch_menu(user_id, offer_id)


async def handle_preview_pitch(user_id: int, offer_id: int) -> Dict[str, Any]:
    """Pré-visualiza o pitch enviando as mensagens reais"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    offer = await OfferRepository.get_offer_by_id(offer_id)
    blocks = await OfferPitchRepository.get_blocks_by_offer(offer_id)

    if not blocks:
        return {
            "text": "❌ Nenhum bloco criado ainda.\n\nCrie pelo menos um bloco para visualizar.",
            "keyboard": None,
        }

    # Importar PitchSenderService para enviar as mensagens
    from services.offers.pitch_sender import PitchSenderService

    # Criar instância do serviço com o token do bot gerenciador
    pitch_sender = PitchSenderService(settings.MANAGER_BOT_TOKEN)

    # Enviar o pitch completo ao usuário (com delays e auto-delete)
    # preview_mode=False para aplicar delays e auto-delete
    await pitch_sender.send_pitch(
        offer_id=offer_id, chat_id=user_id, preview_mode=False
    )

    # Enviar nova mensagem com o menu (não editar mensagem anterior)
    from workers.api_clients import TelegramAPI

    api = TelegramAPI()
    menu_data = await handle_offer_pitch_menu(user_id, offer_id)

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
