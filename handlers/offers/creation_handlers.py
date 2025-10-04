"""
Handlers de criação e edição de ofertas
"""

from typing import Any, Dict

from core.config import settings
from database.repos import OfferRepository
from services.conversation_state import ConversationStateManager


async def handle_create_offer(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Inicia criação de oferta"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id, "awaiting_offer_name", {"bot_id": bot_id}
    )

    return {
        "text": "📝 *Criar Nova Oferta*\n\nDigite o nome da oferta:\n\nExemplo: `Curso Premium`, `Consultoria VIP`",
        "keyboard": None,
    }


async def handle_offer_name_input(
    user_id: int, bot_id: int, name: str
) -> Dict[str, Any]:
    """Processa nome da oferta"""
    name = name.strip()

    if len(name) < 2:
        return {
            "text": "❌ Nome muito curto. Use pelo menos 2 caracteres.\n\nTente novamente:",
            "keyboard": None,
        }

    # Verificar se já existe
    existing = await OfferRepository.get_offer_by_name(bot_id, name)
    if existing:
        return {
            "text": f"❌ Já existe uma oferta com o nome `{name}`.\n\nEscolha outro nome:",
            "keyboard": None,
        }

    # Criar oferta inicial
    offer = await OfferRepository.create_offer(bot_id, name)

    ConversationStateManager.clear_state(user_id)

    # Redirecionar para menu de edição
    from .edit_handlers import handle_offer_edit_menu

    return await handle_offer_edit_menu(user_id, offer.id)


async def handle_offer_value_input(
    user_id: int, bot_id: int, offer_id: int, value: str
) -> Dict[str, Any]:
    """Processa valor da oferta"""
    # Import aqui para evitar circular import
    from .pitch_menu_handlers import handle_offer_pitch_menu

    value = value.strip()

    # Atualizar valor
    await OfferRepository.update_offer(offer_id, value=value)

    ConversationStateManager.clear_state(user_id)

    return await handle_offer_pitch_menu(user_id, offer_id)


async def handle_save_offer(user_id: int, offer_id: int) -> Dict[str, Any]:
    """Salva oferta e volta ao menu"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    offer = await OfferRepository.get_offer_by_id(offer_id)

    return {
        "text": f"✅ Oferta `{offer.name}` salva com sucesso!\n\n"
        f"Quando a IA enviar o nome desta oferta, o pitch será automaticamente enviado ao usuário.",
        "keyboard": None,
    }
