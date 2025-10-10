"""Orquestra o fluxo do primeiro /start por usuário"""

from __future__ import annotations

from typing import Optional

from core.redis_client import redis_client
from core.telemetry import logger
from database.repos import StartMessageStatusRepository

from .metrics import inc_scheduled
from .template_service import StartTemplateMetadata, StartTemplateService


class StartFlowService:
    """Determina quando enviar a mensagem inicial customizada"""

    _PENDING_TTL_SECONDS = 600

    @staticmethod
    def _pending_key(bot_id: int, user_id: int) -> str:
        return f"start_template:pending:{bot_id}:{user_id}"

    @classmethod
    def release_pending(cls, bot_id: int, user_id: int) -> None:
        """Remove marcação de processamento pendente"""
        redis_client.delete(cls._pending_key(bot_id, user_id))

    @classmethod
    def _try_claim(cls, bot_id: int, user_id: int) -> bool:
        """Marca usuário como pendente evitando duplicidade"""
        return bool(
            redis_client.set(
                cls._pending_key(bot_id, user_id),
                "1",
                nx=True,
                ex=cls._PENDING_TTL_SECONDS,
            )
        )

    @classmethod
    async def handle_start_command(
        cls,
        bot,
        user_id: int,
        chat_id: int,
    ) -> bool:
        """Processa /start do usuário. Retorna True se tratado aqui."""
        metadata = await StartTemplateService.get_metadata(bot.id)

        if not metadata.is_active or not metadata.has_blocks:
            inc_scheduled("inactive")
            return False

        # Verificar se usuário já recebeu mensagem inicial
        if StartMessageStatusRepository.has_received_sync(bot.id, user_id):
            inc_scheduled("already_sent")
            return False

        if not cls._try_claim(bot.id, user_id):
            inc_scheduled("pending")
            return False

        logger.info(
            "Scheduling start template",
            extra={
                "bot_id": bot.id,
                "user_id": user_id,
                "template_id": metadata.template_id,
                "template_version": metadata.version,
            },
        )
        inc_scheduled("scheduled")

        try:
            from workers.start_tasks import send_start_message

            send_start_message.delay(
                bot_id=bot.id,
                template_id=metadata.template_id,
                template_version=metadata.version,
                user_id=user_id,
                chat_id=chat_id,
            )
        except Exception as exc:  # pragma: no cover - proteção
            logger.error(
                "Failed to dispatch start message task",
                extra={"bot_id": bot.id, "user_id": user_id, "error": str(exc)},
            )
            cls.release_pending(bot.id, user_id)
            raise

        return True

    @classmethod
    async def preview_metadata(cls, bot_id: int) -> Optional[StartTemplateMetadata]:
        """Exposto para testes ou endpoints administrativos"""
        try:
            return await StartTemplateService.get_metadata(bot_id)
        except Exception as err:  # pragma: no cover - proteção adicional
            logger.warning(
                "Failed to load start template metadata",
                extra={"bot_id": bot_id, "error": str(err)},
            )
            return None
