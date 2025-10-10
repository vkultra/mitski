"""Menu de configuração da mensagem inicial /start"""

from typing import Any, Dict, List

from core.config import settings
from database.repos import StartTemplateBlockRepository, StartTemplateRepository
from services.start import StartTemplateService


async def handle_start_template_menu(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Exibe o editor de blocos da mensagem inicial"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    template = await StartTemplateRepository.get_or_create(bot_id)
    blocks = await StartTemplateBlockRepository.list_blocks(template.id)

    keyboard_buttons: List[List[Dict[str, str]]] = []

    for position, block in enumerate(blocks, start=1):
        keyboard_buttons.append(
            [
                {
                    "text": f"{position}️⃣",
                    "callback_data": f"start_block_view:{block.id}",
                },
                {"text": "Efeitos", "callback_data": f"start_block_effects:{block.id}"},
                {"text": "Mídia", "callback_data": f"start_block_media:{block.id}"},
                {
                    "text": "Texto/Legenda",
                    "callback_data": f"start_block_text:{block.id}",
                },
                {"text": "❌", "callback_data": f"start_block_delete:{block.id}"},
            ]
        )

    keyboard_buttons.append(
        [{"text": "➕ Criar Bloco", "callback_data": f"start_block_add:{template.id}"}]
    )
    keyboard_buttons.append(
        [{"text": "👀 Pré-visualizar", "callback_data": f"start_preview:{template.id}"}]
    )

    keyboard_buttons.append(
        [{"text": "🔙 Voltar", "callback_data": f"action_menu:{bot_id}"}]
    )

    block_count = len(blocks)

    return {
        "text": (
            "🚀 *Mensagem Inicial (/start)*\n\n"
            f"Blocos configurados: {block_count}\n\n"
            "Cada bloco será enviado na ordem acima quando o usuário enviar /start pela primeira vez."
        ),
        "keyboard": {"inline_keyboard": keyboard_buttons},
    }


async def handle_start_template_add_block(
    user_id: int, template_id: int
) -> Dict[str, Any]:
    """Cria um novo bloco no template"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    template = await StartTemplateRepository.get_by_id(template_id)
    if not template:
        return {"text": "❌ Template não encontrado.", "keyboard": None}

    blocks = await StartTemplateBlockRepository.list_blocks(template_id)
    next_order = len(blocks) + 1

    await StartTemplateBlockRepository.create_block(
        template_id=template_id,
        order=next_order,
        text="",
        delay_seconds=0,
        auto_delete_seconds=0,
    )

    await StartTemplateService.bump_version(template.id)

    return await handle_start_template_menu(user_id, template.bot_id)


async def handle_start_template_delete_block(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    """Remove bloco e reordena sequência"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    template_id = await StartTemplateBlockRepository.delete_block(block_id)
    if not template_id:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    template = await StartTemplateRepository.get_by_id(template_id)
    if not template:
        return {"text": "❌ Template não encontrado.", "keyboard": None}

    await StartTemplateService.bump_version(template_id)

    return await handle_start_template_menu(user_id, template.bot_id)


async def handle_start_template_toggle(
    user_id: int, template_id: int
) -> Dict[str, Any]:
    """Alterna ativação da mensagem inicial"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    template = await StartTemplateRepository.get_by_id(template_id)
    if not template:
        return {"text": "❌ Template não encontrado.", "keyboard": None}

    new_status = not template.is_active
    await StartTemplateRepository.update_template(template_id, is_active=new_status)
    StartTemplateService.invalidate_cache(template.bot_id)

    status_text = "✅ Mensagem ativada!" if new_status else "⏸️ Mensagem desativada."

    result = await handle_start_template_menu(user_id, template.bot_id)
    result["text"] = f"{status_text}\n\n" + result["text"]
    return result


async def handle_start_template_preview(
    user_id: int, template_id: int
) -> Dict[str, Any]:
    """Envia pré-visualização da mensagem inicial"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    template = await StartTemplateRepository.get_by_id(template_id)
    if not template:
        return {"text": "❌ Template não encontrado.", "keyboard": None}

    blocks = await StartTemplateBlockRepository.list_blocks(template_id)
    if not blocks:
        return {
            "text": "❌ Nenhum bloco configurado ainda.\n\nCrie pelo menos um bloco para visualizar.",
            "keyboard": None,
        }

    from services.start.start_sender import StartTemplateSenderService
    from workers.api_clients import TelegramAPI

    sender = StartTemplateSenderService(settings.MANAGER_BOT_TOKEN)
    await sender.send_template(
        template_id=template_id,
        bot_id=template.bot_id,
        chat_id=user_id,
        preview_mode=True,
        cache_media=False,
    )

    menu_data = await handle_start_template_menu(user_id, template.bot_id)

    api = TelegramAPI()
    await api.send_message(
        token=settings.MANAGER_BOT_TOKEN,
        chat_id=user_id,
        text=menu_data["text"],
        parse_mode="Markdown",
        reply_markup=menu_data["keyboard"],
    )

    return {
        "text": "✅ Pré-visualização enviada! Veja as mensagens abaixo.",
        "keyboard": None,
    }
