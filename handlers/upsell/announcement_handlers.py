"""
Handlers de menu do anúncio de upsell (sistema de blocos)
"""

from typing import Any, Dict

from core.config import settings
from database.repos import UpsellAnnouncementBlockRepository, UpsellRepository
from services.conversation_state import ConversationStateManager


async def handle_announcement_menu(user_id: int, upsell_id: int) -> Dict[str, Any]:
    """Menu do anúncio (sistema de blocos)"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    upsell = await UpsellRepository.get_upsell_by_id(upsell_id)
    if not upsell:
        return {"text": "❌ Upsell não encontrado.", "keyboard": None}

    # Buscar blocos existentes
    blocks = await UpsellAnnouncementBlockRepository.get_blocks_by_upsell(upsell_id)

    # Montar botões dos blocos
    block_buttons = []
    for i, block in enumerate(blocks, 1):
        # Linha com 5 botões para cada bloco
        buttons_row = [
            {"text": f"{i}️⃣", "callback_data": f"upsell_ann_view:{block.id}"},
            {"text": "Efeitos", "callback_data": f"upsell_ann_effects:{block.id}"},
            {"text": "Mídia", "callback_data": f"upsell_ann_media:{block.id}"},
            {"text": "Texto/Legenda", "callback_data": f"upsell_ann_text:{block.id}"},
            {"text": "❌", "callback_data": f"upsell_ann_delete:{block.id}"},
        ]
        block_buttons.append(buttons_row)

    # Botão criar bloco sempre no final
    keyboard_buttons = block_buttons + [
        [{"text": "➕ Criar Bloco", "callback_data": f"upsell_ann_add:{upsell_id}"}],
        [
            {
                "text": "👀 Pré-visualizar",
                "callback_data": f"upsell_ann_preview:{upsell_id}",
            }
        ],
        [
            {"text": "🔙 Voltar", "callback_data": f"upsell_select:{upsell_id}"},
            {"text": "💾 Salvar", "callback_data": f"upsell_select:{upsell_id}"},
        ],
    ]

    keyboard = {"inline_keyboard": keyboard_buttons}

    value_text = f" ({upsell.value})" if upsell.value else ""

    return {
        "text": f"📢 *Anúncio do Upsell: {upsell.name}{value_text}*\n\n"
        f"Cada linha representa uma mensagem que será enviada no anúncio.\n\n"
        f"💡 Use a tag `{{pixupsell}}` no texto para gerar chave PIX automática.\n\n"
        f"Total de blocos: {len(blocks)}",
        "keyboard": keyboard,
    }


async def handle_add_announcement_block(user_id: int, upsell_id: int) -> Dict[str, Any]:
    """Adiciona novo bloco ao anúncio"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    # Calcular próxima ordem
    blocks = await UpsellAnnouncementBlockRepository.get_blocks_by_upsell(upsell_id)
    next_order = len(blocks) + 1

    # Criar bloco vazio
    await UpsellAnnouncementBlockRepository.create_block(
        upsell_id=upsell_id,
        order=next_order,
    )

    # Voltar ao menu do anúncio
    return await handle_announcement_menu(user_id, upsell_id)


async def handle_delete_announcement_block(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    """Deleta bloco do anúncio"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await UpsellAnnouncementBlockRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    upsell_id = block.upsell_id
    await UpsellAnnouncementBlockRepository.delete_block(block_id)

    return await handle_announcement_menu(user_id, upsell_id)


async def handle_announcement_text_click(user_id: int, block_id: int) -> Dict[str, Any]:
    """Solicita texto/legenda do bloco"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await UpsellAnnouncementBlockRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_upsell_ann_text",
        {"block_id": block_id, "upsell_id": block.upsell_id},
    )

    current_text = f"\n\nTexto atual: `{block.text[:100]}...`" if block.text else ""

    return {
        "text": f"💬 *Texto/Legenda do Bloco*{current_text}\n\nDigite o texto da mensagem:\n\n"
        f"Se houver mídia, será usado como legenda. Se não, será uma mensagem de texto.\n\n"
        f"💡 Dica: Use `{{pixupsell}}` para gerar chave PIX automática.",
        "keyboard": None,
    }


async def handle_announcement_text_input(
    user_id: int, block_id: int, upsell_id: int, text: str
) -> Dict[str, Any]:
    """Salva texto do bloco"""
    await UpsellAnnouncementBlockRepository.update_block(block_id, text=text)
    ConversationStateManager.clear_state(user_id)

    return await handle_announcement_menu(user_id, upsell_id)


async def handle_announcement_media_click(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    """Solicita mídia do bloco"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await UpsellAnnouncementBlockRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_upsell_ann_media",
        {"block_id": block_id, "upsell_id": block.upsell_id},
    )

    current_media = (
        f"\n\nMídia atual: {block.media_type}" if block.media_file_id else ""
    )

    return {
        "text": f"📎 *Mídia do Bloco*{current_media}\n\nEnvie uma mídia (foto, vídeo, áudio, gif ou documento):\n\n"
        f"A mídia será reutilizada sempre que o anúncio for enviado.",
        "keyboard": None,
    }


async def handle_announcement_media_input(
    user_id: int,
    block_id: int,
    upsell_id: int,
    media_file_id: str,
    media_type: str,
) -> Dict[str, Any]:
    """Salva mídia do bloco"""
    await UpsellAnnouncementBlockRepository.update_block(
        block_id, media_file_id=media_file_id, media_type=media_type
    )
    ConversationStateManager.clear_state(user_id)

    return await handle_announcement_menu(user_id, upsell_id)


async def handle_announcement_effects_click(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    """Menu de efeitos do bloco"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await UpsellAnnouncementBlockRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "⏰ Delay", "callback_data": f"upsell_ann_delay:{block_id}"},
                {
                    "text": "🗑️ Auto-deletar",
                    "callback_data": f"upsell_ann_autodel:{block_id}",
                },
            ],
            [
                {
                    "text": "🔙 Voltar",
                    "callback_data": f"upsell_announcement:{block.upsell_id}",
                }
            ],
        ]
    }

    delay_text = (
        f"Delay: {block.delay_seconds}s" if block.delay_seconds else "Sem delay"
    )
    auto_del_text = (
        f"Auto-deletar: {block.auto_delete_seconds}s"
        if block.auto_delete_seconds
        else "Sem auto-exclusão"
    )

    return {
        "text": f"⏱️ *Efeitos do Bloco*\n\n{delay_text}\n{auto_del_text}\n\nEscolha o efeito para configurar:",
        "keyboard": keyboard,
    }


async def handle_announcement_delay_click(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    """Solicita delay do bloco"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await UpsellAnnouncementBlockRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_upsell_ann_delay",
        {"block_id": block_id, "upsell_id": block.upsell_id},
    )

    return {
        "text": f"⏰ *Delay do Bloco*\n\nDigite o tempo de espera em segundos (0-300):\n\n"
        f"Exemplo: `5` para 5 segundos\n\nDelay atual: {block.delay_seconds}s",
        "keyboard": None,
    }


async def handle_announcement_delay_input(
    user_id: int, block_id: int, upsell_id: int, delay: str
) -> Dict[str, Any]:
    """Salva delay do bloco"""
    try:
        delay_seconds = int(delay)
        if delay_seconds < 0 or delay_seconds > 300:
            return {
                "text": "❌ Delay deve estar entre 0 e 300 segundos.\n\nTente novamente:",
                "keyboard": None,
            }
    except ValueError:
        return {
            "text": "❌ Digite apenas números.\n\nTente novamente:",
            "keyboard": None,
        }

    await UpsellAnnouncementBlockRepository.update_block(
        block_id, delay_seconds=delay_seconds
    )
    ConversationStateManager.clear_state(user_id)

    return await handle_announcement_effects_click(user_id, block_id)


async def handle_announcement_autodel_click(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    """Solicita tempo de auto-exclusão"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await UpsellAnnouncementBlockRepository.get_block_by_id(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_upsell_ann_autodel",
        {"block_id": block_id, "upsell_id": block.upsell_id},
    )

    return {
        "text": f"🗑️ *Auto-exclusão do Bloco*\n\nDigite o tempo em segundos para auto-deletar (0-3600):\n\n"
        f"Exemplo: `30` para deletar após 30 segundos\n`0` para não deletar\n\n"
        f"Tempo atual: {block.auto_delete_seconds}s",
        "keyboard": None,
    }


async def handle_announcement_autodel_input(
    user_id: int, block_id: int, upsell_id: int, autodel: str
) -> Dict[str, Any]:
    """Salva tempo de auto-exclusão"""
    try:
        autodel_seconds = int(autodel)
        if autodel_seconds < 0 or autodel_seconds > 3600:
            return {
                "text": "❌ Auto-exclusão deve estar entre 0 e 3600 segundos.\n\nTente novamente:",
                "keyboard": None,
            }
    except ValueError:
        return {
            "text": "❌ Digite apenas números.\n\nTente novamente:",
            "keyboard": None,
        }

    await UpsellAnnouncementBlockRepository.update_block(
        block_id, auto_delete_seconds=autodel_seconds
    )
    ConversationStateManager.clear_state(user_id)

    return await handle_announcement_effects_click(user_id, block_id)


async def handle_preview_announcement(user_id: int, upsell_id: int) -> Dict[str, Any]:
    """Pré-visualiza o anúncio enviando as mensagens reais"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    upsell = await UpsellRepository.get_upsell_by_id(upsell_id)
    blocks = await UpsellAnnouncementBlockRepository.get_blocks_by_upsell(upsell_id)

    if not blocks:
        return {
            "text": "❌ Nenhum bloco criado ainda.\n\nCrie pelo menos um bloco para visualizar.",
            "keyboard": None,
        }

    # Importar AnnouncementSender para enviar as mensagens
    from services.upsell import AnnouncementSender

    # Criar instância com token do bot gerenciador (preview é enviado no bot gerenciador)
    announcement_sender = AnnouncementSender(settings.MANAGER_BOT_TOKEN)

    # Enviar o anúncio completo ao usuário (preview, sem bot_id para não usar stream)
    await announcement_sender.send_announcement(
        upsell_id=upsell_id, chat_id=user_id, bot_id=None
    )

    # Enviar nova mensagem com o menu (não editar mensagem anterior)
    from workers.api_clients import TelegramAPI

    api = TelegramAPI()
    menu_data = await handle_announcement_menu(user_id, upsell_id)

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
