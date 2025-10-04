"""
Handlers para comandos do bot gerenciador
"""
from typing import Dict, Any, Optional
from bot_manager import register_bot, list_bots, deactivate_bot
from core.config import settings
from core.telemetry import logger


async def handle_start(user_id: int) -> Dict[str, Any]:
    """Handler para comando /start - retorna mensagem e teclado"""
    if user_id not in settings.allowed_admin_ids_list:
        return {
            "text": "⛔ Acesso negado. Este bot é restrito a administradores.",
            "keyboard": None
        }

    keyboard = {
        "inline_keyboard": [
            [{"text": "➕ Adicionar Bot", "callback_data": "add_bot"}],
            [
                {"text": "🗑 Desativar", "callback_data": "deactivate_menu"},
                {"text": "📋 Listar Bots", "callback_data": "list_bots"}
            ]
        ]
    }

    return {
        "text": "👋 Bem-vindo ao Telegram Multi-Bot Manager!\n\nEscolha uma opção abaixo:",
        "keyboard": keyboard
    }


async def handle_register(user_id: int, bot_token: str) -> str:
    """Handler para comando /register"""
    if user_id not in settings.allowed_admin_ids_list:
        return "⛔ Acesso negado."

    try:
        bot = await register_bot(user_id, bot_token)
        logger.info("Bot registered successfully", extra={
            "user_id": user_id,
            "bot_id": bot['id'],
            "username": bot['username']
        })
        return f"""
✅ Bot registrado com sucesso!

📋 Detalhes:
- ID: {bot['id']}
- Username: @{bot['username']}
- Webhook: {bot['webhook_url']}
- Status: {bot['status']}

O bot está pronto para uso!
        """
    except Exception as e:
        logger.error("Bot registration failed", extra={
            "user_id": user_id,
            "error": str(e)
        })
        return f"❌ Erro ao registrar bot: {str(e)}"


async def handle_list(user_id: int) -> str:
    """Handler para comando /list"""
    if user_id not in settings.allowed_admin_ids_list:
        return "⛔ Acesso negado."

    try:
        bots = await list_bots(user_id)
        if not bots:
            return "📭 Você ainda não tem bots registrados.\n\nUse /register <token> para adicionar um bot."

        response = "🤖 Seus bots:\n\n"
        for bot in bots:
            status = "✅ Ativo" if bot.is_active else "❌ Inativo"
            response += f"• @{bot.username} (ID: {bot.id}) - {status}\n"

        return response
    except Exception as e:
        logger.error("List bots failed", extra={
            "user_id": user_id,
            "error": str(e)
        })
        return f"❌ Erro ao listar bots: {str(e)}"


async def handle_deactivate(user_id: int, bot_id: int) -> str:
    """Handler para comando /deactivate"""
    if user_id not in settings.allowed_admin_ids_list:
        return "⛔ Acesso negado."

    try:
        success = await deactivate_bot(user_id, bot_id)
        if success:
            logger.info("Bot deactivated", extra={
                "user_id": user_id,
                "bot_id": bot_id
            })
            return f"✅ Bot {bot_id} desativado com sucesso!"
        else:
            return f"❌ Bot {bot_id} não encontrado ou sem permissão."
    except Exception as e:
        logger.error("Deactivate bot failed", extra={
            "user_id": user_id,
            "bot_id": bot_id,
            "error": str(e)
        })
        return f"❌ Erro ao desativar bot: {str(e)}"


async def handle_callback_add_bot(user_id: int) -> Dict[str, Any]:
    """Handler para callback de adicionar bot"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    return {
        "text": "🤖 Para adicionar um novo bot, envie o token no formato:\n\n`TOKEN_DO_BOT`\n\nExemplo:\n`1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`",
        "keyboard": None
    }


async def handle_callback_list_bots(user_id: int) -> Dict[str, Any]:
    """Handler para callback de listar bots"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    try:
        bots = await list_bots(user_id)
        if not bots:
            return {
                "text": "📭 Você ainda não tem bots registrados.\n\nUse o botão ➕ Adicionar Bot para começar.",
                "keyboard": None
            }

        response = "🤖 Seus bots:\n\n"
        for bot in bots:
            status = "✅ Ativo" if bot.is_active else "❌ Inativo"
            response += f"• @{bot.username} (ID: {bot.id}) - {status}\n"

        return {"text": response, "keyboard": None}
    except Exception as e:
        logger.error("List bots failed", extra={
            "user_id": user_id,
            "error": str(e)
        })
        return {"text": f"❌ Erro ao listar bots: {str(e)}", "keyboard": None}


async def handle_callback_deactivate_menu(user_id: int) -> Dict[str, Any]:
    """Handler para callback do menu de desativação"""
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    try:
        bots = await list_bots(user_id)
        if not bots:
            return {
                "text": "📭 Você não tem bots para desativar.",
                "keyboard": None
            }

        # Criar botões inline para cada bot
        buttons = []
        for bot in bots:
            if bot.is_active:
                buttons.append([{
                    "text": f"🗑 @{bot.username}",
                    "callback_data": f"deactivate:{bot.id}"
                }])

        if not buttons:
            return {
                "text": "📭 Você não tem bots ativos para desativar.",
                "keyboard": None
            }

        keyboard = {"inline_keyboard": buttons}
        return {
            "text": "🗑 Escolha um bot para desativar:",
            "keyboard": keyboard
        }
    except Exception as e:
        logger.error("Deactivate menu failed", extra={
            "user_id": user_id,
            "error": str(e)
        })
        return {"text": f"❌ Erro ao carregar menu: {str(e)}", "keyboard": None}
