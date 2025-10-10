"""Tasks relacionadas à mensagem inicial (/start)."""

from __future__ import annotations

import asyncio
import threading

from core.security import decrypt
from core.telemetry import logger
from database.repos import BotRepository, StartMessageStatusRepository
from services.start import StartFlowService, StartTemplateService, inc_delivered
from services.start.start_sender import StartTemplateSenderService

from .celery_app import celery_app


@celery_app.task(bind=True, max_retries=3)
def send_start_message(
    self,
    bot_id: int,
    template_id: int,
    template_version: int,
    user_id: int,
    chat_id: int,
):
    """Envia a mensagem inicial configurada para um usuário"""
    bot = BotRepository.get_bot_by_id_sync(bot_id)
    if not bot or not bot.is_active:
        logger.warning(
            "Bot not available for start message",
            extra={"bot_id": bot_id, "user_id": user_id},
        )
        inc_delivered("bot_inactive")
        StartFlowService.release_pending(bot_id, user_id)
        return

    if StartMessageStatusRepository.has_received_sync(bot_id, user_id):
        inc_delivered("already_sent")
        StartFlowService.release_pending(bot_id, user_id)
        return

    bot_token = decrypt(bot.token)

    async def _run() -> None:
        metadata = await StartTemplateService.get_metadata(bot_id)
        if not metadata.is_active or metadata.template_id != template_id:
            logger.info(
                "Start template inactive or updated, skipping send",
                extra={
                    "bot_id": bot_id,
                    "user_id": user_id,
                    "template_id": template_id,
                    "metadata_template_id": metadata.template_id,
                },
            )
            inc_delivered("skipped")
            return

        sender = StartTemplateSenderService(bot_token)
        await sender.send_template(
            template_id=template_id,
            bot_id=bot_id,
            chat_id=chat_id,
            preview_mode=False,
        )

        await StartMessageStatusRepository.mark_sent(
            bot_id=bot_id,
            user_telegram_id=user_id,
            template_version=template_version,
        )
        inc_delivered("success")

    try:
        try:
            asyncio.run(_run())
        except RuntimeError as loop_error:
            if "asyncio.run() cannot be called" in str(loop_error):
                thread = threading.Thread(target=lambda: asyncio.run(_run()))
                thread.start()
                thread.join()
            else:
                raise
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Failed to send start template",
            extra={
                "bot_id": bot_id,
                "user_id": user_id,
                "template_id": template_id,
                "error": str(exc),
            },
        )
        inc_delivered("error")
        raise self.retry(exc=exc, countdown=2**self.request.retries)
    else:
        StartFlowService.release_pending(bot_id, user_id)
