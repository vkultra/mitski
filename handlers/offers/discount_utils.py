"""Utilidades compartilhadas para menu e blocos de descontos."""

from __future__ import annotations

import base64
import hmac
import re
import time
from dataclasses import dataclass
from hashlib import sha256
from typing import Optional

from core.security import HMAC_SECRET
from database.repos import BotRepository, OfferRepository

TOKEN_TTL_SECONDS = 300
PREFIX_MENU = "disc_m:"
PREFIX_TRIGGER = "disc_t:"
PREFIX_ADD = "disc_a:"
PREFIX_PREVIEW = "disc_p:"
PREFIX_BLOCK = "disc_b:"

_ESCAPE_PATTERN = re.compile(r"([_\\*\[\]()~`>#+\-=|{}.!])")


@dataclass
class DiscountTokenData:
    action: str
    user_id: int
    offer_id: int
    extra: Optional[str]
    issued_at: int


def encode_int_base36(value: int) -> str:
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"
    result = []
    while value:
        value, mod = divmod(value, 36)
        result.append(chars[mod])
    return "".join(reversed(result))


def decode_int_base36(value: str) -> int:
    return int(value, 36)


def encode_token(action: str, user_id: int, offer_id: int, extra: str = "") -> str:
    timestamp = int(time.time())
    payload = f"{action}|{user_id}|{offer_id}|{extra}|{timestamp}".encode()
    mac = hmac.new(HMAC_SECRET, payload, sha256).digest()[:8]
    return base64.urlsafe_b64encode(payload + mac).decode()


def get_token_action(token: str) -> Optional[str]:
    try:
        data = _decode_token(token)
    except ValueError:
        return None
    return data.action


async def validate_token(
    user_id: int, token: str, expected_action: str
) -> Optional[DiscountTokenData]:
    try:
        data = _decode_token(token)
    except ValueError:
        return None

    if data.action != expected_action or data.user_id != user_id:
        return None

    if not await _owns_offer(user_id, data.offer_id):
        return None

    return data


async def _owns_offer(user_id: int, offer_id: int) -> bool:
    offer = await OfferRepository.get_offer_by_id(offer_id)
    if not offer:
        return False
    bot = await BotRepository.get_bot_by_id(offer.bot_id)
    return bool(bot and bot.admin_id == user_id)


def build_menu_token(user_id: int, offer_id: int) -> str:
    return encode_token("m", user_id, offer_id)


def escape_markdown(text: Optional[str]) -> str:
    if not text:
        return ""
    return _ESCAPE_PATTERN.sub(r"\\\1", text)


def _decode_token(token: str) -> DiscountTokenData:
    raw = base64.urlsafe_b64decode(token.encode())
    payload, mac = raw[:-8], raw[-8:]
    expected = hmac.new(HMAC_SECRET, payload, sha256).digest()[:8]
    if not hmac.compare_digest(mac, expected):
        raise ValueError("bad mac")

    try:
        action, raw_user, raw_offer, extra, raw_ts = payload.decode().split("|", 4)
    except ValueError as exc:
        raise ValueError("bad payload") from exc

    timestamp = int(raw_ts)
    if time.time() - timestamp > TOKEN_TTL_SECONDS:
        raise ValueError("token expired")

    return DiscountTokenData(
        action=action,
        user_id=int(raw_user),
        offer_id=int(raw_offer),
        extra=extra or None,
        issued_at=timestamp,
    )


__all__ = [
    "TOKEN_TTL_SECONDS",
    "PREFIX_MENU",
    "PREFIX_TRIGGER",
    "PREFIX_ADD",
    "PREFIX_PREVIEW",
    "PREFIX_BLOCK",
    "DiscountTokenData",
    "encode_int_base36",
    "decode_int_base36",
    "encode_token",
    "get_token_action",
    "validate_token",
    "build_menu_token",
    "escape_markdown",
]
