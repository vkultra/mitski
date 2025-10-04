"""
Handlers para comandos do bot gerenciador
"""

from typing import Any, Dict, Optional

from core.config import settings
from core.telemetry import logger
from services.bot_registration import BotRegistrationService
from services.conversation_state import ConversationStateManager


async def handle_start(user_id: int) -> Dict[str, Any]:
    """Handler para comando /start - retorna mensagem e teclado"""
    if user_id not in settings.allowed_admin_ids_list:
        return {
            "text": "⛔ Acesso negado. Este bot é restrito a administradores.",
            "keyboard": None,
        }

    keyboard = {
        "inline_keyboard": [
            [{"text": "➕ Adicionar Bot", "callback_data": "add_bot"}],
            [
                {"text": "🤖 IA", "callback_data": "ai_menu"},
                {"text": "💳 Gateway", "callback_data": "gateway_menu"},
            ],
            [
                {"text": "🗑 Desativar", "callback_data": "deactivate_menu"},
                {"text": "📋 Listar Bots", "callback_data": "list_bots"},
            ],
        ]
    }

    return {
        "text": "👋 Bem-vindo ao Telegram Multi-Bot Manager!\n\nEscolha uma opção abaixo:",
        "keyboard": keyboard,
    }


async def handle_text_input(user_id: int, text: str) -> Optional[Dict[str, Any]]:
    """
    Handler para processar entrada de texto baseado em estado conversacional

    Args:
        user_id: ID do usuário no Telegram
        text: Texto enviado pelo usuário

    Returns:
        Dict com resposta ou None se não há estado
    """
    if user_id not in settings.allowed_admin_ids_list:
        return None

    # Recupera estado conversacional
    state_data = ConversationStateManager.get_state(user_id)

    if not state_data:
        return None

    state = state_data.get("state")
    data = state_data.get("data", {})

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
            return {"text": "📭 Você não tem bots para desativar.", "keyboard": None}

        # Criar botões inline para cada bot
        buttons = []
        for bot in bots:
            if bot.is_active:
                display = (
                    f"{bot.display_name} (@{bot.username})"
                    if bot.display_name
                    else f"@{bot.username}"
                )
                buttons.append(
                    [{"text": f"🗑 {display}", "callback_data": f"deactivate:{bot.id}"}]
                )

        if not buttons:
            return {
                "text": "📭 Você não tem bots ativos para desativar.",
                "keyboard": None,
            }

        keyboard = {"inline_keyboard": buttons}
        return {"text": "🗑 Escolha um bot para desativar:", "keyboard": keyboard}
    except Exception as e:
        logger.error(
            "Deactivate menu failed", extra={"user_id": user_id, "error": str(e)}
        )
        return {"text": f"❌ Erro ao carregar menu: {str(e)}", "keyboard": None}
