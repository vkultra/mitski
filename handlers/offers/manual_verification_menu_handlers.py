"""
Handlers de menu de verificação manual
"""

from typing import Any, Dict

from core.config import settings
from database.repos import OfferManualVerificationBlockRepository, OfferRepository
from services.conversation_state import ConversationStateManager


async def handle_manual_verification_menu(
    user_id: int, offer_id: int
) -> Dict[str, Any]:
    """Menu de configuração de verificação manual"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    offer = await OfferRepository.get_offer_by_id(offer_id)
    if not offer:
        return {"text": "❌ Oferta não encontrada.", "keyboard": None}

    # Buscar blocos existentes
    blocks = await OfferManualVerificationBlockRepository.get_blocks_by_offer(offer_id)

    # Status do termo
    termo_status = (
        f"✅ `{offer.manual_verification_trigger}`"
        if offer.manual_verification_trigger
        else "❌ Não configurado"
    )

    # Botão do termo (dinâmico: mostra o termo se configurado)
    if offer.manual_verification_trigger:
        termo_button_text = f"🔑 {offer.manual_verification_trigger}"
    else:
        termo_button_text = "🔑 Configurar Termo de Ativação"

    # Montar botões dos blocos
    block_buttons = []
    for i, block in enumerate(blocks, 1):
        buttons_row = [
            {"text": f"{i}️⃣", "callback_data": f"manver_block_view:{block.id}"},
            {"text": "Efeitos", "callback_data": f"manver_block_effects:{block.id}"},
            {"text": "Mídia", "callback_data": f"manver_block_media:{block.id}"},
            {"text": "Texto/Legenda", "callback_data": f"manver_block_text:{block.id}"},
            {"text": "❌", "callback_data": f"manver_block_delete:{block.id}"},
        ]
        block_buttons.append(buttons_row)

    # Estrutura: [Termo] → [Blocos] → [Criar Bloco] → [Pré-visualizar] → [Voltar/Salvar]
    keyboard_buttons = (
        [
            [
                {
                    "text": termo_button_text,
                    "callback_data": f"manver_set_trigger:{offer_id}",
                }
            ]
        ]
        + block_buttons
        + [
            [
                {
                    "text": "➕ Criar Bloco",
                    "callback_data": f"manver_block_add:{offer_id}",
                }
            ],
            [
                {
                    "text": "👀 Pré-visualizar",
                    "callback_data": f"manver_block_preview:{offer_id}",
                }
            ],
            [
                {"text": "🔙 Voltar", "callback_data": f"offer_edit:{offer_id}"},
                {"text": "💾 Salvar", "callback_data": f"offer_edit:{offer_id}"},
            ],
        ]
    )

    keyboard = {"inline_keyboard": keyboard_buttons}

    value_text = f" ({offer.value})" if offer.value else ""

    return {
        "text": f"🔍 *Verificação Manual: {offer.name}{value_text}*\n\n"
        f"**Termo de Ativação:** {termo_status}\n\n"
        f"Quando a IA enviar este termo, o sistema verificará se há pagamento PIX pendente. "
        f"Se não houver pagamento, as mensagens abaixo serão enviadas.\n\n"
        f"Total de blocos: {len(blocks)}",
        "keyboard": keyboard,
    }


async def handle_set_verification_trigger(
    user_id: int, offer_id: int
) -> Dict[str, Any]:
    """Solicita termo de ativação"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    offer = await OfferRepository.get_offer_by_id(offer_id)
    if not offer:
        return {"text": "❌ Oferta não encontrada.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id, "awaiting_manver_trigger", {"offer_id": offer_id}
    )

    current_trigger = (
        f"\n\nTermo atual: `{offer.manual_verification_trigger}`"
        if offer.manual_verification_trigger
        else ""
    )

    return {
        "text": f"🔑 *Termo de Ativação da Verificação Manual*{current_trigger}\n\n"
        f"Digite o termo que a IA deve enviar para acionar a verificação manual:\n\n"
        f"Exemplo: `verificar pagamento`, `comprovar`, `enviei`\n\n"
        f"Quando a IA enviar exatamente este termo, o sistema verificará se há PIX pendente.",
        "keyboard": None,
    }


async def handle_verification_trigger_input(
    user_id: int, offer_id: int, trigger: str
) -> Dict[str, Any]:
    """Salva termo de ativação"""
    trigger = trigger.strip()

    if not trigger:
        return {
            "text": "❌ Termo não pode estar vazio.\n\nTente novamente:",
            "keyboard": None,
        }

    if len(trigger) > 128:
        return {
            "text": f"❌ Termo muito longo ({len(trigger)} caracteres). Máximo: 128.\n\nTente novamente:",
            "keyboard": None,
        }

    # Atualizar oferta
    await OfferRepository.update_offer(
        offer_id, manual_verification_trigger=trigger, requires_manual_verification=True
    )

    ConversationStateManager.clear_state(user_id)

    return await handle_manual_verification_menu(user_id, offer_id)


async def handle_create_manual_verification_block(
    user_id: int, offer_id: int
) -> Dict[str, Any]:
    """Adiciona novo bloco de verificação manual"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    # Calcular próxima ordem
    blocks = await OfferManualVerificationBlockRepository.get_blocks_by_offer(offer_id)
    next_order = len(blocks) + 1

    # Criar bloco vazio
    await OfferManualVerificationBlockRepository.create_block(
        offer_id=offer_id,
        order=next_order,
        text="",
        delay_seconds=0,
        auto_delete_seconds=0,
    )

    return await handle_manual_verification_menu(user_id, offer_id)


async def handle_delete_manual_verification_block(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    """Deleta bloco de verificação manual"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await OfferManualVerificationBlockRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    offer_id = block.offer_id
    await OfferManualVerificationBlockRepository.delete_block(block_id)

    return await handle_manual_verification_menu(user_id, offer_id)


async def handle_preview_manual_verification(
    user_id: int, offer_id: int
) -> Dict[str, Any]:
    """Pré-visualiza mensagens de verificação manual"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    offer = await OfferRepository.get_offer_by_id(offer_id)
    blocks = await OfferManualVerificationBlockRepository.get_blocks_by_offer(offer_id)

    if not blocks:
        return {
            "text": "❌ Nenhum bloco criado ainda.\n\nCrie pelo menos um bloco para visualizar.",
            "keyboard": None,
        }

    # Importar sender
    from services.offers.manual_verification_sender import ManualVerificationSender

    # Criar instância com token do bot gerenciador
    sender = ManualVerificationSender(settings.MANAGER_BOT_TOKEN)

    # Enviar mensagens
    await sender.send_manual_verification(offer_id=offer_id, chat_id=user_id)

    # Enviar nova mensagem com o menu (não editar mensagem anterior)
    from workers.api_clients import TelegramAPI

    api = TelegramAPI()
    menu_data = await handle_manual_verification_menu(user_id, offer_id)

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
