"""
Handlers para gerenciamento de fases de IA

Responsável por:
- Criar fase inicial
- Listar fases
- Visualizar fase
- Editar fase
- Deletar fase
- Definir fase inicial
"""

import re
from typing import Any, Dict

from core.config import settings
from services.ai.phase_service import AIPhaseService
from services.conversation_state import ConversationStateManager
from services.files import (
    TxtFileError,
    build_preview,
    download_txt_document,
    make_txt_stream,
)
from workers.api_clients import TelegramAPI


def _phase_filename(phase_name: str, phase_id: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (phase_name or "").lower()).strip("_") or "fase"
    return f"fase_{phase_id}_{slug}.txt"


async def handle_create_initial_phase_click(
    user_id: int, bot_id: int
) -> Dict[str, Any]:
    """Inicia criação de fase inicial (pede apenas o prompt)"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    # Verificar se já existe fase inicial
    existing_initial = await AIPhaseService.get_initial_phase(bot_id)
    if existing_initial:
        return {
            "text": f"⚠️ Já existe uma fase inicial: `{existing_initial.phase_name}`\n\nDelete-a primeiro para criar uma nova.",
            "keyboard": None,
        }

    ConversationStateManager.set_state(
        user_id, "awaiting_initial_phase_prompt", {"bot_id": bot_id}
    )

    return {
        "text": '⭐ *Criar Fase Inicial*\n\nA fase inicial sempre começa quando um novo usuário interage com o bot.\n\nDigite o prompt desta fase:\n\nExemplo: "Você está na fase de boas-vindas. Seja amigável e pergunte como pode ajudar."',
        "keyboard": None,
    }


async def handle_initial_phase_prompt_input(
    user_id: int, bot_id: int, prompt: str
) -> Dict[str, Any]:
    """Salva fase inicial com nome fixo 'Inicial'"""
    try:
        await AIPhaseService.create_phase(
            bot_id=bot_id, name="Inicial", prompt=prompt, trigger=None, is_initial=True
        )
        ConversationStateManager.clear_state(user_id)

        return {
            "text": (
                "✅ Fase inicial criada!\n"
                f"Caracteres do prompt: {len(prompt)}\n\n"
                "Todos os novos usuários começarão nesta fase."
            ),
            "keyboard": None,
        }
    except ValueError as e:
        return {"text": f"❌ Erro: {str(e)}", "keyboard": None}


async def handle_list_phases(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Lista todas as fases do bot"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    phases = await AIPhaseService.list_phases(bot_id)

    if not phases:
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "⭐ Criar Fase Inicial",
                        "callback_data": f"ai_create_initial:{bot_id}",
                    }
                ],
                [
                    {
                        "text": "➕ Criar Fase",
                        "callback_data": f"ai_create_phase:{bot_id}",
                    }
                ],
                [{"text": "🔙 Voltar", "callback_data": f"ai_select_bot:{bot_id}"}],
            ]
        }

        return {
            "text": "📭 Nenhuma fase criada ainda.\n\n⭐ Crie primeiro uma **fase inicial** para novos usuários.\n\n➕ Depois crie fases adicionais com triggers.",
            "keyboard": keyboard,
        }

    buttons = []

    # Separar fase inicial das demais
    initial_phase = next((p for p in phases if p.is_initial), None)
    regular_phases = [p for p in phases if not p.is_initial]

    # Mostrar fase inicial primeiro
    if initial_phase:
        buttons.append(
            [
                {
                    "text": f"⭐ {initial_phase.phase_name} (Inicial)",
                    "callback_data": f"ai_view_phase:{initial_phase.id}",
                }
            ]
        )

    # Mostrar fases regulares
    for phase in regular_phases:
        buttons.append(
            [
                {
                    "text": f"{phase.phase_name} ({phase.phase_trigger})",
                    "callback_data": f"ai_view_phase:{phase.id}",
                }
            ]
        )

    # Botões de ação
    if not initial_phase:
        buttons.append(
            [
                {
                    "text": "⭐ Criar Fase Inicial",
                    "callback_data": f"ai_create_initial:{bot_id}",
                }
            ]
        )

    buttons.append(
        [{"text": "➕ Criar Fase", "callback_data": f"ai_create_phase:{bot_id}"}]
    )
    buttons.append([{"text": "🔙 Voltar", "callback_data": f"ai_select_bot:{bot_id}"}])

    return {
        "text": f"📋 **Fases Criadas** ({len(phases)} total)\n\n{'⭐ Fase inicial configurada' if initial_phase else '⚠️ Sem fase inicial'}",
        "keyboard": {"inline_keyboard": buttons},
    }


async def handle_view_phase(user_id: int, phase_id: int) -> Dict[str, Any]:
    """Visualiza detalhes de uma fase"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    phase = await AIPhaseService.get_phase_by_id(phase_id)

    if not phase:
        return {"text": "❌ Fase não encontrada.", "keyboard": None}

    # Texto descritivo
    prompt = phase.phase_prompt or ""
    preview = build_preview(prompt, max_chars=300)
    preview_safe = preview.replace("`", r"\`")

    if phase.is_initial:
        text = f"⭐ **{phase.phase_name}** (Fase Inicial)\n\n"
        text += f"📝 **Preview:** `{preview_safe}`\n\n"
        text += (
            "Baixe o arquivo .txt para visualizar o prompt completo."
            "\n\nℹ️ Todos os novos usuários começam nesta fase."
        )
    else:
        text = f"📋 **{phase.phase_name}**\n\n"
        text += f"🔑 **Trigger:** `{phase.phase_trigger}`\n\n"
        text += f"📝 **Preview:** `{preview_safe}`\n\n"
        text += (
            f"Quando a IA retornar `{phase.phase_trigger}`, esta fase será ativada. "
            "Baixe o .txt para ler o prompt completo."
        )

    # Botões de ação
    buttons = []

    if not phase.is_initial:
        buttons.append(
            [
                {
                    "text": "⭐ Definir como Inicial",
                    "callback_data": f"ai_set_initial:{phase.id}",
                }
            ]
        )

    buttons.append(
        [
            {
                "text": "✏️ Editar Prompt",
                "callback_data": f"ai_phase_edit:{phase.id}",
            }
        ]
    )
    buttons.append(
        [
            {
                "text": "⬆️ Enviar .txt",
                "callback_data": f"ai_phase_upload:{phase.id}",
            },
            {
                "text": "⬇️ Baixar .txt",
                "callback_data": f"ai_phase_download:{phase.id}",
            },
        ]
    )
    buttons.append(
        [
            {
                "text": "🗑 Excluir Fase",
                "callback_data": f"ai_confirm_delete:{phase.id}",
            }
        ]
    )
    buttons.append(
        [{"text": "🔙 Voltar", "callback_data": f"ai_list_phases:{phase.bot_id}"}]
    )

    return {"text": text, "keyboard": {"inline_keyboard": buttons}}


async def handle_phase_download(user_id: int, phase_id: int) -> Dict[str, Any]:
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    phase = await AIPhaseService.get_phase_by_id(phase_id)

    if not phase:
        return {"text": "❌ Fase não encontrada.", "keyboard": None}

    prompt = phase.phase_prompt or ""

    if not prompt.strip():
        return {"text": "⚠️ Este prompt ainda não foi configurado.", "keyboard": None}

    filename = _phase_filename(phase.phase_name, phase.id)
    stream = make_txt_stream(filename, prompt)

    api = TelegramAPI()
    await api.send_document(
        token=settings.MANAGER_BOT_TOKEN,
        chat_id=user_id,
        document=stream,
        caption=f"📄 Prompt da fase {phase.phase_name}.",
    )

    view = await handle_view_phase(user_id, phase_id)
    view["text"] = (
        "📄 Prompt enviado como .txt. Confira o arquivo acima.\n\n" + view["text"]
    )
    return view


async def handle_set_initial_phase(user_id: int, phase_id: int) -> Dict[str, Any]:
    """Define fase como inicial"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    phase = await AIPhaseService.get_phase_by_id(phase_id)

    if not phase:
        return {"text": "❌ Fase não encontrada.", "keyboard": None}

    success = await AIPhaseService.set_initial_phase(phase.bot_id, phase_id)

    if success:
        return {
            "text": f"✅ Fase `{phase.phase_name}` definida como inicial!\n\nNovos usuários começarão nesta fase.",
            "keyboard": None,
        }
    else:
        return {"text": "❌ Erro ao definir fase inicial.", "keyboard": None}


async def handle_confirm_delete_phase(user_id: int, phase_id: int) -> Dict[str, Any]:
    """Confirmação antes de deletar fase"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    phase = await AIPhaseService.get_phase_by_id(phase_id)

    if not phase:
        return {"text": "❌ Fase não encontrada.", "keyboard": None}

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Sim, excluir",
                    "callback_data": f"ai_delete_phase:{phase_id}",
                }
            ],
            [
                {
                    "text": "❌ Cancelar",
                    "callback_data": f"ai_view_phase:{phase_id}",
                }
            ],
        ]
    }

    return {
        "text": f"⚠️ **Confirmar Exclusão**\n\nTem certeza que deseja excluir a fase `{phase.phase_name}`?\n\n{'⚠️ Esta é a fase inicial! Novos usuários não terão fase inicial.' if phase.is_initial else 'Esta ação não pode ser desfeita.'}",
        "keyboard": keyboard,
    }


async def handle_delete_phase(user_id: int, phase_id: int) -> Dict[str, Any]:
    """Deleta fase"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    phase = await AIPhaseService.get_phase_by_id(phase_id)

    if not phase:
        return {"text": "❌ Fase não encontrada.", "keyboard": None}

    bot_id = phase.bot_id
    success = await AIPhaseService.delete_phase(phase_id)

    if success:
        # Redirecionar para lista de fases
        return await handle_list_phases(user_id, bot_id)
    else:
        return {"text": "❌ Erro ao excluir fase.", "keyboard": None}


async def handle_phase_edit_prompt(user_id: int, phase_id: int) -> Dict[str, Any]:
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    phase = await AIPhaseService.get_phase_by_id(phase_id)
    if not phase:
        return {"text": "❌ Fase não encontrada.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_phase_prompt_update",
        {"phase_id": phase_id},
    )

    return {
        "text": (
            f"✏️ Envie o novo prompt para a fase `{phase.phase_name}`.\n\n"
            "Para textos maiores que 4096 caracteres, prefira enviar um arquivo .txt "
            "com o botão de upload."
        ),
        "keyboard": None,
    }


async def handle_phase_upload_request(user_id: int, phase_id: int) -> Dict[str, Any]:
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    phase = await AIPhaseService.get_phase_by_id(phase_id)
    if not phase:
        return {"text": "❌ Fase não encontrada.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id,
        "awaiting_phase_prompt_file",
        {"phase_id": phase_id},
    )

    return {
        "text": (
            f"📂 Envie o arquivo .txt com o prompt para `{phase.phase_name}`.\n"
            "Tamanho máximo aceito: 64 KB."
        ),
        "keyboard": None,
    }


async def handle_phase_prompt_update_input(
    user_id: int, phase_id: int, prompt: str
) -> Dict[str, Any]:
    return await _persist_phase_prompt_update(user_id, phase_id, prompt)


async def handle_phase_prompt_document_input(
    user_id: int, phase_id: int, document: Dict[str, Any], token: str
) -> Dict[str, Any]:
    try:
        prompt = await download_txt_document(token, document)
    except TxtFileError as exc:
        return {"text": f"❌ {exc}", "keyboard": None}

    return await _persist_phase_prompt_update(user_id, phase_id, prompt)


async def _persist_phase_prompt_update(
    user_id: int, phase_id: int, prompt: str
) -> Dict[str, Any]:
    success = await AIPhaseService.update_phase(phase_id, prompt=prompt)

    if not success:
        return {"text": "❌ Não foi possível atualizar a fase.", "keyboard": None}

    ConversationStateManager.clear_state(user_id)

    char_count = len(prompt)
    view = await handle_view_phase(user_id, phase_id)
    view["text"] = (
        f"✅ Prompt da fase atualizado! ({char_count} caracteres).\n"
        "Preview e opções abaixo.\n\n" + view["text"]
    )
    return view
