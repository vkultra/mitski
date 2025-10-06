"""Gerenciamento de estado em Redis para a recuperação."""

from __future__ import annotations

import time
import uuid
from typing import Optional

from core.redis_client import redis_client

_STATE_TTL = 60 * 60 * 24 * 30  # 30 dias


def _last_active_key(bot_id: int, user_id: int) -> str:
    return f"rec:last_active:{bot_id}:{user_id}"


def _inactivity_version_key(bot_id: int, user_id: int) -> str:
    return f"rec:iv:{bot_id}:{user_id}"


def _episode_key(bot_id: int, user_id: int) -> str:
    return f"rec:episode:{bot_id}:{user_id}"


def _campaign_version_key(bot_id: int, user_id: int) -> str:
    return f"rec:campaign_ver:{bot_id}:{user_id}"


def mark_user_activity(bot_id: int, user_id: int) -> int:
    """Atualiza último contato do usuário e retorna nova versão de inatividade."""

    now = int(time.time())
    pipeline = redis_client.pipeline()
    pipeline.setex(_last_active_key(bot_id, user_id), _STATE_TTL, now)
    pipeline.incr(_inactivity_version_key(bot_id, user_id))
    pipeline.expire(_inactivity_version_key(bot_id, user_id), _STATE_TTL)
    pipeline.delete(_episode_key(bot_id, user_id))
    _, version, _, _ = pipeline.execute()
    return int(version)


def get_last_activity(bot_id: int, user_id: int) -> Optional[int]:
    value = redis_client.get(_last_active_key(bot_id, user_id))
    return int(value) if value else None


def get_inactivity_version(bot_id: int, user_id: int) -> int:
    value = redis_client.get(_inactivity_version_key(bot_id, user_id))
    return int(value) if value else 0


def remember_campaign_version(bot_id: int, user_id: int, version: int) -> None:
    redis_client.setex(_campaign_version_key(bot_id, user_id), _STATE_TTL, version)


def get_campaign_version(bot_id: int, user_id: int) -> Optional[int]:
    value = redis_client.get(_campaign_version_key(bot_id, user_id))
    return int(value) if value else None


def allocate_episode(bot_id: int, user_id: int, episode_id: str) -> None:
    redis_client.setex(_episode_key(bot_id, user_id), _STATE_TTL, episode_id)


def try_allocate_episode(bot_id: int, user_id: int, episode_id: str) -> bool:
    return bool(
        redis_client.set(
            _episode_key(bot_id, user_id),
            episode_id,
            nx=True,
            ex=_STATE_TTL,
        )
    )


def current_episode(bot_id: int, user_id: int) -> Optional[str]:
    return redis_client.get(_episode_key(bot_id, user_id))


def clear_episode(bot_id: int, user_id: int) -> None:
    redis_client.delete(_episode_key(bot_id, user_id))


def generate_episode_id() -> str:
    return uuid.uuid4().hex
