"""Runtime helpers for handling /start tracking and enforcement."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple

from core.telemetry import logger
from database.tracking_repos import (
    count_active_by_bot,
    get_bot_config,
    get_tracker_by_code,
    get_tracker_by_id,
)
from database.tracking_stats_repo import get_attribution
from services.tracking import cache
from services.tracking.service import TrackerService

_CODE_PREFIX = "/start"


def extract_tracker_code(message_text: str) -> Optional[str]:
    if not message_text or not message_text.startswith(_CODE_PREFIX):
        return None
    parts = message_text.split(" ", 1)
    if len(parts) < 2:
        return None
    code = parts[1].strip()
    return code or None


def should_ignore_untracked(bot_id: int) -> Tuple[bool, int]:
    cached = cache.get_bot_config(bot_id)
    if cached is not None:
        return cached
    flag = get_bot_config(bot_id)
    active = count_active_by_bot(bot_id)
    ignore = bool(flag)
    cache.cache_bot_config(bot_id, ignore=ignore, active_count=active)
    return ignore, active


def resolve_tracker(bot_id: int, code: str):
    tracker_id = cache.get_tracker_id_cached(bot_id, code)
    if tracker_id:
        tracker = get_tracker_by_id(tracker_id)
        if tracker:
            return tracker
    tracker = get_tracker_by_code(bot_id, code)
    if tracker:
        cache.cache_tracker_code(bot_id, code, tracker.id)
    return tracker


def handle_start(
    *,
    bot_id: int,
    user_id: int,
    message_text: str,
    now: datetime,
) -> Tuple[str, Optional[int]]:
    code = extract_tracker_code(message_text)
    tracker = resolve_tracker(bot_id, code) if code else None

    if tracker:
        cache.cache_attribution(bot_id, user_id, tracker.id)
        service = TrackerService(tracker.admin_id)
        service.record_start(
            bot_id=bot_id, tracker_id=tracker.id, user_id=user_id, when=now
        )
        return "tracked", tracker.id

    if code is None:
        existing = cache.get_cached_attribution(bot_id, user_id)
        if existing is None:
            existing = get_attribution(bot_id=bot_id, user_telegram_id=user_id)
            if existing:
                cache.cache_attribution(bot_id, user_id, existing)

        if existing:
            return "pass", existing

    ignore_flag, active_count = should_ignore_untracked(bot_id)
    if ignore_flag and active_count > 0:
        logger.info(
            "Start ignored due to enforcement",
            extra={"bot_id": bot_id, "user_id": user_id, "has_code": bool(code)},
        )
        return "ignored", None

    return "pass", None


__all__ = [
    "extract_tracker_code",
    "should_ignore_untracked",
    "resolve_tracker",
    "handle_start",
]
