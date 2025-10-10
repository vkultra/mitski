"""Compact callback tokens for tracking menu interactions."""

from __future__ import annotations

import base64
import hmac
import struct
import time
from dataclasses import dataclass
from hashlib import sha256
from typing import Optional

from core.security import HMAC_SECRET

_TTL_SECONDS = 300
_PREFIX = "trk:"
_HEADER_STRUCT = struct.Struct("!cQIII B")  # action, user, bot, tracker, ts, extra_len
_MAX_EXTRA_LEN = 24


@dataclass
class TokenData:
    action: str
    user_id: int
    bot_id: Optional[int]
    tracker_id: Optional[int]
    extra: Optional[str]
    timestamp: int


def build_token(
    action: str,
    *,
    user_id: int,
    bot_id: Optional[int] = None,
    tracker_id: Optional[int] = None,
    extra: Optional[str] = None,
) -> str:
    extra_bytes = (extra or "").encode()
    if len(extra_bytes) > _MAX_EXTRA_LEN:
        raise ValueError("Token extra data too long")
    payload = (
        _HEADER_STRUCT.pack(
            action.encode(),
            user_id,
            bot_id or 0,
            tracker_id or 0,
            int(time.time()),
            len(extra_bytes),
        )
        + extra_bytes
    )
    mac = _sign(payload)
    token = base64.urlsafe_b64encode(payload + mac).decode()
    return f"{_PREFIX}{token}"


def parse_token(
    token: str, *, expected_action: Optional[str] = None
) -> Optional[TokenData]:
    if not token.startswith(_PREFIX):
        return None
    raw_token = token[len(_PREFIX) :]
    try:
        blob = base64.urlsafe_b64decode(raw_token.encode())
    except Exception:
        return None
    if len(blob) <= 8:
        return None
    payload, mac = blob[:-8], blob[-8:]
    if not hmac.compare_digest(mac, _sign(payload)):
        return None
    if len(payload) < _HEADER_STRUCT.size:
        return None
    try:
        action_b, user_id, bot_id, tracker_id, timestamp, extra_len = (
            _HEADER_STRUCT.unpack(payload[: _HEADER_STRUCT.size])
        )
    except struct.error:
        return None
    if len(payload) != _HEADER_STRUCT.size + extra_len:
        return None
    action = action_b.decode()
    if expected_action and action != expected_action:
        return None
    if time.time() - timestamp > _TTL_SECONDS:
        return None
    extra_bytes = payload[_HEADER_STRUCT.size :]
    extra = extra_bytes.decode() if extra_bytes else None
    return TokenData(
        action=action,
        user_id=user_id,
        bot_id=bot_id or None,
        tracker_id=tracker_id or None,
        extra=extra,
        timestamp=timestamp,
    )


def _sign(payload: bytes) -> bytes:
    return hmac.new(HMAC_SECRET, payload, sha256).digest()[:8]


__all__ = ["TokenData", "build_token", "parse_token", "_PREFIX"]
