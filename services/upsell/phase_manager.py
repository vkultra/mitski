"""
Gerenciador de fases temporárias de upsell
"""

from core.redis_client import redis_client
from core.telemetry import logger
from database.repos import UpsellPhaseConfigRepository


class UpsellPhaseManager:
    """Gerencia troca de fases temporárias durante upsells usando Redis"""

    UPSELL_PHASE_TTL = 86400  # 24 horas

    @staticmethod
    def _get_redis_key(bot_id: int, user_id: int) -> str:
        """Gera chave Redis para armazenar upsell ativo"""
        return f"upsell:active:{bot_id}:{user_id}"

    @staticmethod
    async def activate_upsell_phase(bot_id: int, user_id: int, upsell_id: int):
        """
        Ativa fase temporária do upsell para o usuário

        Armazena no Redis o upsell_id ativo por 24h
        """
        phase_config = await UpsellPhaseConfigRepository.get_phase_config(upsell_id)

        if not phase_config or not phase_config.phase_prompt:
            logger.warning(
                "No phase config for upsell",
                extra={"upsell_id": upsell_id, "bot_id": bot_id},
            )
            return False

        # Armazenar no Redis
        key = UpsellPhaseManager._get_redis_key(bot_id, user_id)
        redis_client.set(key, str(upsell_id), ex=UpsellPhaseManager.UPSELL_PHASE_TTL)

        logger.info(
            "Upsell phase activated",
            extra={"bot_id": bot_id, "user_id": user_id, "upsell_id": upsell_id},
        )

        return True

    @staticmethod
    def activate_upsell_phase_sync(bot_id: int, user_id: int, upsell_id: int):
        """Versão síncrona para workers"""
        phase_config = UpsellPhaseConfigRepository.get_phase_config_sync(upsell_id)

        if not phase_config or not phase_config.phase_prompt:
            logger.warning(
                "No phase config for upsell",
                extra={"upsell_id": upsell_id, "bot_id": bot_id},
            )
            return False

        # Armazenar no Redis
        key = UpsellPhaseManager._get_redis_key(bot_id, user_id)
        redis_client.set(key, str(upsell_id), ex=UpsellPhaseManager.UPSELL_PHASE_TTL)

        logger.info(
            "Upsell phase activated (sync)",
            extra={"bot_id": bot_id, "user_id": user_id, "upsell_id": upsell_id},
        )

        return True

    @staticmethod
    async def get_active_upsell(bot_id: int, user_id: int):
        """Retorna ID do upsell ativo, se houver"""
        key = UpsellPhaseManager._get_redis_key(bot_id, user_id)
        upsell_id = redis_client.get(key)
        return int(upsell_id) if upsell_id else None

    @staticmethod
    def get_active_upsell_sync(bot_id: int, user_id: int):
        """Versão síncrona"""
        key = UpsellPhaseManager._get_redis_key(bot_id, user_id)
        upsell_id = redis_client.get(key)
        return int(upsell_id) if upsell_id else None

    @staticmethod
    async def clear_upsell_phase(bot_id: int, user_id: int):
        """Remove fase temporária de upsell"""
        key = UpsellPhaseManager._get_redis_key(bot_id, user_id)
        redis_client.delete(key)

        logger.info(
            "Upsell phase cleared", extra={"bot_id": bot_id, "user_id": user_id}
        )

    @staticmethod
    def clear_upsell_phase_sync(bot_id: int, user_id: int):
        """Versão síncrona"""
        key = UpsellPhaseManager._get_redis_key(bot_id, user_id)
        redis_client.delete(key)

        logger.info(
            "Upsell phase cleared (sync)", extra={"bot_id": bot_id, "user_id": user_id}
        )
