"""
Handlers de gerenciamento de entregáveis da oferta
"""

from typing import Any, Dict

from core.config import settings
from database.repos import OfferDeliverableRepository, OfferRepository
from services.conversation_state import ConversationStateManager


async def handle_offer_deliverable_menu(user_id: int, offer_id: int) -> Dict[str, Any]:
    """Menu de gerenciamento de entregáveis"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    offer = await OfferRepository.get_offer_by_id(offer_id)
    if not offer:
        return {"text": "❌ Oferta não encontrada.", "keyboard": None}

    # Buscar entregáveis existentes
    deliverables = await OfferDeliverableRepository.get_deliverables_by_offer(offer_id)

    # Construir lista de entregáveis
    deliverable_text = ""
    deliverable_buttons = []

    if deliverables:
        for i, deliverable in enumerate(deliverables, 1):
            content_preview = (
                deliverable.content[:50] + "..."
                if len(deliverable.content) > 50
                else deliverable.content
            )
            type_label = f" [{deliverable.type}]" if deliverable.type else ""
            deliverable_text += f"\n{i}. {content_preview}{type_label}"

            # Botão de deletar para cada entregável
            deliverable_buttons.append(
                [
                    {
                        "text": f"❌ Deletar #{i}",
                        "callback_data": f"deliverable_delete:{deliverable.id}",
                    }
                ]
            )
    else:
        deliverable_text = "\n_Nenhum entregável adicionado ainda._"

    keyboard = {
        "inline_keyboard": deliverable_buttons
        + [
            [
                {
                    "text": "➕ Adicionar Entregável",
                    "callback_data": f"deliverable_add:{offer_id}",
                }
            ],
            [
                {
                    "text": "🔙 Voltar",
                    "callback_data": f"offer_edit:{offer_id}",
                }
            ],
        ]
    }

    return {
        "text": f"📦 *Entregáveis da Oferta: {offer.name}*\n"
        f"{deliverable_text}\n\n"
        f"Os entregáveis são enviados ao usuário após a confirmação da compra.",
        "keyboard": keyboard,
    }


async def handle_create_deliverable(user_id: int, offer_id: int) -> Dict[str, Any]:
    """Inicia criação de entregável"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id, "awaiting_deliverable_content", {"offer_id": offer_id}
    )

    return {
        "text": "📦 *Adicionar Entregável*\n\n"
        "Digite o conteúdo do entregável:\n\n"
        "Exemplos:\n"
        "• Link do produto\n"
        "• Código de acesso\n"
        "• Instruções de uso\n"
        "• URL de download",
        "keyboard": None,
    }


async def handle_deliverable_content_input(
    user_id: int, offer_id: int, content: str
) -> Dict[str, Any]:
    """Salva conteúdo do entregável"""
    content = content.strip()

    if not content:
        return {
            "text": "❌ Conteúdo não pode estar vazio.\n\nTente novamente:",
            "keyboard": None,
        }

    if len(content) > 8192:
        return {
            "text": f"❌ Conteúdo muito longo ({len(content)} caracteres). "
            f"Máximo permitido: 8192 caracteres.\n\nTente novamente:",
            "keyboard": None,
        }

    # Detectar tipo do entregável automaticamente
    deliverable_type = None
    if content.startswith(("http://", "https://")):
        deliverable_type = "link"
    elif content.startswith(("/", "~/", "C:", "D:")):
        deliverable_type = "arquivo"
    elif len(content) <= 50 and content.replace("-", "").replace("_", "").isalnum():
        deliverable_type = "código"
    else:
        deliverable_type = "texto"

    # Criar entregável
    await OfferDeliverableRepository.create_deliverable(
        offer_id=offer_id, content=content, deliverable_type=deliverable_type
    )

    ConversationStateManager.clear_state(user_id)

    return await handle_offer_deliverable_menu(user_id, offer_id)


async def handle_delete_deliverable(
    user_id: int, deliverable_id: int
) -> Dict[str, Any]:
    """Deleta entregável"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    deliverable = await OfferDeliverableRepository.get_deliverable_by_id(deliverable_id)
    if not deliverable:
        return {"text": "❌ Entregável não encontrado.", "keyboard": None}

    offer_id = deliverable.offer_id
    await OfferDeliverableRepository.delete_deliverable(deliverable_id)

    return await handle_offer_deliverable_menu(user_id, offer_id)
