"""Lightweight helpers to persist telemetry events without coupling."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from core.telemetry import logger
from database.repos import BotRepository
from database.stats_repos import StatsEventRepository


def _owner_for_bot(bot_id: int) -> Optional[int]:
    bot = BotRepository.get_bot_by_id_sync(bot_id)
    return bot.admin_id if bot else None


def record_start_event(
    bot_id: int,
    user_telegram_id: int,
    occurred_at: Optional[datetime] = None,
) -> None:
    """Persist a /start occurrence in the background."""

    owner_id = _owner_for_bot(bot_id)
    if owner_id is None:
        logger.debug("Bot not found while logging start", extra={"bot_id": bot_id})
        return
    StatsEventRepository.record_start(
        owner_id, bot_id, user_telegram_id, occurred_at or datetime.utcnow()
    )


def record_phase_transition(
    bot_id: int,
    user_telegram_id: int,
    to_phase_id: int,
    *,
    from_phase_id: Optional[int] = None,
    occurred_at: Optional[datetime] = None,
) -> None:
    """Persist IA phase transitions for abandonment reports."""

    owner_id = _owner_for_bot(bot_id)
    if owner_id is None:
        logger.debug(
            "Bot not found while logging phase transition",
            extra={"bot_id": bot_id, "to_phase_id": to_phase_id},
        )
        return
    StatsEventRepository.record_phase_transition(
        owner_id=owner_id,
        bot_id=bot_id,
        user_telegram_id=user_telegram_id,
        from_phase_id=from_phase_id,
        to_phase_id=to_phase_id,
        occurred_at=occurred_at or datetime.utcnow(),
    )


__all__ = ["record_start_event", "record_phase_transition"]
