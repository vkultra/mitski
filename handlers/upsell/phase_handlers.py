"""
Handlers para configuração de fase do upsell
"""

import re
from typing import Any, Dict

from core.config import settings
from database.repos import UpsellPhaseConfigRepository, UpsellRepository
from services.conversation_state import ConversationStateManager
from services.files import (
    TxtFileError,
    build_preview,
    download_txt_document,
    make_txt_stream,
)
from workers.api_clients import TelegramAPI


def _upsell_phase_filename(upsell_name: str, upsell_id: int) -> str:
    slug = (
        re.sub(r"[^a-z0-9]+", "_", (upsell_name or "").lower()).strip("_") or "upsell"
    )
    return f"upsell_{upsell_id}_fase_{slug}.txt"


async def handle_phase_menu(user_id: int, upsell_id: int) -> Dict[str, Any]:
    """Menu de configuração de fase"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    upsell = await UpsellRepository.get_upsell_by_id(upsell_id)
    if not upsell:
        return {"text": "❌ Upsell não encontrado.", "keyboard": None}

    phase_config = await UpsellPhaseConfigRepository.get_phase_config(upsell_id)

    prompt = phase_config.phase_prompt if phase_config else ""
    preview = build_preview(prompt)
    preview_safe = preview.replace("`", r"\`")
    char_count = len(prompt or "")

    text = (
        f"🎭 **Fase - {upsell.name}**\n\n"
        f"Caracteres salvos: *{char_count}*\n"
        f"Preview: `{preview_safe}`\n\n"
        "Use os botões abaixo para editar. Prompts maiores que 4096 caracteres devem "
        "ser enviados via arquivo .txt para evitar limites do Telegram."
    )

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "✏️ Editar Prompt",
                    "callback_data": f"upsell_phase_edit:{upsell_id}",
                }
            ],
            [
                {
                    "text": "⬆️ Enviar .txt",
                    "callback_data": f"upsell_phase_upload:{upsell_id}",
                },
                {
                    "text": "⬇️ Baixar .txt",
                    "callback_data": f"upsell_phase_download:{upsell_id}",
                },
            ],
            [{"text": "🔙 Voltar", "callback_data": f"upsell_select:{upsell_id}"}],
        ]
    }

    return {"text": text, "keyboard": keyboard}


async def handle_phase_edit_click(user_id: int, upsell_id: int) -> Dict[str, Any]:
    """Solicita prompt da fase"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_upsell_phase_prompt",
        {"upsell_id": upsell_id},
    )

    return {
        "text": '🎭 Digite o prompt da fase:\n\nExemplo: "Você está oferecendo o pacote premium. Seja direto e destaque os benefícios exclusivos."',
        "keyboard": None,
    }


async def handle_phase_prompt_input(
    user_id: int, upsell_id: int, prompt: str
) -> Dict[str, Any]:
    """Salva prompt da fase"""
    return await _persist_upsell_phase_prompt(user_id, upsell_id, prompt)


async def handle_upsell_phase_upload_request(
    user_id: int, upsell_id: int
) -> Dict[str, Any]:
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    upsell = await UpsellRepository.get_upsell_by_id(upsell_id)
    if not upsell:
        return {"text": "❌ Upsell não encontrado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_upsell_phase_prompt_file",
        {"upsell_id": upsell_id},
    )

    return {
        "text": (
            f"📂 Envie o arquivo .txt com o prompt da fase `{upsell.name}`.\n"
            "Tamanho máximo aceito: 64 KB."
        ),
        "keyboard": None,
    }


async def handle_upsell_phase_prompt_document_input(
    user_id: int, upsell_id: int, document: Dict[str, Any], token: str
) -> Dict[str, Any]:
    try:
        prompt = await download_txt_document(token, document)
    except TxtFileError as exc:
        return {"text": f"❌ {exc}", "keyboard": None}

    return await _persist_upsell_phase_prompt(user_id, upsell_id, prompt)


async def handle_upsell_phase_download(user_id: int, upsell_id: int) -> Dict[str, Any]:
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    upsell = await UpsellRepository.get_upsell_by_id(upsell_id)
    if not upsell:
        return {"text": "❌ Upsell não encontrado.", "keyboard": None}

    phase_config = await UpsellPhaseConfigRepository.get_phase_config(upsell_id)
    prompt = phase_config.phase_prompt if phase_config else ""

    if not prompt.strip():
        return {
            "text": "⚠️ Nenhum prompt configurado para este upsell.",
            "keyboard": None,
        }

    filename = _upsell_phase_filename(upsell.name, upsell.id)
    stream = make_txt_stream(filename, prompt)

    api = TelegramAPI()
    await api.send_document(
        token=settings.MANAGER_BOT_TOKEN,
        chat_id=user_id,
        document=stream,
        caption=f"📄 Prompt da fase do upsell {upsell.name}.",
    )

    menu = await handle_phase_menu(user_id, upsell_id)
    menu["text"] = (
        "📄 Prompt enviado como .txt. Confira o arquivo acima.\n\n" + menu["text"]
    )
    return menu


async def _persist_upsell_phase_prompt(
    user_id: int, upsell_id: int, prompt: str
) -> Dict[str, Any]:
    await UpsellPhaseConfigRepository.create_or_update_phase(upsell_id, prompt)
    ConversationStateManager.clear_state(user_id)

    char_count = len(prompt)

    menu = await handle_phase_menu(user_id, upsell_id)
    menu["text"] = (
        f"✅ Prompt da fase atualizado! ({char_count} caracteres).\n"
        "Preview e opções abaixo.\n\n" + menu["text"]
    )
    return menu
