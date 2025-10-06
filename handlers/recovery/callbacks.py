"""Store-and-forward callbacks for the recovery module."""

from __future__ import annotations

import json
import secrets
import time
from typing import Any, Dict, Tuple

from core.redis_client import redis_client
from core.telemetry import logger

_PREFIX = "rec"
_STORE_PREFIX = "rec:cb:"
_LOCAL_STORE: Dict[str, tuple[float, str]] = {}


def build_callback(action: str, ttl: int = 900, **data: Any) -> str:
    """Persist callback payload in Redis (or local fallback) and emit token."""

    token = secrets.token_urlsafe(12).replace("-", "_")  # <= ~16 chars
    payload = json.dumps({"a": action, **data})
    store_key = f"{_STORE_PREFIX}{token}"

    try:
        redis_client.setex(store_key, ttl, payload)
    except Exception:
        _LOCAL_STORE[store_key] = (time.time() + ttl, payload)
        logger.warning(
            "Recovery callback stored in local cache",
            extra={"key": store_key},
        )
    else:
        logger.debug(
            "Recovery callback stored",
            extra={"key": store_key},
        )

    return f"{_PREFIX}:{token}"


def _pop_local(store_key: str) -> str | None:
    expires_at, cached = _LOCAL_STORE.pop(store_key, (0.0, ""))
    if not cached or expires_at < time.time():
        return None
    return cached


def parse_callback(callback: str) -> Tuple[str, Dict[str, Any]]:
    """Retrieve callback payload from Redis/local cache and validate it."""

    if not callback.startswith(f"{_PREFIX}:"):
        raise ValueError("invalid_prefix")

    token = callback.split(":", 1)[1]
    store_key = f"{_STORE_PREFIX}{token}"

    raw_payload = None
    try:
        raw_payload = redis_client.get(store_key)
    except Exception:
        raw_payload = None

    if raw_payload:
        redis_client.delete(store_key)
    else:
        raw_payload = _pop_local(store_key)
        if not raw_payload:
            raise ValueError("expired")

    payload = json.loads(raw_payload)
    action = payload.pop("a", None)
    if not action:
        raise ValueError("missing_action")

    return action, payload
