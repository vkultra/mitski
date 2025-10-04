"""
Handlers genéricos para bots secundários
"""


async def handle_bot_start(bot_id: int, user_id: int) -> str:
    """Handler genérico para /start de bots secundários"""
    return "OK, bot funcional!"


async def handle_bot_help(bot_id: int, user_id: int) -> str:
    """Handler genérico para /help de bots secundários"""
    return """
📚 Comandos disponíveis:

/start - Iniciar bot
/help - Exibir esta mensagem
/status - Ver status do bot

Para mais informações, entre em contato com o administrador.
    """


async def handle_bot_status(bot_id: int, user_id: int) -> str:
    """Handler genérico para /status de bots secundários"""
    return """
✅ Bot Status: Online

O bot está funcionando normalmente.
    """
