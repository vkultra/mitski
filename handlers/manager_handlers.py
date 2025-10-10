"""
Handlers para comandos do bot gerenciador
"""

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional

from core.config import settings
from core.telemetry import logger
from database.credits_repos import CreditWalletRepository
from handlers.recovery.callbacks import build_callback
from services.bot_registration import BotRegistrationService
from services.conversation_state import ConversationStateManager
from services.credits.analytics import message_token_stats, sum_ledger_amount
from services.credits.credit_service import is_unlimited_admin
from services.stats.formatters import format_brl
from services.stats.service import StatsService


def _escape_mdv2(text: str) -> str:
    """Escapes Telegram MarkdownV2 special chars (keep it minimal and local)."""
    if not text:
        return ""
    specials = r"_[]()~`>#+-=|{}.!*"
    out = []
    for ch in text:
        if ch in specials:
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


def _load_ascii_block() -> list[str]:
    """Load ASCII header from inicialmenu.txt; fallback to embedded lines.

    Only the top ASCII art (including the line with v1.0) is used.
    """
    # Try to locate repo root relative to this file
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    path = os.path.join(root, "inicialmenu.txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f.readlines()]
        # Skip leading blanks
        start = 0
        while start < len(lines) and not lines[start].strip():
            start += 1
        # Collect until a blank line after ASCII block
        block: list[str] = []
        for ln in lines[start:]:
            if not ln.strip():
                break
            block.append(ln)
        # Ensure we only keep up to the line containing v1.0 (inclusive) if present
        for idx, ln in enumerate(block):
            if "v1.0" in ln:
                return block[: idx + 1]
        return block
    except Exception:
        # Fallback: embedded copy (kept short and exact)
        return [
            "▗▖ ▗▖▗▄▗▄▄▄▗▄▄▄▗▄▄▄▖▗▄▖",
            "▐▌ ▐▐▌ ▐▌█   █   █ ▐▌ ▐▌",
            "▐▛▀▜▐▌ ▐▌█   █   █ ▐▛▀▜▌",
            "▐▌ ▐▝▚▄▞▘█   █ ▗▄█▄▐▌ ▐▌ v1.0",
        ]


def _load_footer_quote() -> str:
    """Load the final paragraph from inicialmenu.txt (quoted in output)."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    path = os.path.join(root, "inicialmenu.txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f.readlines()]
        # Take the last non-empty line as footer
        for ln in reversed(lines):
            if ln.strip():
                return ln.strip()
        return "Navegue usando os botões abaixo."
    except Exception:
        return (
            "Navegue usando os botões abaixo. Pensou em uma organização melhor para os menus "
            "ou novas funções ou está perdido ou rolou algum BUG? Sim? Para qualquer uma dessas "
            "coisas me chame imediatamente no PV."
        )


def _today_bounds() -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_today = start_today + timedelta(days=1)
    return start_today, end_today


def _build_start_message(user_id: int) -> tuple[str, str]:
    """Builds the /start message with MarkdownV2 quoting and user metrics."""
    # Admin unlimited flag and wallet balance
    unlimited = is_unlimited_admin(user_id)
    balance_cents = CreditWalletRepository.get_balance_cents_sync(user_id)
    balance_text = "♾️ Admin (ilimitado)" if unlimited else format_brl(balance_cents)

    # Credits usage today (consistent with Credits menu)
    start_today, end_today = _today_bounds()
    messages_today, tokens_today = message_token_stats(user_id, start_today, end_today)
    today_spent_cents = sum_ledger_amount(
        user_id, "debit", start_today, end_today, None
    )

    # If unlimited admin, display zero in "Uso Hoje" as requested
    if unlimited:
        tokens_today = 0
        today_spent_cents = 0

    tokens_display = f"{tokens_today:,}".replace(",", ".")

    # Sales today (consistent with Estatísticas menu)
    svc = StatsService(user_id)
    summary = svc.load_summary(svc.build_window(day=date.today()))
    sales_count = int(getattr(summary.totals, "sales_count", 0) or 0)
    gross_cents = int(getattr(summary.totals, "gross_cents", 0) or 0)

    # Compose message parts with MarkdownV2 escaping
    ascii_lines = _load_ascii_block()
    ascii_quote = "\n".join(["> " + _escape_mdv2(line) for line in ascii_lines])

    sep = _escape_mdv2("➖➖➖➖➖➖➖➖➖")

    lines = [
        ascii_quote,
        "",
        sep,
        _escape_mdv2(f"🔴 Créditos Atuais: {balance_text}"),
        _escape_mdv2(
            f"💰 Vendas Totais (hoje): {sales_count} | {format_brl(gross_cents)}"
        ),
        _escape_mdv2(f"✉️ Mensagens Hoje: {messages_today}"),
        _escape_mdv2(
            f"🧮 Uso Hoje: {tokens_display} tokens | {format_brl(today_spent_cents)}"
        ),
        "",
        "> " + _escape_mdv2(_load_footer_quote()),
    ]

    text = "\n".join(lines)
    return text, "MarkdownV2"


async def handle_start(user_id: int) -> Dict[str, Any]:
    """Handler para comando /start - retorna mensagem e teclado"""
    ConversationStateManager.clear_state(user_id)

    notifications_row = [
        [{"text": "🔔 Notificações", "callback_data": "notifications_menu"}]
    ]

    start_text, parse_mode = _build_start_message(user_id)

    if user_id not in settings.allowed_admin_ids_list:
        keyboard = {
            "inline_keyboard": notifications_row
            + [[{"text": "📈 Estatísticas", "callback_data": "stats_menu"}]]
            + [[{"text": "🧭 Rastreio", "callback_data": "tracking_menu"}]]
            + [[{"text": "🤖 IA", "callback_data": "ai_menu"}]]
            + [[{"text": "💳 Créditos", "callback_data": "credits_menu"}]],
        }
        return {"text": start_text, "keyboard": keyboard, "parse_mode": parse_mode}

    keyboard = {
        "inline_keyboard": [
            [{"text": "➕ Adicionar Perfil", "callback_data": "add_bot"}],
            [
                {"text": "🧠 Controle", "callback_data": "ai_menu"},
                {"text": "📈 Estatísticas", "callback_data": "stats_menu"},
                {"text": "💳 Créditos", "callback_data": "credits_menu"},
            ],
            [
                {"text": "⏸️ Pausar", "callback_data": "pause_menu"},
                {"text": "🧭 Rastreio", "callback_data": "tracking_menu"},
            ],
            [
                {"text": "🔔 Notificações", "callback_data": "notifications_menu"},
                {"text": "🏦 Gateway", "callback_data": "gateway_menu"},
            ],
            [
                {
                    "text": "🔁 Recuperação",
                    "callback_data": build_callback("menu", page=1),
                },
                {"text": "🛡️ ANTISPAM", "callback_data": "antispam_menu"},
            ],
            [
                {"text": "👥 Grupo", "callback_data": "group_menu"},
                {"text": "🗑 Desativar", "callback_data": "deactivate_menu"},
            ],
        ]
    }

    return {"text": start_text, "keyboard": keyboard, "parse_mode": parse_mode}


async def handle_text_input(user_id: int, text: str) -> Optional[Dict[str, Any]]:
    """
    Handler para processar entrada de texto baseado em estado conversacional

    Args:
        user_id: ID do usuário no Telegram
        text: Texto enviado pelo usuário

    Returns:
        Dict com resposta ou None se não há estado
    """
    state_data = ConversationStateManager.get_state(user_id)

    if not state_data:
        if user_id not in settings.allowed_admin_ids_list:
            return None
        return None

    state = state_data.get("state")
    data = state_data.get("data", {})

    if state and state.startswith("notifications:"):
        from handlers.notifications.manager_menu import handle_notifications_text_input

        return await handle_notifications_text_input(user_id, text, state_data)

    if state == "awaiting_audio_default_reply":
        from handlers.ai.audio_menu_handlers import handle_audio_menu
        from services.audio import AudioPreferenceError, AudioPreferencesService

        bot_id = data.get("bot_id")
        try:
            AudioPreferencesService.set_default_reply(user_id, text)
            ConversationStateManager.clear_state(user_id)
        except AudioPreferenceError as exc:
            ConversationStateManager.clear_state(user_id)
            return {"text": f"❌ {str(exc)}", "keyboard": None}

        if bot_id:
            response = await handle_audio_menu(
                user_id, bot_id, highlight="✅ Resposta padrão atualizada!"
            )
            return response

        return {"text": "✅ Resposta padrão atualizada!", "keyboard": None}

    if state and state.startswith("tracking:"):
        from handlers.tracking.menu import handle_tracking_text_input

        return await handle_tracking_text_input(user_id, text, state_data)

    if user_id not in settings.allowed_admin_ids_list:
        return None

    # Estado: aguardando nome do bot
    if state == "awaiting_bot_name":
        bot_name = text.strip()

        if len(bot_name) < 3:
            return {
                "text": "❌ Nome muito curto. Por favor, digite um nome com pelo menos 3 caracteres:",
                "keyboard": None,
            }

        # Salva nome e pede token
        ConversationStateManager.set_state(
            user_id, "awaiting_bot_token", {"bot_name": bot_name}
        )

        return {
            "text": f"✅ Nome definido: *{bot_name}*\n\n🔑 Agora envie o token do bot:\n\nExemplo:\n`1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`",
            "keyboard": None,
        }

    # Estado: aguardando token do bot
    elif state == "awaiting_bot_token":
        bot_token = text.strip()
        bot_name = data.get("bot_name", "Sem nome")

        # Valida formato básico do token
        if ":" not in bot_token or len(bot_token) < 30:
            return {
                "text": "❌ Token inválido. O token deve ter o formato:\n`1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`\n\nTente novamente:",
                "keyboard": None,
            }

        try:
            # Registra bot
            bot = await BotRegistrationService.register_bot(
                admin_id=user_id, display_name=bot_name, bot_token=bot_token
            )

            # Limpa estado
            ConversationStateManager.clear_state(user_id)

            logger.info(
                "Bot registered via conversation flow",
                extra={
                    "user_id": user_id,
                    "bot_id": bot["id"],
                    "display_name": bot["display_name"],
                },
            )

            return {
                "text": f"""
✅ *Bot {bot['display_name']} adicionado com sucesso e está online!*

📋 Detalhes:
• Nome: {bot['display_name']}
• Username: @{bot['username']}
• ID: {bot['id']}
• Status: ✅ Online

O bot está pronto para uso!
                """,
                "keyboard": None,
            }

        except ValueError as e:
            ConversationStateManager.clear_state(user_id)
            return {"text": f"❌ Erro ao registrar bot: {str(e)}", "keyboard": None}
        except Exception as e:
            ConversationStateManager.clear_state(user_id)
            logger.error(
                "Bot registration failed in conversation",
                extra={"user_id": user_id, "error": str(e)},
            )
            return {"text": f"❌ Erro inesperado: {str(e)}", "keyboard": None}

    return None


async def handle_list(user_id: int) -> str:
    """Handler para comando /list"""
    if user_id not in settings.allowed_admin_ids_list:
        return "⛔ Acesso negado."

    try:
        bots = await BotRegistrationService.list_bots(user_id)
        if not bots:
            return "📭 Você ainda não tem bots registrados.\n\nUse o botão ➕ Adicionar Bot para começar."

        response = "🤖 Seus bots:\n\n"
        for bot in bots:
            status = "✅ Ativo" if bot.is_active else "❌ Inativo"
            display = (
                f"{bot.display_name} (@{bot.username})"
                if bot.display_name
                else f"@{bot.username}"
            )
            response += f"• {display} (ID: {bot.id}) - {status}\n"

        return response
    except Exception as e:
        logger.error("List bots failed", extra={"user_id": user_id, "error": str(e)})
        return f"❌ Erro ao listar bots: {str(e)}"


async def handle_deactivate(user_id: int, bot_id: int) -> str:
    """Handler para comando /deactivate"""
    if user_id not in settings.allowed_admin_ids_list:
        return "⛔ Acesso negado."

    try:
        success = await BotRegistrationService.deactivate_bot(user_id, bot_id)
        if success:
            return f"✅ Bot {bot_id} desativado com sucesso!"
        else:
            return f"❌ Bot {bot_id} não encontrado."
    except ValueError as e:
        return f"❌ {str(e)}"
    except Exception as e:
        logger.error(
            "Deactivate bot failed",
            extra={"user_id": user_id, "bot_id": bot_id, "error": str(e)},
        )
        return f"❌ Erro ao desativar bot: {str(e)}"


async def handle_callback_add_bot(user_id: int) -> Dict[str, Any]:
    """Handler para callback de adicionar bot - inicia fluxo conversacional"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    # Inicia estado conversacional
    ConversationStateManager.set_state(user_id, "awaiting_bot_name")

    return {
        "text": "🤖 *Adicionar Novo Bot*\n\nPrimeiro, digite um nome para este bot:\n\nExemplo: Bot de Vendas, Suporte, etc.",
        "keyboard": None,
    }


async def handle_callback_list_bots(user_id: int) -> Dict[str, Any]:
    """Handler para callback de listar bots"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    try:
        bots = await BotRegistrationService.list_bots(user_id)
        if not bots:
            return {
                "text": "📭 Você ainda não tem bots registrados.\n\nUse o botão ➕ Adicionar Bot para começar.",
                "keyboard": None,
            }

        response = "🤖 Seus bots:\n\n"
        for bot in bots:
            status = "✅ Ativo" if bot.is_active else "❌ Inativo"
            display = (
                f"{bot.display_name} (@{bot.username})"
                if bot.display_name
                else f"@{bot.username}"
            )
            response += f"• {display} (ID: {bot.id}) - {status}\n"

        return {"text": response, "keyboard": None}
    except Exception as e:
        logger.error("List bots failed", extra={"user_id": user_id, "error": str(e)})
        return {"text": f"❌ Erro ao listar bots: {str(e)}", "keyboard": None}


async def handle_callback_deactivate_menu(user_id: int) -> Dict[str, Any]:
    """Handler para callback do menu de desativação"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    try:
        bots = await BotRegistrationService.list_bots(user_id)
        if not bots:
            return {"text": "📭 Você não tem bots para gerenciar.", "keyboard": None}

        buttons = []
        for bot in bots:
            display = (
                f"{bot.display_name} (@{bot.username})"
                if bot.display_name
                else f"@{bot.username}"
            )

            if bot.is_active:
                left_button = {
                    "text": f"⏸️ {display}",
                    "callback_data": f"deactivate:{bot.id}",
                }
            else:
                left_button = {
                    "text": f"✅ {display}",
                    "callback_data": "noop",
                }

            buttons.append(
                [
                    left_button,
                    {
                        "text": "🗑 Excluir",
                        "callback_data": f"delete_confirm:{bot.id}",
                    },
                ]
            )

        buttons.append([{"text": "🔙 Voltar", "callback_data": "back_to_main"}])

        keyboard = {"inline_keyboard": buttons}
        return {
            "text": "🗑 *Desativar ou excluir bots*\n\nEscolha o bot desejado:",
            "keyboard": keyboard,
            "parse_mode": "Markdown",
        }
    except Exception as e:
        logger.error(
            "Deactivate menu failed", extra={"user_id": user_id, "error": str(e)}
        )
        return {"text": f"❌ Erro ao carregar menu: {str(e)}", "keyboard": None}


async def handle_callback_delete_confirm(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Confirmação antes de excluir definitivamente um bot."""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    try:
        bots = await BotRegistrationService.list_bots(user_id)
        bot = next((b for b in bots if b.id == bot_id), None)
        if not bot:
            return {
                "text": "❌ Bot não encontrado.",
                "keyboard": {
                    "inline_keyboard": [
                        [{"text": "🔙 Voltar", "callback_data": "deactivate_menu"}]
                    ]
                },
            }

        display = (
            f"{bot.display_name} (@{bot.username})"
            if bot.display_name
            else f"@{bot.username}"
        )

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "❌ Cancelar", "callback_data": "deactivate_menu"},
                    {"text": "🗑 Excluir", "callback_data": f"delete_bot:{bot_id}"},
                ]
            ]
        }

        text = (
            "⚠️ Excluir bot\n\n"
            f"Tem certeza que deseja remover {display}?\n"
            "Todos os dados associados (histórico, ofertas, rastreios, etc.) serão apagados."
        )
        return {"text": text, "keyboard": keyboard}
    except Exception as e:
        logger.error(
            "Delete confirm failed",
            extra={"user_id": user_id, "bot_id": bot_id, "error": str(e)},
        )
        return {"text": f"❌ Erro ao carregar confirmação: {str(e)}", "keyboard": None}


async def handle_callback_delete_bot(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Exclui definitivamente um bot e dados relacionados."""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    try:
        success = await BotRegistrationService.delete_bot(user_id, bot_id)
        if success:
            response = await handle_callback_deactivate_menu(user_id)
            response["text"] = "🗑 Bot excluído com sucesso!\n\n" + response.get(
                "text", "Selecione outro bot."
            )
            return response

        return {
            "text": "❌ Bot não encontrado ou já removido.",
            "keyboard": {
                "inline_keyboard": [
                    [{"text": "🔙 Voltar", "callback_data": "deactivate_menu"}]
                ]
            },
        }
    except ValueError as exc:
        return {
            "text": f"❌ {str(exc)}",
            "keyboard": {
                "inline_keyboard": [
                    [{"text": "🔙 Voltar", "callback_data": "deactivate_menu"}]
                ]
            },
        }
    except Exception as exc:  # pragma: no cover - proteção extra
        logger.error(
            "Delete bot failed",
            extra={"user_id": user_id, "bot_id": bot_id, "error": str(exc)},
        )
        return {
            "text": "❌ Erro inesperado ao excluir bot. Tente novamente.",
            "keyboard": {
                "inline_keyboard": [
                    [{"text": "🔙 Voltar", "callback_data": "deactivate_menu"}]
                ]
            },
        }


async def handle_pause_menu(user_id: int) -> Dict[str, Any]:
    """Menu para pausar/despausar bots"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    try:
        bots = await BotRegistrationService.list_bots(user_id)
        if not bots:
            return {"text": "📭 Você não tem bots registrados.", "keyboard": None}

        buttons = []
        for bot in bots:
            display = (
                f"{bot.display_name} (@{bot.username})"
                if bot.display_name
                else f"@{bot.username}"
            )

            # Emoji e callback dependem do status
            if bot.is_active:
                status_emoji = "▶️"
                callback = f"pause_confirm:{bot.id}"
            else:
                status_emoji = "⏸️"
                callback = f"unpause_confirm:{bot.id}"

            buttons.append(
                [{"text": f"{status_emoji} {display}", "callback_data": callback}]
            )

        buttons.append([{"text": "🔙 Voltar", "callback_data": "back_to_main"}])

        return {
            "text": "⏸️ *Pausar/Despausar Bots*\n\n▶️ = Ativo (clique para pausar)\n⏸️ = Pausado (clique para despausar)\n\nSelecione um bot:",
            "keyboard": {"inline_keyboard": buttons},
        }
    except Exception as e:
        logger.error("Pause menu failed", extra={"user_id": user_id, "error": str(e)})
        return {"text": f"❌ Erro ao carregar menu: {str(e)}", "keyboard": None}


async def handle_pause_confirm(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Confirmação para pausar bot"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    try:
        bots = await BotRegistrationService.list_bots(user_id)
        bot = next((b for b in bots if b.id == bot_id), None)

        if not bot:
            return {"text": "❌ Bot não encontrado.", "keyboard": None}

        display = (
            f"{bot.display_name} (@{bot.username})"
            if bot.display_name
            else f"@{bot.username}"
        )

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Sim, pausar", "callback_data": f"pause:{bot_id}"},
                    {"text": "❌ Cancelar", "callback_data": "pause_menu"},
                ]
            ]
        }

        return {
            "text": f"⚠️ *Confirmar Pausa*\n\nDeseja pausar o bot `{display}`?\n\n"
            f"O bot parará de responder mensagens até ser despausado.",
            "keyboard": keyboard,
        }
    except Exception as e:
        logger.error(
            "Pause confirm failed", extra={"user_id": user_id, "error": str(e)}
        )
        return {"text": f"❌ Erro: {str(e)}", "keyboard": None}


async def handle_unpause_confirm(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Confirmação para despausar bot"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    try:
        bots = await BotRegistrationService.list_bots(user_id)
        bot = next((b for b in bots if b.id == bot_id), None)

        if not bot:
            return {"text": "❌ Bot não encontrado.", "keyboard": None}

        display = (
            f"{bot.display_name} (@{bot.username})"
            if bot.display_name
            else f"@{bot.username}"
        )

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Sim, despausar", "callback_data": f"unpause:{bot_id}"},
                    {"text": "❌ Cancelar", "callback_data": "pause_menu"},
                ]
            ]
        }

        return {
            "text": f"✅ *Confirmar Despausa*\n\nDeseja despausar o bot `{display}`?\n\n"
            f"O bot voltará a responder mensagens normalmente.",
            "keyboard": keyboard,
        }
    except Exception as e:
        logger.error(
            "Unpause confirm failed", extra={"user_id": user_id, "error": str(e)}
        )
        return {"text": f"❌ Erro: {str(e)}", "keyboard": None}


async def handle_pause_bot(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Executa pausa do bot"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    try:
        success = await BotRegistrationService.deactivate_bot(user_id, bot_id)
        if success:
            return {
                "text": "⏸️ Bot pausado com sucesso!\n\nO bot não responderá mais mensagens até ser despausado.",
                "keyboard": None,
            }
        else:
            return {"text": "❌ Bot não encontrado.", "keyboard": None}
    except Exception as e:
        logger.error("Pause bot failed", extra={"user_id": user_id, "error": str(e)})
        return {"text": f"❌ Erro ao pausar bot: {str(e)}", "keyboard": None}


async def handle_unpause_bot(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Executa despausa do bot"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    try:
        success = await BotRegistrationService.activate_bot(user_id, bot_id)
        if success:
            return {
                "text": "▶️ Bot despausado com sucesso!\n\nO bot voltou a responder mensagens normalmente.",
                "keyboard": None,
            }
        else:
            return {"text": "❌ Bot não encontrado.", "keyboard": None}
    except Exception as e:
        logger.error("Unpause bot failed", extra={"user_id": user_id, "error": str(e)})
        return {"text": f"❌ Erro ao despausar bot: {str(e)}", "keyboard": None}
