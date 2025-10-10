"""
Bot Gerenciador - Comandos administrativos
"""

import os

from core.config import settings
from core.security import encrypt
from database.repos import BotRepository
from workers.api_clients import TelegramAPI

WEBHOOK_BASE_URL = os.environ.get("WEBHOOK_BASE_URL", "http://localhost:8000")


async def register_bot(admin_id: int, bot_token: str) -> dict:
    """
    Registra um novo bot no sistema

    Args:
        admin_id: ID do Telegram do administrador
        bot_token: Token do bot fornecido pelo BotFather

    Returns:
        dict com informações do bot registrado
    """
    if not settings.is_user_authorized(admin_id):
        raise PermissionError("Usuário não autorizado")

    # 1. Valida token com a API do Telegram
    telegram_api = TelegramAPI()
    bot_info = await telegram_api.get_me(bot_token)

    # 2. Salva no banco com token criptografado
    bot = await BotRepository.create_bot(
        {
            "admin_id": admin_id,
            "token": encrypt(bot_token),
            "username": bot_info.get("username"),
            "webhook_secret": os.urandom(32).hex(),
        }
    )

    # 3. Configura webhook no Telegram
    webhook_url = f"{WEBHOOK_BASE_URL}/webhook/{bot.id}"
    await telegram_api.set_webhook(
        token=bot_token,
        url=webhook_url,
        secret_token=bot.webhook_secret,
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )

    return {
        "id": bot.id,
        "username": bot.username,
        "webhook_url": webhook_url,
        "status": "active",
    }


async def list_bots(admin_id: int) -> list:
    """Lista todos os bots de um admin"""
    if not settings.is_user_authorized(admin_id):
        raise PermissionError("Usuário não autorizado")

    return await BotRepository.get_bots_by_admin(admin_id)


async def deactivate_bot(admin_id: int, bot_id: int) -> bool:
    """Desativa um bot"""
    if not settings.is_user_authorized(admin_id):
        raise PermissionError("Usuário não autorizado")

    bot = await BotRepository.get_bot_by_id(bot_id)
    if not bot or bot.admin_id != admin_id:
        raise ValueError("Bot não encontrado ou sem permissão")

    return await BotRepository.deactivate_bot(bot_id)
