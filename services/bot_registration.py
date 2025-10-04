"""
Bot Registration Service
Serviço para registro e validação de bots secundários
"""

import os
from typing import Any, Dict

from core.security import encrypt
from core.telemetry import logger
from database.repos import BotRepository
from workers.api_clients import TelegramAPI

WEBHOOK_BASE_URL = os.environ.get("WEBHOOK_BASE_URL", "http://localhost:8000")


class BotRegistrationService:
    """Serviço de registro de bots"""

    @staticmethod
    async def validate_token(bot_token: str) -> Dict[str, Any]:
        """
        Valida token do bot com API do Telegram

        Args:
            bot_token: Token do bot fornecido pelo BotFather

        Returns:
            Dict com informações do bot (id, username, first_name)

        Raises:
            ValueError: Se token for inválido
        """
        try:
            telegram_api = TelegramAPI()
            bot_info = await telegram_api.get_me(bot_token)

            if not bot_info or "id" not in bot_info:
                raise ValueError("Token inválido ou bot não encontrado")

            logger.info(
                "Bot token validated",
                extra={
                    "bot_id": bot_info.get("id"),
                    "username": bot_info.get("username"),
                },
            )

            return bot_info

        except Exception as e:
            logger.error("Bot token validation failed", extra={"error": str(e)})
            raise ValueError(f"Token inválido: {str(e)}")

    @staticmethod
    async def register_bot(
        admin_id: int, display_name: str, bot_token: str
    ) -> Dict[str, Any]:
        """
        Registra novo bot no sistema

        Args:
            admin_id: ID do Telegram do administrador
            display_name: Nome customizado para o bot
            bot_token: Token do bot fornecido pelo BotFather

        Returns:
            Dict com informações do bot registrado

        Raises:
            ValueError: Se registro falhar
        """
        try:
            # 1. Valida token
            bot_info = await BotRegistrationService.validate_token(bot_token)

            # 2. Verifica se bot já existe
            existing_bot = await BotRepository.get_bot_by_username(
                bot_info.get("username")
            )
            if existing_bot:
                raise ValueError(f"Bot @{bot_info.get('username')} já está registrado")

            # 3. Cria webhook secret
            webhook_secret = os.urandom(32).hex()

            # 4. Salva no banco
            bot = await BotRepository.create_bot(
                {
                    "admin_id": admin_id,
                    "token": encrypt(bot_token),
                    "username": bot_info.get("username"),
                    "display_name": display_name,
                    "webhook_secret": webhook_secret,
                    "is_active": True,
                }
            )

            # 5. Configura webhook no Telegram
            telegram_api = TelegramAPI()
            webhook_url = f"{WEBHOOK_BASE_URL}/webhook/{bot.id}"

            await telegram_api.set_webhook(
                token=bot_token,
                url=webhook_url,
                secret_token=webhook_secret,
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=True,
            )

            logger.info(
                "Bot registered successfully",
                extra={
                    "bot_id": bot.id,
                    "display_name": display_name,
                    "username": bot.username,
                    "admin_id": admin_id,
                },
            )

            return {
                "id": bot.id,
                "display_name": bot.display_name,
                "username": bot.username,
                "webhook_url": webhook_url,
                "status": "active",
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(
                "Bot registration failed",
                extra={
                    "admin_id": admin_id,
                    "display_name": display_name,
                    "error": str(e),
                },
            )
            raise ValueError(f"Erro ao registrar bot: {str(e)}")

    @staticmethod
    async def list_bots(admin_id: int) -> list:
        """
        Lista todos os bots de um administrador

        Args:
            admin_id: ID do Telegram do administrador

        Returns:
            Lista de bots do administrador
        """
        return await BotRepository.get_bots_by_admin(admin_id)

    @staticmethod
    async def deactivate_bot(admin_id: int, bot_id: int) -> bool:
        """
        Desativa um bot

        Args:
            admin_id: ID do Telegram do administrador
            bot_id: ID do bot a desativar

        Returns:
            True se desativou com sucesso

        Raises:
            ValueError: Se bot não pertence ao admin
        """
        bot = await BotRepository.get_bot_by_id(bot_id)

        if not bot:
            raise ValueError("Bot não encontrado")

        if bot.admin_id != admin_id:
            raise ValueError("Você não tem permissão para desativar este bot")

        success = await BotRepository.deactivate_bot(bot_id)

        if success:
            logger.info(
                "Bot deactivated", extra={"bot_id": bot_id, "admin_id": admin_id}
            )

        return success
