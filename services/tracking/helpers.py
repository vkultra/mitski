"""Utility helpers shared across tracking services."""

from __future__ import annotations

import secrets
import string
from typing import Dict, Iterable

from database.repos import BotRepository
from database.tracking_repos import (
    count_active_by_bot,
    get_bot_config,
    get_tracker_by_code,
)
from services.tracking import cache
from services.tracking.types import TrackerNotFoundError

_BASE62 = string.ascii_letters + string.digits
_CODE_LENGTH = 8


def ensure_bot(admin_id: int, bot_id: int):
    bot = BotRepository.get_bot_by_id_sync(bot_id)
    if not bot or bot.admin_id != admin_id:
        raise TrackerNotFoundError
    if not bot.username:
        raise ValueError("Bot sem username definido no Telegram.")
    return bot


def load_bot_usernames(admin_id: int, bot_ids: Iterable[int]) -> Dict[int, str]:
    usernames: Dict[int, str] = {}
    for bot_id in bot_ids:
        bot = BotRepository.get_bot_by_id_sync(bot_id)
        if bot and bot.admin_id == admin_id and bot.username:
            usernames[bot_id] = bot.username
    return usernames


def build_deeplink(username: str, code: str) -> str:
    if not username:
        return code
    return f"https://t.me/{username}?start={code}"


def generate_unique_code(bot_id: int) -> str:
    for _ in range(8):
        candidate = "".join(secrets.choice(_BASE62) for _ in range(_CODE_LENGTH))
        if not get_tracker_by_code(bot_id, candidate):
            return candidate
    raise RuntimeError("Não foi possível gerar um código único.")


def sanitize_name(name: str) -> str:
    clean = " ".join(name.strip().split())
    if len(clean) < 3:
        raise ValueError("Nome muito curto. Use pelo menos 3 caracteres.")
    if len(clean) > 48:
        raise ValueError("Nome muito longo. Limite de 48 caracteres.")
    return clean


def load_ignore_flag(admin_id: int, bot_id: int) -> bool:
    cached = cache.get_bot_config(bot_id)
    if cached is not None:
        return cached[0]
    flag = get_bot_config(bot_id)
    if flag is None:
        return False
    cache.cache_bot_config(
        bot_id, ignore=flag, active_count=count_active_by_bot(bot_id)
    )
    return flag


__all__ = [
    "ensure_bot",
    "load_bot_usernames",
    "build_deeplink",
    "generate_unique_code",
    "sanitize_name",
    "load_ignore_flag",
]
