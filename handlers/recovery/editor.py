"""Handlers do editor de blocos para recuperações."""

from __future__ import annotations

from typing import Any, Dict, List

from core.config import settings
from core.recovery import decode_schedule, format_schedule_definition
from database.recovery import (
    RecoveryBlockRepository,
    RecoveryCampaignRepository,
    RecoveryStepRepository,
)
from services.conversation_state import ConversationStateManager
from services.recovery.sender import RecoveryMessageSender

from .callbacks import build_callback


def _ensure_admin(user_id: int) -> bool:
    return user_id in settings.allowed_admin_ids_list


async def _bump_version_by_step(step_id: int) -> None:
    step = await RecoveryStepRepository.get_step(step_id)
    if step:
        await RecoveryCampaignRepository.increment_version(step.campaign_id)


async def handle_recovery_step_view(user_id: int, step_id: int) -> Dict[str, Any]:
    if not _ensure_admin(user_id):
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    step = await RecoveryStepRepository.get_step(step_id)
    if not step:
        return {"text": "❌ Recuperação não encontrada.", "keyboard": None}

    blocks = await RecoveryBlockRepository.list_blocks(step_id)
    campaign = await RecoveryCampaignRepository.get_by_id(step.campaign_id)
    bot_id = campaign.bot_id if campaign else None
    schedule = decode_schedule(step.schedule_type, step.schedule_value)
    schedule_text = format_schedule_definition(schedule)

    inline_keyboard: List[List[Dict[str, str]]] = []
    for idx, block in enumerate(blocks, start=1):
        inline_keyboard.append(
            [
                {
                    "text": f"{idx}️⃣",
                    "callback_data": build_callback("step_view", step_id=block.step_id),
                },
                {
                    "text": "Efeitos",
                    "callback_data": build_callback("block_effects", block_id=block.id),
                },
                {
                    "text": "Mídia",
                    "callback_data": build_callback("block_media", block_id=block.id),
                },
                {
                    "text": "Texto/Legenda",
                    "callback_data": build_callback("block_text", block_id=block.id),
                },
                {
                    "text": "❌",
                    "callback_data": build_callback("block_delete", block_id=block.id),
                },
            ]
        )

    inline_keyboard.append(
        [
            {
                "text": "➕ Adicionar Bloco",
                "callback_data": build_callback("block_add", step_id=step_id),
            }
        ]
    )
    inline_keyboard.append(
        [
            {
                "text": "👀 Pré-visualizar",
                "callback_data": build_callback("step_preview", step_id=step_id),
            }
        ]
    )
    back_cb = (
        build_callback("select_bot", bot_id=bot_id)
        if bot_id
        else build_callback("menu")
    )
    inline_keyboard.append([{"text": "🔙 Voltar", "callback_data": back_cb}])

    header = (
        f"🧩 *Blocos da Recuperação #{step.order_index}*\n"
        f"Horário: `{schedule_text}`"
    )
    return {"text": header, "keyboard": {"inline_keyboard": inline_keyboard}}


async def handle_recovery_block_add(user_id: int, step_id: int) -> Dict[str, Any]:
    if not _ensure_admin(user_id):
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    await RecoveryBlockRepository.create_block(step_id)
    await _bump_version_by_step(step_id)
    return await handle_recovery_step_view(user_id, step_id)


async def handle_recovery_block_delete(user_id: int, block_id: int) -> Dict[str, Any]:
    if not _ensure_admin(user_id):
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    step_id = await RecoveryBlockRepository.delete_block(block_id)
    if not step_id:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}
    await _bump_version_by_step(step_id)
    return await handle_recovery_step_view(user_id, step_id)


async def handle_recovery_block_text_click(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    if not _ensure_admin(user_id):
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await RecoveryBlockRepository.get_block(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_recovery_block_text",
        {"block_id": block_id, "step_id": block.step_id},
    )

    current = f"\n\nAtual: `{block.text[:100]}`" if block.text else ""
    return {
        "text": "💬 *Texto/Legenda do Bloco*\n\nDigite a mensagem."
        "\n\nSuporta Markdown."
        f"{current}",
        "keyboard": None,
    }


async def handle_recovery_block_text_input(
    user_id: int, block_id: int, step_id: int, text: str
) -> Dict[str, Any]:
    await RecoveryBlockRepository.update_block(block_id, text=text)
    await _bump_version_by_step(step_id)
    ConversationStateManager.clear_state(user_id)
    return await handle_recovery_step_view(user_id, step_id)


async def handle_recovery_block_media_click(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    if not _ensure_admin(user_id):
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await RecoveryBlockRepository.get_block(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_recovery_block_media",
        {"block_id": block_id, "step_id": block.step_id},
    )

    current = f"\n\nMídia atual: {block.media_type}" if block.media_file_id else ""
    return {
        "text": "📎 *Mídia do Bloco*\n\nEnvie foto, vídeo, áudio, gif ou documento."
        f"{current}",
        "keyboard": None,
    }


async def handle_recovery_block_media_input(
    user_id: int,
    block_id: int,
    step_id: int,
    media_file_id: str,
    media_type: str,
) -> Dict[str, Any]:
    await RecoveryBlockRepository.update_block(
        block_id, media_file_id=media_file_id, media_type=media_type
    )
    await _bump_version_by_step(step_id)
    ConversationStateManager.clear_state(user_id)
    return await handle_recovery_step_view(user_id, step_id)


async def handle_recovery_block_effects_click(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    if not _ensure_admin(user_id):
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await RecoveryBlockRepository.get_block(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "⏰ Delay",
                    "callback_data": build_callback("block_delay", block_id=block_id),
                },
                {
                    "text": "🗑️ Auto-deletar",
                    "callback_data": build_callback("block_autodel", block_id=block_id),
                },
            ],
            [
                {
                    "text": "🔙 Voltar",
                    "callback_data": build_callback("step_view", step_id=block.step_id),
                }
            ],
        ]
    }

    text = (
        "⏱️ *Efeitos*\n\n"
        f"Delay: {block.delay_seconds}s\n"
        f"Auto-delete: {block.auto_delete_seconds}s"
    )
    return {"text": text, "keyboard": keyboard}


async def handle_recovery_block_delay_click(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    if not _ensure_admin(user_id):
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await RecoveryBlockRepository.get_block(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_recovery_block_delay",
        {"block_id": block_id, "step_id": block.step_id},
    )

    return {
        "text": f"⏰ *Delay*\n\nEnvie segundos (0-300).\nAtual: {block.delay_seconds}s",
        "keyboard": None,
    }


async def handle_recovery_block_delay_input(
    user_id: int, block_id: int, step_id: int, delay_text: str
) -> Dict[str, Any]:
    try:
        delay = int(delay_text)
        if delay < 0 or delay > 300:
            raise ValueError
    except ValueError:
        return {"text": "❌ Informe um número entre 0 e 300.", "keyboard": None}

    await RecoveryBlockRepository.update_block(block_id, delay_seconds=delay)
    await _bump_version_by_step(step_id)
    ConversationStateManager.clear_state(user_id)
    return await handle_recovery_block_effects_click(user_id, block_id)


async def handle_recovery_block_autodel_click(
    user_id: int, block_id: int
) -> Dict[str, Any]:
    if not _ensure_admin(user_id):
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    block = await RecoveryBlockRepository.get_block(block_id)
    if not block:
        return {"text": "❌ Bloco não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_recovery_block_autodel",
        {"block_id": block_id, "step_id": block.step_id},
    )

    return {
        "text": f"🗑️ *Auto-excluir*\n\nEnvie segundos (0-3600).\nAtual: {block.auto_delete_seconds}s",
        "keyboard": None,
    }


async def handle_recovery_block_autodel_input(
    user_id: int, block_id: int, step_id: int, autodel_text: str
) -> Dict[str, Any]:
    try:
        seconds = int(autodel_text)
        if seconds < 0 or seconds > 3600:
            raise ValueError
    except ValueError:
        return {"text": "❌ Informe um número entre 0 e 3600.", "keyboard": None}

    await RecoveryBlockRepository.update_block(block_id, auto_delete_seconds=seconds)
    await _bump_version_by_step(step_id)
    ConversationStateManager.clear_state(user_id)
    return await handle_recovery_block_effects_click(user_id, block_id)


async def handle_recovery_step_preview(user_id: int, step_id: int) -> Dict[str, Any]:
    if not _ensure_admin(user_id):
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    step = await RecoveryStepRepository.get_step(step_id)
    if not step:
        return {"text": "❌ Recuperação não encontrada.", "keyboard": None}

    blocks = await RecoveryBlockRepository.list_blocks(step_id)
    if not blocks:
        return {"text": "❌ Nenhum bloco configurado.", "keyboard": None}

    sender = RecoveryMessageSender(settings.MANAGER_BOT_TOKEN)
    await sender.send_blocks(blocks, chat_id=user_id)

    # Reenvia o menu completo abaixo da pré-visualização para continuar edição
    menu_data = await handle_recovery_step_view(user_id, step_id)

    from workers.api_clients import TelegramAPI

    api = TelegramAPI()
    await api.send_message(
        token=settings.MANAGER_BOT_TOKEN,
        chat_id=user_id,
        text=menu_data["text"],
        parse_mode="Markdown",
        reply_markup=menu_data["keyboard"],
    )

    return {
        "text": "✅ Pré-visualização enviada! O menu foi reenviado abaixo.",
        "keyboard": None,
    }
