"""
Handlers para configuração de anti-spam
"""

from typing import Any, Dict

from core.config import settings
from database.repos import AntiSpamConfigRepository
from services.bot_registration import BotRegistrationService
from services.conversation_state import ConversationStateManager


async def handle_antispam_menu_click(user_id: int) -> Dict[str, Any]:
    """Handler quando usuário clica no botão ANTISPAM"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    return await handle_select_bot_for_antispam(user_id, page=1)


async def handle_select_bot_for_antispam(user_id: int, page: int = 1) -> Dict[str, Any]:
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
        buttons.append(
            [{"text": display, "callback_data": f"antispam_select_bot:{bot.id}"}]
        )

    nav_buttons = []
    if page > 1:
        nav_buttons.append(
            {"text": "← Anterior", "callback_data": f"antispam_bots_page:{page-1}"}
        )
    if end_idx < len(bots):
        nav_buttons.append(
            {"text": "Próxima →", "callback_data": f"antispam_bots_page:{page+1}"}
        )

    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([{"text": "🔙 Voltar", "callback_data": "back_to_main"}])

    return {
        "text": f"🛡️ *ANTISPAM*\n\nSelecione um bot para configurar proteções:\n\n(Página {page})",
        "keyboard": {"inline_keyboard": buttons},
    }


async def handle_bot_selected_for_antispam(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Menu de configuração de anti-spam do bot"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    # Busca ou cria configuração
    config = await AntiSpamConfigRepository.get_or_create(bot_id)

    # Monta texto informativo
    text = """🛡️ *ANTISPAM - Configuração*

Use os botões abaixo para alternar cada proteção. Os filtros ativos banem automaticamente quando a condição ocorre.

*Status das Proteções:*"""

    # Adiciona status de cada proteção
    protections = [
        (
            "dot_after_start",
            "'.' após /start",
            "bane se enviar '.' até 60s após /start",
        ),
        ("repetition", "Repetição", "≥ 3 msgs iguais em 30s"),
        ("flood", "Flood", "> 8 msgs em 10s"),
        ("links_mentions", "Links/Menções", "2+ URLs/@ em 60s"),
        ("short_messages", "Msgs curtas", "5 msgs < 3 chars em sequência"),
        ("loop_start", "Loop /start", "3 /starts em 5 min"),
        ("total_limit", "Limite total", f"ban após {config.total_limit_value} msgs"),
    ]

    for attr, name, desc in protections:
        status = "✅" if getattr(config, attr) else "❌"
        text += f"\n• {status} *{name}*"

    # Monta teclado com toggles
    keyboard: dict[str, list] = {"inline_keyboard": []}

    # Proteções principais (2 por linha)
    main_protections = [
        ("dot_after_start", "'.' após /start"),
        ("repetition", "Repetição"),
        ("flood", "Flood"),
        ("links_mentions", "Links/Menções"),
        ("short_messages", "Msgs curtas"),
        ("loop_start", "Loop /start"),
    ]

    for i in range(0, len(main_protections), 2):
        row = []
        for j in range(2):
            if i + j < len(main_protections):
                attr, name = main_protections[i + j]
                status = "✅" if getattr(config, attr) else "❌"
                row.append(
                    {
                        "text": f"{status} {name}",
                        "callback_data": f"antispam_toggle:{bot_id}:{attr}",
                    }
                )
        keyboard["inline_keyboard"].append(row)

    # Limite total (linha separada)
    total_status = "✅" if config.total_limit else "❌"
    keyboard["inline_keyboard"].append(
        [
            {
                "text": f"{total_status} Limite total ({config.total_limit_value} msgs)",
                "callback_data": f"antispam_toggle:{bot_id}:total_limit",
            }
        ]
    )

    # Botão para definir limite
    keyboard["inline_keyboard"].append(
        [
            {
                "text": f"⚙️ Definir Limite (atual: {config.total_limit_value})",
                "callback_data": f"antispam_set_limit:{bot_id}",
            }
        ]
    )

    # Proteções extras (sugestões)
    keyboard["inline_keyboard"].append(
        [{"text": "➕ Proteções Extras", "callback_data": f"antispam_extras:{bot_id}"}]
    )

    # Voltar
    keyboard["inline_keyboard"].append(
        [{"text": "🔙 Voltar", "callback_data": "antispam_menu"}]
    )

    return {"text": text, "keyboard": keyboard}


async def handle_antispam_extras(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Menu de proteções extras/sugestões"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    config = await AntiSpamConfigRepository.get_or_create(bot_id)

    text = """🛡️ *ANTISPAM - Proteções Extras*

Proteções adicionais recomendadas:"""

    extras = [
        ("forward_spam", "Forward Spam", "> 3 forwards em 30s"),
        ("emoji_flood", "Emoji Flood", "> 10 emojis por msg"),
        ("char_repetition", "Repetição Chars", "aaaa, !!!!, etc"),
        ("bot_speed", "Velocidade Bot", "< 1s entre msgs, 5+ vezes"),
        ("media_spam", "Media Spam", "> 5 fotos/vídeos em 30s"),
        ("sticker_spam", "Sticker Spam", "> 5 stickers em 30s"),
        ("contact_spam", "Contact Spam", "> 2 contatos em 60s"),
        ("location_spam", "Location Spam", "> 2 localizações em 60s"),
    ]

    for attr, name, desc in extras:
        status = "✅" if getattr(config, attr) else "❌"
        text += f"\n• {status} *{name}* - {desc}"

    # Teclado com toggles (2 por linha)
    keyboard: dict[str, list] = {"inline_keyboard": []}

    for i in range(0, len(extras), 2):
        row = []
        for j in range(2):
            if i + j < len(extras):
                attr, name, _ = extras[i + j]
                status = "✅" if getattr(config, attr) else "❌"
                row.append(
                    {
                        "text": f"{status} {name}",
                        "callback_data": f"antispam_toggle:{bot_id}:{attr}",
                    }
                )
        keyboard["inline_keyboard"].append(row)

    keyboard["inline_keyboard"].append(
        [{"text": "🔙 Voltar", "callback_data": f"antispam_config:{bot_id}"}]
    )

    return {"text": text, "keyboard": keyboard}


async def handle_antispam_toggle(
    user_id: int, bot_id: int, protection: str
) -> Dict[str, Any]:
    """Alterna status de uma proteção"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    # Toggle proteção
    new_value = await AntiSpamConfigRepository.toggle_protection(bot_id, protection)

    # Invalida cache Redis
    from core.redis_client import redis_client

    redis_client.delete(f"antispam_config:{bot_id}")

    # Retorna ao menu apropriado
    extras = [
        "forward_spam",
        "emoji_flood",
        "char_repetition",
        "bot_speed",
        "media_spam",
        "sticker_spam",
        "contact_spam",
        "location_spam",
    ]

    if protection in extras:
        return await handle_antispam_extras(user_id, bot_id)
    else:
        return await handle_bot_selected_for_antispam(user_id, bot_id)


async def handle_set_limit_click(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Inicia processo de definir limite total"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    ConversationStateManager.set_state(
        user_id, "awaiting_spam_limit", {"bot_id": bot_id}
    )

    return {
        "text": "⚙️ *Definir Limite Total*\n\nDigite o número máximo de mensagens permitidas antes do ban automático.\n\nExemplo: `100`\n\n_Valores aceitos: 10 a 10000_",
        "keyboard": None,
    }


async def handle_spam_limit_input(
    user_id: int, bot_id: int, text: str
) -> Dict[str, Any]:
    """Processa input do limite"""
    try:
        limit = int(text.strip())

        if limit < 10 or limit > 10000:
            return {
                "text": "❌ Valor inválido. Digite um número entre 10 e 10000:",
                "keyboard": None,
            }

        # Atualiza configuração
        await AntiSpamConfigRepository.update_config(bot_id, total_limit_value=limit)

        # Invalida cache
        from core.redis_client import redis_client

        redis_client.delete(f"antispam_config:{bot_id}")

        ConversationStateManager.clear_state(user_id)

        return {
            "text": f"✅ Limite atualizado para {limit} mensagens!\n\nQuando ativado, usuários serão banidos após enviar {limit} mensagens.",
            "keyboard": None,
        }

    except ValueError:
        return {
            "text": "❌ Digite apenas números. Tente novamente:",
            "keyboard": None,
        }
