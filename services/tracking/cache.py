"""Redis helpers for tracker lookups and configs."""

from __future__ import annotations

from typing import Optional, Tuple

from core.redis_client import redis_client

_CODE_KEY = "trk:code:{bot}:{code}"
_CONFIG_KEY = "trk:cfg:{bot}"
_ATTR_KEY = "trk:attr:{bot}:{user}"
_ATTR_TTL = 60 * 60 * 24 * 30  # 30 days
_CODE_TTL = 60 * 60 * 24 * 7  # 7 days; refreshed on hits
_CONFIG_TTL = 300


def cache_tracker_code(bot_id: int, code: str, tracker_id: int) -> None:
    redis_client.set(
        _CODE_KEY.format(bot=bot_id, code=code),
        tracker_id,
        ex=_CODE_TTL,
    )


def drop_tracker_code(bot_id: int, code: str) -> None:
    redis_client.delete(_CODE_KEY.format(bot=bot_id, code=code))


def get_tracker_id_cached(bot_id: int, code: str) -> Optional[int]:
    raw = redis_client.get(_CODE_KEY.format(bot=bot_id, code=code))
    if raw is None:
        return None
    try:
        tracker_id = int(raw)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        redis_client.delete(_CODE_KEY.format(bot=bot_id, code=code))
        return None
    return tracker_id


def cache_bot_config(bot_id: int, *, ignore: bool, active_count: int) -> None:
    value = f"{1 if ignore else 0}|{active_count}"
    redis_client.set(_CONFIG_KEY.format(bot=bot_id), value, ex=_CONFIG_TTL)


def get_bot_config(bot_id: int) -> Optional[Tuple[bool, int]]:
    raw = redis_client.get(_CONFIG_KEY.format(bot=bot_id))
    if not raw:
        return None
    try:
        ignore_flag, active_count = raw.split("|", 1)
        return bool(int(ignore_flag)), int(active_count)
    except (ValueError, TypeError):  # pragma: no cover - defensive
        redis_client.delete(_CONFIG_KEY.format(bot=bot_id))
        return None


def cache_attribution(bot_id: int, user_id: int, tracker_id: int) -> None:
    redis_client.set(
        _ATTR_KEY.format(bot=bot_id, user=user_id),
        tracker_id,
        ex=_ATTR_TTL,
    )


def get_cached_attribution(bot_id: int, user_id: int) -> Optional[int]:
    raw = redis_client.get(_ATTR_KEY.format(bot=bot_id, user=user_id))
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        redis_client.delete(_ATTR_KEY.format(bot=bot_id, user=user_id))
        return None


def drop_cached_attribution(bot_id: int, user_id: int) -> None:
    redis_client.delete(_ATTR_KEY.format(bot=bot_id, user=user_id))


__all__ = [
    "cache_tracker_code",
    "drop_tracker_code",
    "get_tracker_id_cached",
    "cache_bot_config",
    "get_bot_config",
    "cache_attribution",
    "get_cached_attribution",
    "drop_cached_attribution",
]
