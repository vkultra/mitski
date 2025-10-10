from typing import Any, Dict

from core.config import settings
from database.repos import StartTemplateBlockRepository, StartTemplateRepository
from services.conversation_state import ConversationStateManager
from services.start import StartTemplateService

from .start_template_menu_handlers import handle_start_template_menu


async def handle_start_template_view_block(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await StartTemplateBlockRepository.get_block(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    template = await StartTemplateRepository.get_by_id(block.template_id)
    if not template:
        return {"text": "❌ Template não encontrado.", "keyboard": None}

    media_info = block.media_type if block.media_file_id else "—"
    delay_info = f"{block.delay_seconds}s" if block.delay_seconds else "Sem delay"
    autodel_info = (
        f"{block.auto_delete_seconds}s"
        if block.auto_delete_seconds
        else "Sem auto-delete"
    )

    return {
        "text": (
            "🧱 *Bloco da mensagem inicial*\n\n"
            f"Texto: `{(block.text or '—')[:120]}`\n"
            f"Mídia: {media_info}\n"
            f"Delay: {delay_info}\n"
            f"Auto-delete: {autodel_info}"
        ),
        "keyboard": {
            "inline_keyboard": [
                [
                    {
                        "text": "🔙 Voltar",
                        "callback_data": f"start_template_menu:{template.bot_id}",
                    }
                ]
            ]
        },
    }


async def handle_start_template_text_click(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await StartTemplateBlockRepository.get_block(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_start_block_text",
        {"block_id": block_id, "template_id": block.template_id},
    )

    current_text = f"\n\nTexto atual: `{block.text[:100]}...`" if block.text else ""
    return {
        "text": "💬 *Texto do Bloco*\n\nDigite o texto completo da mensagem."
        + current_text,
        "keyboard": None,
    }


async def handle_start_template_text_input(
    user_id: int, block_id: int, template_id: int, text: str
) -> Dict[str, Any]:
    await StartTemplateBlockRepository.update_block(block_id, text=text)
    ConversationStateManager.clear_state(user_id)

    template = await StartTemplateRepository.get_by_id(template_id)
    if not template:
        return {"text": "❌ Template não encontrado.", "keyboard": None}

    await StartTemplateService.bump_version(template_id)

    result = await handle_start_template_menu(user_id, template.bot_id)
    result["text"] = "✅ Texto atualizado!\n\n" + result["text"]
    return result


async def handle_start_template_media_click(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await StartTemplateBlockRepository.get_block(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_start_block_media",
        {"block_id": block_id, "template_id": block.template_id},
    )

    current_media = (
        f"\n\nMídia atual: {block.media_type}" if block.media_file_id else ""
    )

    return {
        "text": (
            "📎 *Mídia do Bloco*\n\nEnvie uma foto, vídeo, documento ou áudio"
            " para associar ao bloco."
        )
        + current_media,
        "keyboard": None,
    }


async def handle_start_template_media_input(
    user_id: int,
    block_id: int,
    template_id: int,
    media_file_id: str,
    media_type: str,
) -> Dict[str, Any]:
    await StartTemplateBlockRepository.update_block(
        block_id, media_file_id=media_file_id, media_type=media_type
    )
    ConversationStateManager.clear_state(user_id)

    template = await StartTemplateRepository.get_by_id(template_id)
    if not template:
        return {"text": "❌ Template não encontrado.", "keyboard": None}

    await StartTemplateService.bump_version(template_id)

    result = await handle_start_template_menu(user_id, template.bot_id)
    result["text"] = "✅ Mídia atualizada!\n\n" + result["text"]
    return result


async def handle_start_template_effects_click(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await StartTemplateBlockRepository.get_block(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    template = await StartTemplateRepository.get_by_id(block.template_id)
    if not template:
        return {"text": "❌ Template não encontrado.", "keyboard": None}

    delay_text = (
        f"Delay: {block.delay_seconds}s" if block.delay_seconds else "Sem delay"
    )
    autodel_text = (
        f"Auto-delete: {block.auto_delete_seconds}s"
        if block.auto_delete_seconds
        else "Sem auto-delete"
    )

    return {
        "text": (
            "⏱️ *Efeitos do Bloco*\n\n"
            f"{delay_text}\n{autodel_text}\n\nEscolha o que deseja configurar."
        ),
        "keyboard": {
            "inline_keyboard": [
                [
                    {
                        "text": "⏰ Delay",
                        "callback_data": f"start_block_delay:{block.id}",
                    },
                    {
                        "text": "🗑️ Auto-delete",
                        "callback_data": f"start_block_autodel:{block.id}",
                    },
                ],
                [
                    {
                        "text": "🔙 Voltar",
                        "callback_data": f"start_template_menu:{template.bot_id}",
                    }
                ],
            ]
        },
    }


async def handle_start_template_delay_click(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await StartTemplateBlockRepository.get_block(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_start_block_delay",
        {"block_id": block_id, "template_id": block.template_id},
    )

    return {
        "text": (
            "⏰ *Delay do Bloco*\n\nDigite o tempo em segundos (0-300).\n\n"
            f"Valor atual: {block.delay_seconds}s"
        ),
        "keyboard": None,
    }


async def handle_start_template_delay_input(
    user_id: int, block_id: int, template_id: int, delay_text: str
) -> Dict[str, Any]:
    try:
        delay_value = int(delay_text.strip())
        if delay_value < 0 or delay_value > 300:
            raise ValueError
    except ValueError:
        return {
            "text": "❌ Valor inválido. Informe um número entre 0 e 300:",
            "keyboard": None,
        }

    await StartTemplateBlockRepository.update_block(block_id, delay_seconds=delay_value)
    ConversationStateManager.clear_state(user_id)

    template = await StartTemplateRepository.get_by_id(template_id)
    if not template:
        return {"text": "❌ Template não encontrado.", "keyboard": None}

    await StartTemplateService.bump_version(template_id)

    result = await handle_start_template_menu(user_id, template.bot_id)
    result["text"] = f"✅ Delay configurado ({delay_value}s)!\n\n" + result["text"]
    return result


async def handle_start_template_autodel_click(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await StartTemplateBlockRepository.get_block(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_start_block_autodel",
        {"block_id": block_id, "template_id": block.template_id},
    )

    return {
        "text": (
            "🗑️ *Auto-delete*\n\nDigite em quantos segundos a mensagem deve ser apagada (0-86400).\n\n"
            f"Valor atual: {block.auto_delete_seconds}s"
        ),
        "keyboard": None,
    }


async def handle_start_template_autodel_input(
    user_id: int, block_id: int, template_id: int, autodel_text: str
) -> Dict[str, Any]:
    try:
        autodel_value = int(autodel_text.strip())
        if autodel_value < 0 or autodel_value > 86400:
            raise ValueError
    except ValueError:
        return {
            "text": "❌ Valor inválido. Informe um número entre 0 e 86400:",
            "keyboard": None,
        }

    await StartTemplateBlockRepository.update_block(
        block_id, auto_delete_seconds=autodel_value
    )
    ConversationStateManager.clear_state(user_id)

    template = await StartTemplateRepository.get_by_id(template_id)
    if not template:
        return {"text": "❌ Template não encontrado.", "keyboard": None}

    await StartTemplateService.bump_version(template_id)

    result = await handle_start_template_menu(user_id, template.bot_id)
    result["text"] = (
        f"✅ Auto-delete configurado ({autodel_value}s)!\n\n" + result["text"]
    )
    return result
