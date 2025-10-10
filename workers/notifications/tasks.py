"""Tasks Celery responsáveis pelo envio das notificações de venda."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from celery import Task

from core.config import settings
from core.notifications.dispatcher import TelegramNotificationClient
from core.notifications.metrics import inc_processed
from core.notifications.renderer import SaleMessageData, render_sale_message
from core.telemetry import logger
from database.notifications.repos import (
    NotificationSettingsRepository,
    SaleNotificationsRepository,
)
from database.repos import BotRepository, PixTransactionRepository, UserRepository
from workers.celery_app import celery_app


def _resolve_active_settings(owner_user_id: int, bot_id: int):
    bot_settings = NotificationSettingsRepository.get_for_owner_sync(
        owner_user_id, bot_id
    )
    if bot_settings and bot_settings.enabled and bot_settings.channel_id:
        return bot_settings

    default_settings = NotificationSettingsRepository.get_default_sync(owner_user_id)
    if default_settings and default_settings.enabled and default_settings.channel_id:
        return default_settings

    return None


@celery_app.task(
    bind=True,
    max_retries=3,
    name="workers.notifications.tasks.enqueue_sale_notification",
)
def enqueue_sale_notification(
    self: Task, transaction_id: str, origin: str = "auto"
) -> None:
    transaction = PixTransactionRepository.get_by_transaction_id_sync(transaction_id)
    if not transaction:
        logger.warning(
            "Sale notification aborted: transaction not found",
            extra={"transaction_id": transaction_id, "origin": origin},
        )
        return

    bot = BotRepository.get_bot_by_id_sync(transaction.bot_id)
    if not bot:
        logger.error(
            "Sale notification aborted: bot not found",
            extra={"transaction_id": transaction_id, "bot_id": transaction.bot_id},
        )
        return

    settings = _resolve_active_settings(bot.admin_id, bot.id)

    user = UserRepository.get_user_sync(bot.id, transaction.user_telegram_id)
    buyer_username = user.username if user else None

    record_data = {
        "transaction_id": transaction.transaction_id,
        "provider": origin,
        "owner_user_id": bot.admin_id,
        "bot_id": bot.id,
        "channel_id": settings.channel_id if settings else None,
        "is_upsell": bool(transaction.upsell_id),
        "amount_cents": transaction.value_cents,
        "currency": "BRL",
        "buyer_user_id": transaction.user_telegram_id,
        "buyer_username": buyer_username,
        "bot_username": bot.username,
        "origin": origin,
        "status": "pending" if settings else "skipped",
    }

    record, created = SaleNotificationsRepository.create_if_absent_sync(record_data)
    if not record:
        logger.warning(
            "Sale notification record missing after creation attempt",
            extra={"transaction_id": transaction_id},
        )
        return

    if not settings:
        SaleNotificationsRepository.mark_status_sync(
            transaction.transaction_id,
            status="skipped",
            error="missing_channel_configuration",
        )
        inc_processed("skipped")
        logger.info(
            "Sale notification skipped: no channel configured",
            extra={
                "transaction_id": transaction.transaction_id,
                "owner_user_id": bot.admin_id,
                "bot_id": bot.id,
            },
        )
        return

    if not record.channel_id:
        SaleNotificationsRepository.mark_status_sync(
            transaction.transaction_id,
            status="skipped",
            error="channel_not_available",
        )
        inc_processed("skipped")
        return

    if not created and record.status != "pending":
        logger.info(
            "Sale notification already processed",
            extra={
                "transaction_id": transaction.transaction_id,
                "status": record.status,
            },
        )
        return

    send_sale_notification_message.delay(transaction.transaction_id)


@celery_app.task(
    bind=True,
    max_retries=3,
    name="workers.notifications.tasks.send_sale_notification_message",
)
def send_sale_notification_message(self: Task, transaction_id: str) -> None:
    record = SaleNotificationsRepository.get_by_transaction_sync(transaction_id)
    if not record:
        logger.warning(
            "Sale notification send aborted: record not found",
            extra={"transaction_id": transaction_id},
        )
        return

    if record.status != "pending":
        logger.info(
            "Sale notification already handled",
            extra={"transaction_id": transaction_id, "status": record.status},
        )
        return

    if not record.channel_id:
        SaleNotificationsRepository.mark_status_sync(
            record.transaction_id,
            status="skipped",
            error="missing_channel_id",
        )
        inc_processed("skipped")
        return

    bot = BotRepository.get_bot_by_id_sync(record.bot_id)
    if not bot:
        SaleNotificationsRepository.mark_status_sync(
            record.transaction_id,
            status="failed",
            error="bot_not_found",
        )
        inc_processed("failed")
        logger.error(
            "Sale notification failed: bot not found",
            extra={"transaction_id": transaction_id, "bot_id": record.bot_id},
        )
        return

    manager_token = settings.MANAGER_BOT_TOKEN
    if not manager_token:
        SaleNotificationsRepository.mark_status_sync(
            record.transaction_id,
            status="failed",
            error="manager_token_missing",
        )
        inc_processed("failed")
        logger.error(
            "Sale notification failed: manager bot token not configured",
            extra={"transaction_id": transaction_id},
        )
        return

    client = TelegramNotificationClient(manager_token)

    message = render_sale_message(
        SaleMessageData(
            amount_cents=record.amount_cents,
            currency=record.currency,
            buyer_username=record.buyer_username,
            buyer_user_id=record.buyer_user_id,
            bot_username=record.bot_username or bot.username,
            is_upsell=record.is_upsell,
        )
    )

    try:
        client.send_message(int(record.channel_id), message)
        SaleNotificationsRepository.mark_status_sync(
            record.transaction_id,
            status="sent",
            notified_at=datetime.utcnow(),
            error=None,
        )
        inc_processed("sent")
        logger.info(
            "Sale notification sent",
            extra={
                "transaction_id": transaction_id,
                "channel_id": record.channel_id,
                "bot_id": record.bot_id,
            },
        )
    except Exception as exc:  # noqa: BLE001
        if self.request.retries < self.max_retries:
            logger.warning(
                "Sale notification send failed, retrying",
                extra={
                    "transaction_id": transaction_id,
                    "error": str(exc),
                    "attempt": self.request.retries + 1,
                },
            )
            raise self.retry(countdown=2**self.request.retries, exc=exc)

        SaleNotificationsRepository.mark_status_sync(
            record.transaction_id,
            status="failed",
            error=str(exc),
        )
        inc_processed("failed")
        logger.error(
            "Sale notification failed after retries",
            extra={"transaction_id": transaction_id, "error": str(exc)},
        )
        raise


__all__ = [
    "enqueue_sale_notification",
    "send_sale_notification_message",
]
