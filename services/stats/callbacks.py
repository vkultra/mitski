"""Callback payload storage for statistics menus."""

from __future__ import annotations

import json
import secrets
from typing import Any, Dict

from core.redis_client import redis_client

_CALLBACK_PREFIX = "stats:cb:"
_TTL_SECONDS = 300


def encode_callback(user_id: int, payload: Dict[str, Any]) -> str:
    """Store payload in Redis and return compact token for callback_data."""
    token = secrets.token_urlsafe(12)
    key = f"{_CALLBACK_PREFIX}{token}"
    redis_client.setex(
        key,
        _TTL_SECONDS,
        json.dumps({"user": user_id, "payload": payload}),
    )
    return f"stats:{token}"


def decode_callback(user_id: int, token: str) -> Dict[str, Any]:
    """Retrieve payload for token ensuring it belongs to the user."""
    key = f"{_CALLBACK_PREFIX}{token}"
    raw = redis_client.get(key)
    if raw is None:
        raise ValueError("callback expired")

    data = json.loads(raw)
    if data.get("user") != user_id:
        raise ValueError("callback owner mismatch")

    # remove to avoid replay
    redis_client.delete(key)

    payload = data.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("invalid payload")
    return payload


__all__ = ["encode_callback", "decode_callback"]
