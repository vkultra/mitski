"""Eventos relacionados a vendas aprovadas."""

from __future__ import annotations

from typing import Optional

from core.config import settings
from core.notifications.dedup import (
    SALE_LOCK_TTL_SECONDS,
    acquire_sale_lock,
    release_sale_lock,
)
from core.notifications.metrics import inc_enqueued
from core.telemetry import logger


def emit_sale_approved(
    transaction_identifier: str,
    *,
    origin: str = "auto",
    lock_ttl: Optional[int] = SALE_LOCK_TTL_SECONDS,
    force: bool = False,
) -> bool:
    """Dispara o fluxo assíncrono de notificação para uma venda aprovada.

    Retorna ``True`` quando a tarefa foi enfileirada.
    """

    if not settings.ENABLE_SALE_NOTIFICATIONS:
        logger.debug(
            "Sale notifications disabled by settings",
            extra={"transaction": transaction_identifier, "origin": origin},
        )
        return False

    if not transaction_identifier:
        logger.warning("Cannot emit sale notification without transaction id")
        return False

    acquired = True
    if not force:
        acquired = acquire_sale_lock(
            transaction_identifier,
            ttl_seconds=lock_ttl or SALE_LOCK_TTL_SECONDS,
        )
        if not acquired:
            logger.debug(
                "Sale notification already scheduled",
                extra={"transaction": transaction_identifier, "origin": origin},
            )
            return False

    try:
        from workers.notifications.tasks import enqueue_sale_notification

        enqueue_sale_notification.delay(transaction_identifier, origin=origin)
        inc_enqueued(origin)
        logger.info(
            "Sale notification task enqueued",
            extra={"transaction": transaction_identifier, "origin": origin},
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Failed to enqueue sale notification",
            extra={"transaction": transaction_identifier, "origin": origin, "error": str(exc)},
        )
        return False
    finally:
        if not force and acquired:
            release_sale_lock(transaction_identifier)


__all__ = ["emit_sale_approved"]
