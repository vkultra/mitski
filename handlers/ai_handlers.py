"""
Handlers para configuração de IA
"""

import re
from typing import Any, Dict

from core.config import settings
from services.ai.config import AIConfigService
from services.bot_registration import BotRegistrationService
from services.conversation_state import ConversationStateManager
from services.files import (
    TxtFileError,
    build_preview,
    download_txt_document,
    make_txt_stream,
)
from workers.api_clients import TelegramAPI


def _slugify(value: str) -> str:
    """Create a filesystem-friendly slug for filenames."""
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "prompt"


async def handle_ai_menu_click(user_id: int) -> Dict[str, Any]:
    """Handler quando usuário clica no botão IA"""
    return await handle_select_bot_for_ai(user_id, page=1)


async def handle_select_bot_for_ai(user_id: int, page: int = 1) -> Dict[str, Any]:
    """Lista bots para seleção (3 por página)"""
    bots = await BotRegistrationService.list_bots(user_id)

    if not bots:
        return {
            "text": "📭 Você não tem bots registrados.\n\nAdicione um bot primeiro.",
            "keyboard": None,
        }

    per_page = 3
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    bots_page = bots[start_idx:end_idx]

    buttons = []
    for bot in bots_page:
        display = (
            f"{bot.display_name} (@{bot.username})"
            if bot.display_name
            else f"@{bot.username}"
        )
        buttons.append([{"text": display, "callback_data": f"ai_select_bot:{bot.id}"}])

    nav_buttons = []
    if page > 1:
        nav_buttons.append(
            {"text": "← Anterior", "callback_data": f"ai_bots_page:{page-1}"}
        )
    if end_idx < len(bots):
        nav_buttons.append(
            {"text": "Próxima →", "callback_data": f"ai_bots_page:{page+1}"}
        )

    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([{"text": "🔙 Voltar", "callback_data": "back_to_main"}])

    return {
        "text": f"🤖 Selecione um bot para configurar a IA:\n\n(Página {page})",
        "keyboard": {"inline_keyboard": buttons},
    }


async def handle_bot_selected_for_ai(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Menu de configuração de IA do bot"""
    is_authorized = user_id in settings.allowed_admin_ids_list
    config = await AIConfigService.get_or_create_config(bot_id)

    if not is_authorized:
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "⚡ Ações",
                        "callback_data": f"action_menu:{bot_id}",
                    }
                ],
                [{"text": "🔙 Voltar", "callback_data": "ai_menu"}],
            ]
        }

        return {
            "text": (
                "⚙️ *Configurações disponíveis*\n\n"
                "Você pode ajustar as respostas de áudio do bot usando o menu de Ações."
            ),
            "keyboard": keyboard,
        }

    model_label = (
        "🧠 Reasoning" if config.model_type == "reasoning" else "⚡ Non-Reasoning"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "📝 Comportamento Geral",
                    "callback_data": f"ai_general_prompt:{bot_id}",
                }
            ],
            [
                {
                    "text": "📋 Gerenciar Fases",
                    "callback_data": f"ai_list_phases:{bot_id}",
                }
            ],
            [
                {
                    "text": "💰 Ofertas",
                    "callback_data": f"offer_menu:{bot_id}",
                },
                {
                    "text": "⚡ Ações",
                    "callback_data": f"action_menu:{bot_id}",
                },
                {
                    "text": "💎 Upsell",
                    "callback_data": f"upsell_menu:{bot_id}",
                },
            ],
            [
                {
                    "text": f"🔄 Modelo: {model_label}",
                    "callback_data": f"ai_toggle_model:{bot_id}",
                }
            ],
            [{"text": "🔙 Voltar", "callback_data": "ai_menu"}],
        ]
    }

    return {
        "text": f"⚙️ Configuração de IA\n\nModelo: {model_label}\nStatus: {'✅ Ativo' if config.is_enabled else '❌ Inativo'}",
        "keyboard": keyboard,
    }


async def handle_general_prompt_click(user_id: int, bot_id: int) -> Dict[str, Any]:
    return await handle_general_prompt_menu(user_id, bot_id)


async def handle_general_prompt_menu(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Solicita prompt de comportamento geral"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    config = await AIConfigService.get_or_create_config(bot_id)
    prompt = config.general_prompt or ""
    preview = build_preview(prompt)
    preview_safe = preview.replace("`", r"\`")
    char_count = len(prompt)

    return {
        "text": (
            "📝 *Comportamento Geral da IA*\n\n"
            f"Caracteres salvos: *{char_count}*\n"
            f"Preview: `{preview_safe}`\n\n"
            "Se o prompt ultrapassar 4096 caracteres, envie um arquivo .txt usando o botão "
            "de upload abaixo para evitar limites do Telegram."
        ),
        "keyboard": {
            "inline_keyboard": [
                [
                    {
                        "text": "✏️ Editar digitando",
                        "callback_data": f"ai_general_edit:{bot_id}",
                    }
                ],
                [
                    {
                        "text": "⬆️ Enviar .txt",
                        "callback_data": f"ai_general_upload:{bot_id}",
                    },
                    {
                        "text": "⬇️ Baixar .txt",
                        "callback_data": f"ai_general_download:{bot_id}",
                    },
                ],
                [{"text": "🔙 Voltar", "callback_data": f"ai_select_bot:{bot_id}"}],
            ]
        },
    }


async def handle_general_prompt_download(user_id: int, bot_id: int) -> Dict[str, Any]:
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    config = await AIConfigService.get_or_create_config(bot_id)
    prompt = config.general_prompt or ""

    if not prompt.strip():
        return {
            "text": "⚠️ Nenhum prompt geral configurado ainda.",
            "keyboard": None,
        }

    filename = f"prompt_geral_{bot_id}.txt"
    stream = make_txt_stream(filename, prompt)

    api = TelegramAPI()
    await api.send_document(
        token=settings.MANAGER_BOT_TOKEN,
        chat_id=user_id,
        document=stream,
        caption="📄 Prompt geral exportado.",
    )

    menu = await handle_general_prompt_menu(user_id, bot_id)
    menu["text"] = (
        "📄 Prompt enviado como .txt. Confira o arquivo acima.\n\n" + menu["text"]
    )
    return menu


async def handle_general_prompt_edit(user_id: int, bot_id: int) -> Dict[str, Any]:
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_general_prompt",
        {"bot_id": bot_id},
    )

    return {
        "text": (
            "📝 Envie o novo comportamento geral digitando a mensagem aqui mesmo.\n\n"
            "Se o texto for maior que 4096 caracteres, use o botão de upload de .txt "
            "para evitar erros do Telegram."
        ),
        "keyboard": None,
    }


async def handle_general_prompt_upload_request(
    user_id: int, bot_id: int
) -> Dict[str, Any]:
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_general_prompt_file",
        {"bot_id": bot_id},
    )

    return {
        "text": (
            "📂 Envie o arquivo .txt com o prompt completo como documento.\n"
            "Tamanho máximo aceito: 64 KB."
        ),
        "keyboard": None,
    }


async def handle_general_prompt_document_input(
    user_id: int, bot_id: int, document: Dict[str, Any], token: str
) -> Dict[str, Any]:
    try:
        prompt = await download_txt_document(token, document)
    except TxtFileError as exc:
        return {"text": f"❌ {exc}", "keyboard": None}

    return await _persist_general_prompt(user_id, bot_id, prompt)


async def _persist_general_prompt(
    user_id: int, bot_id: int, prompt: str
) -> Dict[str, Any]:
    await AIConfigService.update_general_prompt(bot_id, prompt)
    ConversationStateManager.clear_state(user_id)

    char_count = len(prompt)
    menu = await handle_general_prompt_menu(user_id, bot_id)
    menu["text"] = (
        f"✅ Comportamento geral atualizado! ({char_count} caracteres).\n"
        "Preview e opções abaixo.\n\n" + menu["text"]
    )
    return menu


async def handle_general_prompt_input(
    user_id: int, bot_id: int, prompt: str
) -> Dict[str, Any]:
    """Salva prompt geral"""
    return await _persist_general_prompt(user_id, bot_id, prompt)


async def handle_create_phase_click(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Inicia criação de fase"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id, "awaiting_phase_name", {"bot_id": bot_id}
    )

    return {
        "text": "➕ *Criar Nova Fase*\n\nDigite o nome da fase:\n\nExemplo: `Negociação`, `Fechamento`, `Suporte`",
        "keyboard": None,
    }


async def handle_phase_name_input(
    user_id: int, bot_id: int, name: str
) -> Dict[str, Any]:
    """Processa nome da fase"""
    name = name.strip()

    if len(name) < 3:
        return {
            "text": "❌ Nome muito curto. Use pelo menos 3 caracteres.\n\nTente novamente:",
            "keyboard": None,
        }

    ConversationStateManager.set_state(
        user_id, "awaiting_phase_trigger", {"bot_id": bot_id, "name": name}
    )

    return {
        "text": f"✅ Nome: `{name}`\n\nAgora digite um termo único (gatilho):\n\n⚠️ Preferir termos não comuns:\n• `fcf4`\n• `eko3`\n• `zx9p`\n\nQuando a IA retornar este termo, a fase mudará automaticamente.",
        "keyboard": None,
    }


async def handle_phase_trigger_input(
    user_id: int, bot_id: int, name: str, trigger: str
) -> Dict[str, Any]:
    """Processa trigger da fase"""
    trigger = trigger.strip()

    if len(trigger) < 3:
        return {
            "text": "❌ Trigger muito curto. Use pelo menos 3 caracteres.\n\nTente novamente:",
            "keyboard": None,
        }

    from database.repos import AIPhaseRepository

    existing = await AIPhaseRepository.get_phase_by_trigger(bot_id, trigger)

    if existing:
        return {
            "text": f"❌ O trigger `{trigger}` já existe.\n\nEscolha outro termo:",
            "keyboard": None,
        }

    ConversationStateManager.set_state(
        user_id,
        "awaiting_phase_prompt",
        {"bot_id": bot_id, "name": name, "trigger": trigger},
    )

    return {
        "text": (
            f"✅ Nome: `{name}`\n✅ Trigger: `{trigger}`\n\n"
            "Agora digite o prompt desta fase ou envie um arquivo `.txt` como documento.\n\n"
            'Exemplo: "Agora você está na fase de fechamento. Seja direto ao oferecer o produto."'
        ),
        "keyboard": None,
    }


async def handle_phase_prompt_input(
    user_id: int, bot_id: int, name: str, trigger: str, prompt: str
) -> Dict[str, Any]:
    """Salva prompt da fase"""
    await AIConfigService.create_phase(bot_id, name, prompt, trigger, is_initial=False)
    ConversationStateManager.clear_state(user_id)

    char_count = len(prompt)

    return {
        "text": (
            f"✅ Fase `{name}` criada! ({char_count} caracteres).\n"
            f"Quando a IA retornar `{trigger}`, esta fase será ativada."
        ),
        "keyboard": {
            "inline_keyboard": [
                [{"text": "🔙 Voltar", "callback_data": f"ai_list_phases:{bot_id}"}],
                [{"text": "🏠 Menu IA", "callback_data": f"ai_select_bot:{bot_id}"}],
            ]
        },
    }


async def handle_toggle_model(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Alterna entre reasoning e non-reasoning"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    new_type = await AIConfigService.toggle_model(bot_id)

    label = "🧠 Reasoning" if new_type == "reasoning" else "⚡ Non-Reasoning"

    return {
        "text": f"✅ Modelo alterado para: {label}\n\nAs próximas mensagens usarão este modelo.\nO histórico foi mantido.",
        "keyboard": None,
    }
