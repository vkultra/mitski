"""
Handlers de menu principal de Upsells
"""

from typing import Any, Dict

from core.config import settings
from database.repos import UpsellRepository
from services.upsell import UpsellService


async def handle_upsell_menu(
    user_id: int, bot_id: int, page: int = 1
) -> Dict[str, Any]:
    """Menu principal de upsells com listagem e paginação"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    # Buscar todos os upsells do bot
    all_upsells = await UpsellRepository.get_upsells_by_bot(bot_id)
    # Ordenar por order
    all_upsells = sorted(all_upsells, key=lambda u: u.order)

    # Paginação: 5 upsells por página
    ITEMS_PER_PAGE = 5
    total_upsells = len(all_upsells)
    total_pages = (
        (total_upsells + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        if total_upsells > 0
        else 1
    )

    # Ajustar página se for inválida
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages

    # Calcular índices de slice
    start_idx = (page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_upsells = all_upsells[start_idx:end_idx]

    # Botões de ação no topo (apenas adicionar se não for pré-salvo)
    action_buttons = [
        [
            {"text": "➕ Adicionar Upsell", "callback_data": f"upsell_add:{bot_id}"},
            {
                "text": "🗑️ Excluir Upsell",
                "callback_data": f"upsell_delete_menu:{bot_id}",
            },
        ]
    ]

    # Montar botões dos upsells da página atual
    upsell_buttons = []
    for upsell in page_upsells:
        # Verificar completude
        is_complete = await UpsellService.is_upsell_complete(upsell.id)
        status_emoji = "✅" if is_complete else "⚠️"

        # Nome do botão
        value_text = f" ({upsell.value})" if upsell.value else ""
        upsell_name = f"{status_emoji} #{upsell.order} - {upsell.name}{value_text}"

        upsell_buttons.append(
            [
                {
                    "text": upsell_name,
                    "callback_data": f"upsell_select:{upsell.id}",
                }
            ]
        )

    # Botões de navegação
    nav_buttons = []
    if total_pages > 1:
        nav_row = []
        if page > 1:
            nav_row.append(
                {
                    "text": "⬅️ Anterior",
                    "callback_data": f"upsell_menu_page:{bot_id}:{page-1}",
                }
            )
        nav_row.append({"text": f"📄 {page}/{total_pages}", "callback_data": "noop"})
        if page < total_pages:
            nav_row.append(
                {
                    "text": "➡️ Próximo",
                    "callback_data": f"upsell_menu_page:{bot_id}:{page+1}",
                }
            )
        nav_buttons.append(nav_row)

    # Botão voltar
    back_buttons = [[{"text": "🔙 Voltar", "callback_data": f"ai_select_bot:{bot_id}"}]]

    # Montar keyboard
    keyboard_buttons = action_buttons + upsell_buttons + nav_buttons + back_buttons

    text = "💎 **Gerenciar Upsells**\n\n"
    if total_upsells == 0:
        text += "Nenhum upsell criado ainda.\n\n"
    else:
        text += f"Total: {total_upsells} upsell(s)\n"
        text += f"Página {page} de {total_pages}\n\n"

    text += "✅ = Completo (pronto para ativar)\n⚠️ = Incompleto (faltam campos)"

    return {"text": text, "keyboard": {"inline_keyboard": keyboard_buttons}}


async def handle_upsell_menu_page(
    user_id: int, bot_id: int, page: int
) -> Dict[str, Any]:
    """Handler de paginação"""
    return await handle_upsell_menu(user_id, bot_id, page)


async def handle_upsell_select(user_id: int, upsell_id: int) -> Dict[str, Any]:
    """Menu de edição de um upsell específico"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    upsell = await UpsellRepository.get_upsell_by_id(upsell_id)
    if not upsell:
        return {"text": "❌ Upsell não encontrado.", "keyboard": None}

    # Verificar completude
    is_complete = await UpsellService.is_upsell_complete(upsell_id)
    status = "✅ Completo" if is_complete else "⚠️ Incompleto"

    # Verificar quantidade de blocos
    from database.repos import (
        UpsellAnnouncementBlockRepository,
        UpsellDeliverableBlockRepository,
        UpsellPhaseConfigRepository,
    )

    announcement_count = await UpsellAnnouncementBlockRepository.count_blocks(upsell_id)
    deliverable_count = await UpsellDeliverableBlockRepository.count_blocks(upsell_id)
    phase_config = await UpsellPhaseConfigRepository.get_phase_config(upsell_id)

    # Verificar preenchimento de cada campo
    has_value = bool(upsell.value)
    has_announcement = announcement_count > 0
    has_deliverable = deliverable_count > 0
    has_phase = bool(phase_config and phase_config.phase_prompt)
    has_trigger = bool(upsell.upsell_trigger)

    text = f"💎 **{upsell.name}**\n\n"
    text += f"Status: {status}\n"
    text += f"Ordem: #{upsell.order}\n"
    text += f"Valor: {upsell.value or 'Não definido'}\n"
    text += f"Anúncio: {announcement_count} bloco(s)\n"
    text += f"Entrega: {deliverable_count} bloco(s)\n"

    keyboard_buttons = []

    # Linha 1: Termo (só se for pré-salvo)
    if upsell.is_pre_saved:
        termo_emoji = "✅" if has_trigger else "⚠️"
        keyboard_buttons.append(
            [
                {
                    "text": f"{termo_emoji} 🎯 Termo",
                    "callback_data": f"upsell_trigger:{upsell_id}",
                }
            ]
        )

    # Linha 2: Anúncio | Entrega
    announcement_emoji = "✅" if has_announcement else "⚠️"
    deliverable_emoji = "✅" if has_deliverable else "⚠️"
    keyboard_buttons.append(
        [
            {
                "text": f"{announcement_emoji} 📢 Anúncio",
                "callback_data": f"upsell_announcement:{upsell_id}",
            },
            {
                "text": f"{deliverable_emoji} 📦 Entrega",
                "callback_data": f"upsell_deliverable:{upsell_id}",
            },
        ]
    )

    # Linha 3: Fase | Valor
    phase_emoji = "✅" if has_phase else "⚠️"
    value_emoji = "✅" if has_value else "⚠️"
    keyboard_buttons.append(
        [
            {
                "text": f"{phase_emoji} 🎭 Fase",
                "callback_data": f"upsell_phase:{upsell_id}",
            },
            {
                "text": f"{value_emoji} 💰 Valor",
                "callback_data": f"upsell_value:{upsell_id}",
            },
        ]
    )

    # Linha 4: Agendar (só se não for pré-salvo)
    if not upsell.is_pre_saved:
        keyboard_buttons.append(
            [
                {
                    "text": "✅ 📅 Agendar",
                    "callback_data": f"upsell_schedule:{upsell_id}",
                }
            ]
        )

    # Linha final: Voltar
    keyboard_buttons.append(
        [{"text": "🔙 Voltar", "callback_data": f"upsell_menu:{upsell.bot_id}"}]
    )

    return {"text": text, "keyboard": {"inline_keyboard": keyboard_buttons}}


async def handle_add_upsell(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Adiciona novo upsell"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    # Buscar todos os upsells para determinar próxima ordem
    existing = await UpsellRepository.get_upsells_by_bot(bot_id)
    next_order = len(existing) + 1

    # Criar novo upsell
    new_upsell = await UpsellRepository.create_upsell(
        bot_id=bot_id,
        name=f"Upsell #{next_order}",
        order=next_order,
        is_pre_saved=False,
    )

    # Criar agendamento padrão (3 dias)
    from database.repos import UpsellScheduleRepository

    await UpsellScheduleRepository.create_schedule(
        upsell_id=new_upsell.id,
        is_immediate=False,
        days_after=3,
        hours=0,
        minutes=0,
    )

    # Criar fase vazia
    from database.repos import UpsellPhaseConfigRepository

    await UpsellPhaseConfigRepository.create_or_update_phase(new_upsell.id, "")

    text = (
        f"✅ Upsell #{next_order} criado!\n\nConfigure os blocos e campos necessários."
    )

    keyboard = {
        "inline_keyboard": [
            [{"text": "✏️ Editar", "callback_data": f"upsell_select:{new_upsell.id}"}],
            [{"text": "🔙 Voltar", "callback_data": f"upsell_menu:{bot_id}"}],
        ]
    }

    return {"text": text, "keyboard": keyboard}


async def handle_delete_upsell_menu(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Menu de seleção para exclusão"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    # Buscar upsells (exceto o pré-salvo #1)
    all_upsells = await UpsellRepository.get_upsells_by_bot(bot_id)
    deletable = [u for u in all_upsells if not u.is_pre_saved]

    if not deletable:
        return {
            "text": "❌ Não há upsells para excluir.\n\n(O upsell #1 não pode ser excluído)",
            "keyboard": {
                "inline_keyboard": [
                    [{"text": "🔙 Voltar", "callback_data": f"upsell_menu:{bot_id}"}]
                ]
            },
        }

    keyboard_buttons = []
    for upsell in sorted(deletable, key=lambda u: u.order):
        value_text = f" ({upsell.value})" if upsell.value else ""
        keyboard_buttons.append(
            [
                {
                    "text": f"🗑️ #{upsell.order} - {upsell.name}{value_text}",
                    "callback_data": f"upsell_delete_confirm:{upsell.id}",
                }
            ]
        )

    keyboard_buttons.append(
        [{"text": "🔙 Cancelar", "callback_data": f"upsell_menu:{bot_id}"}]
    )

    return {
        "text": "🗑️ Selecione o upsell para excluir:",
        "keyboard": {"inline_keyboard": keyboard_buttons},
    }


async def handle_delete_upsell_confirm(user_id: int, upsell_id: int) -> Dict[str, Any]:
    """Confirma e executa exclusão"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    upsell = await UpsellRepository.get_upsell_by_id(upsell_id)
    if not upsell:
        return {"text": "❌ Upsell não encontrado.", "keyboard": None}

    # Não permitir excluir upsell #1
    if upsell.is_pre_saved:
        return {
            "text": "❌ O upsell #1 não pode ser excluído.",
            "keyboard": {
                "inline_keyboard": [
                    [
                        {
                            "text": "🔙 Voltar",
                            "callback_data": f"upsell_menu:{upsell.bot_id}",
                        }
                    ]
                ]
            },
        }

    bot_id = upsell.bot_id

    # Excluir upsell (CASCADE deleta blocos, fase, schedule, etc.)
    await UpsellRepository.delete_upsell(upsell_id)

    return {
        "text": f"✅ Upsell '{upsell.name}' excluído com sucesso!",
        "keyboard": {
            "inline_keyboard": [
                [{"text": "🔙 Voltar", "callback_data": f"upsell_menu:{bot_id}"}]
            ]
        },
    }
