"""
Handlers de menu e navegação de ofertas
"""

from typing import Any, Dict

from core.config import settings
from database.repos import BotRepository, OfferRepository


async def handle_offer_menu(user_id: int, bot_id: int, page: int = 1) -> Dict[str, Any]:
    """Menu principal de ofertas com listagem, associação e paginação"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    # Buscar bot para saber qual oferta está associada
    bot = await BotRepository.get_bot_by_id(bot_id)
    if not bot:
        return {"text": "❌ Bot não encontrado.", "keyboard": None}

    # Buscar todas as ofertas (mais recentes no final)
    all_offers = await OfferRepository.get_offers_by_bot(bot_id, active_only=True)
    # Ordenar por created_at ASC (mais antigas primeiro, mais recentes no final)
    all_offers = sorted(all_offers, key=lambda o: o.created_at)

    # Paginação: 5 ofertas por página
    ITEMS_PER_PAGE = 5
    total_offers = len(all_offers)
    total_pages = (
        (total_offers + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE if total_offers > 0 else 1
    )

    # Ajustar página se for inválida
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages

    # Calcular índices de slice
    start_idx = (page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_offers = all_offers[start_idx:end_idx]

    # Botões de ação no topo
    action_buttons = [
        [
            {"text": "➕ Criar Nova Oferta", "callback_data": f"offer_create:{bot_id}"},
            {
                "text": "🗑️ Excluir Oferta",
                "callback_data": f"offer_list_delete:{bot_id}",
            },
        ]
    ]

    # Montar botões das ofertas da página atual
    offer_buttons = []
    for offer in page_offers:
        # Verificar se esta oferta está associada ao bot atual
        is_associated = bot.associated_offer_id == offer.id

        # Nome do botão de oferta
        value_text = f" ({offer.value})" if offer.value else ""
        offer_name = f"{'✅ ' if is_associated else ''}{offer.name}{value_text}"

        # Botão de associação
        if is_associated:
            assoc_button_text = "🔗 Associado"
            assoc_callback = f"offer_dissociate:{bot_id}:{offer.id}"
        else:
            assoc_button_text = "➕ Associar"
            assoc_callback = f"offer_associate:{bot_id}:{offer.id}"

        offer_buttons.append(
            [
                {"text": offer_name, "callback_data": f"offer_edit:{offer.id}"},
                {"text": assoc_button_text, "callback_data": assoc_callback},
            ]
        )

    # Botões de navegação
    nav_buttons = []
    if total_pages > 1:
        nav_row = []
        if page > 1:
            nav_row.append(
                {
                    "text": "⬅️ Anterior",
                    "callback_data": f"offer_menu_page:{bot_id}:{page-1}",
                }
            )
        nav_row.append({"text": f"📄 {page}/{total_pages}", "callback_data": "noop"})
        if page < total_pages:
            nav_row.append(
                {
                    "text": "➡️ Próximo",
                    "callback_data": f"offer_menu_page:{bot_id}:{page+1}",
                }
            )
        nav_buttons.append(nav_row)

    # Botão voltar
    back_button = [{"text": "🔙 Voltar", "callback_data": f"ai_select_bot:{bot_id}"}]

    keyboard = {
        "inline_keyboard": action_buttons + offer_buttons + nav_buttons + [back_button]
    }

    # Informação sobre oferta associada
    if bot.associated_offer_id:
        associated_offer = next(
            (o for o in all_offers if o.id == bot.associated_offer_id), None
        )
        assoc_info = f"\n\n**Oferta Associada:** {associated_offer.name if associated_offer else 'Desconhecida'}"
    else:
        assoc_info = "\n\n_Nenhuma oferta associada a este bot._"

    return {
        "text": f"💰 *Menu de Ofertas*\n\nBot: {bot.display_name or bot.username}"
        f"{assoc_info}\n\n"
        f"Ofertas: {total_offers} | Página: {page}/{total_pages}\n\n"
        f"Clique no nome da oferta para editar ou em 'Associar' para vincular ao bot.",
        "keyboard": keyboard,
    }


async def handle_list_offers(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Lista ofertas do bot"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    offers = await OfferRepository.get_offers_by_bot(bot_id)

    if not offers:
        return {
            "text": "📭 Nenhuma oferta cadastrada ainda.",
            "keyboard": {
                "inline_keyboard": [
                    [{"text": "🔙 Voltar", "callback_data": f"offer_menu:{bot_id}"}]
                ]
            },
        }

    buttons = []
    for offer in offers:
        value_text = f" - {offer.value}" if offer.value else ""
        buttons.append(
            [
                {
                    "text": f"📦 {offer.name}{value_text}",
                    "callback_data": f"offer_pitch:{offer.id}",
                }
            ]
        )

    buttons.append([{"text": "🔙 Voltar", "callback_data": f"offer_menu:{bot_id}"}])

    return {
        "text": f"📋 *Ofertas Cadastradas*\n\nTotal: {len(offers)}",
        "keyboard": {"inline_keyboard": buttons},
    }


async def handle_list_offers_delete(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Lista ofertas para deletar"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    offers = await OfferRepository.get_offers_by_bot(bot_id)

    if not offers:
        return {
            "text": "📭 Nenhuma oferta para excluir.",
            "keyboard": {
                "inline_keyboard": [
                    [{"text": "🔙 Voltar", "callback_data": f"offer_menu:{bot_id}"}]
                ]
            },
        }

    buttons = []
    for offer in offers:
        buttons.append(
            [
                {
                    "text": f"🗑️ {offer.name}",
                    "callback_data": f"offer_delete_confirm:{offer.id}",
                }
            ]
        )

    buttons.append([{"text": "🔙 Voltar", "callback_data": f"offer_menu:{bot_id}"}])

    return {
        "text": "🗑️ *Excluir Oferta*\n\nSelecione a oferta para excluir:",
        "keyboard": {"inline_keyboard": buttons},
    }


async def handle_delete_offer_confirm(user_id: int, offer_id: int) -> Dict[str, Any]:
    """Confirma exclusão da oferta"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    offer = await OfferRepository.get_offer_by_id(offer_id)
    if not offer:
        return {"text": "❌ Oferta não encontrada.", "keyboard": None}

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Sim, excluir",
                    "callback_data": f"offer_delete:{offer_id}",
                },
                {"text": "❌ Cancelar", "callback_data": f"offer_menu:{offer.bot_id}"},
            ]
        ]
    }

    return {
        "text": f"⚠️ *Confirmar Exclusão*\n\nDeseja realmente excluir a oferta `{offer.name}`?\n\n"
        f"Esta ação não pode ser desfeita.",
        "keyboard": keyboard,
    }


async def handle_delete_offer(user_id: int, offer_id: int) -> Dict[str, Any]:
    """Exclui oferta definitivamente"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    offer = await OfferRepository.get_offer_by_id(offer_id)
    if not offer:
        return {"text": "❌ Oferta não encontrada.", "keyboard": None}

    bot_id = offer.bot_id
    await OfferRepository.delete_offer(offer_id)

    return {
        "text": f"✅ Oferta `{offer.name}` excluída com sucesso.",
        "keyboard": {
            "inline_keyboard": [
                [{"text": "🔙 Voltar", "callback_data": f"offer_menu:{bot_id}"}]
            ]
        },
    }


async def handle_associate_offer(
    user_id: int, bot_id: int, offer_id: int
) -> Dict[str, Any]:
    """Associa oferta ao bot"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    # Verificar se bot existe
    bot = await BotRepository.get_bot_by_id(bot_id)
    if not bot:
        return {"text": "❌ Bot não encontrado.", "keyboard": None}

    # Verificar se oferta existe
    offer = await OfferRepository.get_offer_by_id(offer_id)
    if not offer:
        return {"text": "❌ Oferta não encontrada.", "keyboard": None}

    # Associar oferta ao bot
    await BotRepository.associate_offer(bot_id, offer_id)

    # Retornar ao menu de ofertas
    return await handle_offer_menu(user_id, bot_id)


async def handle_dissociate_offer(
    user_id: int, bot_id: int, offer_id: int
) -> Dict[str, Any]:
    """Remove associação de oferta do bot"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    # Verificar se bot existe
    bot = await BotRepository.get_bot_by_id(bot_id)
    if not bot:
        return {"text": "❌ Bot não encontrado.", "keyboard": None}

    # Remover associação
    await BotRepository.dissociate_offer(bot_id)

    # Retornar ao menu de ofertas
    return await handle_offer_menu(user_id, bot_id)
