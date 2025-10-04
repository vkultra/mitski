"""
Serviço de gerenciamento de gateway de pagamento
"""

from typing import Optional

from core.security import decrypt, encrypt
from core.telemetry import logger
from database.repos import (
    BotGatewayConfigRepository,
    BotRepository,
    GatewayConfigRepository,
)

from .pushinpay_client import PushinPayClient


class GatewayService:
    """Serviço para gerenciar configurações de gateway"""

    @staticmethod
    async def get_token_for_bot(admin_id: int, bot_id: int) -> Optional[str]:
        """
        Busca token para bot (específico > geral)

        Args:
            admin_id: ID do admin
            bot_id: ID do bot

        Returns:
            Token descriptografado ou None
        """
        # Primeiro tenta buscar token específico do bot
        bot_config = await BotGatewayConfigRepository.get_by_bot_id(
            bot_id, gateway_type="pushinpay"
        )

        if bot_config and bot_config.is_active:
            token = decrypt(bot_config.encrypted_token)
            logger.info(
                "Using bot-specific gateway token",
                extra={"bot_id": bot_id, "admin_id": admin_id},
            )
            return token

        # Se não encontrou, busca token geral do admin
        gateway_config = await GatewayConfigRepository.get_by_admin_id(
            admin_id, gateway_type="pushinpay"
        )

        if gateway_config and gateway_config.is_active:
            token = decrypt(gateway_config.encrypted_token)
            logger.info(
                "Using general gateway token",
                extra={"admin_id": admin_id, "bot_id": bot_id},
            )
            return token

        logger.warning(
            "No gateway token found",
            extra={"admin_id": admin_id, "bot_id": bot_id},
        )
        return None

    @staticmethod
    def get_token_for_bot_sync(admin_id: int, bot_id: int) -> Optional[str]:
        """
        Versão síncrona para workers

        Args:
            admin_id: ID do admin
            bot_id: ID do bot

        Returns:
            Token descriptografado ou None
        """
        # Token específico do bot
        bot_config = BotGatewayConfigRepository.get_by_bot_id_sync(
            bot_id, gateway_type="pushinpay"
        )

        if bot_config and bot_config.is_active:
            return decrypt(bot_config.encrypted_token)

        # Token geral do admin
        gateway_config = GatewayConfigRepository.get_by_admin_id_sync(
            admin_id, gateway_type="pushinpay"
        )

        if gateway_config and gateway_config.is_active:
            return decrypt(gateway_config.encrypted_token)

        return None

    @staticmethod
    async def validate_and_save_token(
        admin_id: int, token: str, gateway_type: str = "pushinpay"
    ) -> bool:
        """
        Valida token via API e salva criptografado

        Args:
            admin_id: ID do admin
            token: Token a ser validado e salvo
            gateway_type: Tipo de gateway (padrão: pushinpay)

        Returns:
            True se validou e salvou com sucesso

        Raises:
            ValueError: Se token inválido
        """
        # Valida token
        is_valid = await PushinPayClient.validate_token(token)

        if not is_valid:
            raise ValueError("Token inválido ou sem permissões necessárias")

        # Criptografa token
        encrypted_token = encrypt(token)

        # Verifica se já existe configuração
        existing_config = await GatewayConfigRepository.get_by_admin_id(
            admin_id, gateway_type
        )

        if existing_config:
            # Atualiza token existente
            await GatewayConfigRepository.update_token(
                admin_id, gateway_type, encrypted_token
            )
            logger.info(
                "Gateway token updated",
                extra={"admin_id": admin_id, "gateway_type": gateway_type},
            )
        else:
            # Cria nova configuração
            await GatewayConfigRepository.create_config(
                admin_id, gateway_type, encrypted_token
            )
            logger.info(
                "Gateway token created",
                extra={"admin_id": admin_id, "gateway_type": gateway_type},
            )

        return True

    @staticmethod
    async def validate_and_save_bot_token(
        bot_id: int, token: str, gateway_type: str = "pushinpay"
    ) -> bool:
        """
        Valida e salva token específico para bot

        Args:
            bot_id: ID do bot
            token: Token a ser validado e salvo
            gateway_type: Tipo de gateway

        Returns:
            True se validou e salvou com sucesso
        """
        # Valida token
        is_valid = await PushinPayClient.validate_token(token)

        if not is_valid:
            raise ValueError("Token inválido")

        # Criptografa token
        encrypted_token = encrypt(token)

        # Verifica se já existe
        existing_config = await BotGatewayConfigRepository.get_by_bot_id(
            bot_id, gateway_type
        )

        if existing_config:
            await BotGatewayConfigRepository.update_token(
                bot_id, gateway_type, encrypted_token
            )
            logger.info(
                "Bot gateway token updated",
                extra={"bot_id": bot_id, "gateway_type": gateway_type},
            )
        else:
            await BotGatewayConfigRepository.create_config(
                bot_id, gateway_type, encrypted_token
            )
            logger.info(
                "Bot gateway token created",
                extra={"bot_id": bot_id, "gateway_type": gateway_type},
            )

        return True

    @staticmethod
    async def get_config_status(admin_id: int, gateway_type: str = "pushinpay") -> bool:
        """
        Verifica se admin tem token configurado

        Args:
            admin_id: ID do admin
            gateway_type: Tipo de gateway

        Returns:
            True se tem token ativo
        """
        config = await GatewayConfigRepository.get_by_admin_id(admin_id, gateway_type)
        return config is not None and config.is_active

    @staticmethod
    async def get_bot_config_status(
        bot_id: int, gateway_type: str = "pushinpay"
    ) -> bool:
        """
        Verifica se bot tem token específico

        Args:
            bot_id: ID do bot
            gateway_type: Tipo de gateway

        Returns:
            True se tem token específico ativo
        """
        config = await BotGatewayConfigRepository.get_by_bot_id(bot_id, gateway_type)
        return config is not None and config.is_active

    @staticmethod
    async def delete_token(admin_id: int, gateway_type: str = "pushinpay") -> bool:
        """
        Remove token geral do admin

        Args:
            admin_id: ID do admin
            gateway_type: Tipo de gateway

        Returns:
            True se removeu com sucesso
        """
        success = await GatewayConfigRepository.delete_config(admin_id, gateway_type)

        if success:
            logger.info(
                "Gateway token deleted",
                extra={"admin_id": admin_id, "gateway_type": gateway_type},
            )

        return success

    @staticmethod
    async def delete_bot_token(bot_id: int, gateway_type: str = "pushinpay") -> bool:
        """
        Remove token específico do bot

        Args:
            bot_id: ID do bot
            gateway_type: Tipo de gateway

        Returns:
            True se removeu com sucesso
        """
        success = await BotGatewayConfigRepository.delete_config(bot_id, gateway_type)

        if success:
            logger.info(
                "Bot gateway token deleted",
                extra={"bot_id": bot_id, "gateway_type": gateway_type},
            )

        return success
