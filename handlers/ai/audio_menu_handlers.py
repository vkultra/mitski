"""Handlers para configuração de áudio (resposta padrão x Whisper)."""

from __future__ import annotations

import base64
import hmac
import re
import time
from dataclasses import dataclass
from hashlib import sha256
from typing import Dict, Optional

from core.rate_limiter import with_cooldown
from core.security import HMAC_SECRET
from core.telemetry import logger
from database.repos import BotRepository
from services.audio import (
    AudioPreferenceError,
    AudioPreferenceMode,
    AudioPreferencesService,
)
from services.conversation_state import ConversationStateManager

POPUP_MESSAGE = "Configure o reconhecimento de áudio ou mantenha uma resposta padrão fixa usando o botão Configurar."
_TOKEN_TTL_SECONDS = 300

_INFO_PREFIX = "aud_i:"
_MENU_PREFIX = "aud_m:"
_MODE_PREFIX = "aud_o:"
_REPLY_PREFIX = "aud_r:"


@dataclass
class _TokenData:
    action: str
    user_id: int
    bot_id: int
    extra: Optional[str]
    timestamp: int


def build_audio_buttons(user_id: int, bot_id: int) -> Dict[str, str]:
    info_token = _encode_token("i", user_id, bot_id)
    menu_token = _encode_token("m", user_id, bot_id)
    return {
        "info": f"{_INFO_PREFIX}{info_token}",
        "menu": f"{_MENU_PREFIX}{menu_token}",
    }


def _escape_markdown(text: str, limit: int = 400) -> str:
    snippet = text[:limit]
    return re.sub(r"([_\*\[\]()~`>#+\-=|{}.!])", r"\\\1", snippet)


async def handle_audio_popup(user_id: int, token: str) -> Dict[str, Dict[str, object]]:
    if not await _validate_request(user_id, token, expected_action="i"):
        return {
            "callback_alert": {
                "text": "⚠️ Ação inválida ou expirada.",
                "show_alert": True,
            }
        }
    # Usar alerta do tipo popup (mesmo efeito do botão /start)
    return {"callback_alert": {"text": POPUP_MESSAGE, "show_alert": True}}


async def handle_audio_menu_from_token(
    user_id: int, token: str, highlight: Optional[str] = None
) -> Dict[str, object]:
    data = await _validate_request(user_id, token, expected_action="m")
    if not data:
        return {
            "callback_alert": {
                "text": "⚠️ Ação inválida ou expirada.",
                "show_alert": True,
            }
        }
    return await handle_audio_menu(user_id, data.bot_id, highlight=highlight)


async def handle_audio_menu(
    user_id: int, bot_id: int, highlight: Optional[str] = None
) -> Dict[str, object]:
    if not await _owns_bot(user_id, bot_id):
        return {
            "callback_alert": {
                "text": "⚠️ Você não pode configurar este bot.",
                "show_alert": True,
            }
        }

    prefs = AudioPreferencesService.get_preferences(user_id)
    mode_value = prefs.get("mode") or "whisper"
    try:
        mode = AudioPreferenceMode.from_value(mode_value)
    except AudioPreferenceError:
        mode = AudioPreferenceMode.WHISPER
    default_reply = (
        prefs.get("default_reply") or AudioPreferencesService.get_default_reply()
    )

    mode_label = (
        "🟢 Whisper ativo"
        if mode == AudioPreferenceMode.WHISPER
        else "🟡 Resposta padrão ativa"
    )

    escaped_reply = _escape_markdown(default_reply)
    if len(default_reply) > 400:
        escaped_reply += "…"

    info_lines = [
        "🎧 *Áudio: opções de resposta*",
        "",
        f"*Modo atual:* {mode_label}",
        "• Whisper transcreve o áudio e envia para a IA.",
        "• Resposta padrão envia um texto fixo para todo áudio.",
        "",
        "*Texto padrão atual:*",
        escaped_reply or "_(vazio)_",
    ]
    if highlight:
        info_lines.insert(1, highlight)

    whisper_button = {
        "text": (
            "✅ Whisper" if mode == AudioPreferenceMode.WHISPER else "Ativar Whisper"
        ),
        "callback_data": f"{_MODE_PREFIX}{_encode_token('o', user_id, bot_id, 'w')}",
    }
    default_button = {
        "text": (
            "✅ Resposta padrão"
            if mode == AudioPreferenceMode.DEFAULT
            else "Usar resposta padrão"
        ),
        "callback_data": f"{_MODE_PREFIX}{_encode_token('o', user_id, bot_id, 'd')}",
    }

    edit_token = _encode_token("r", user_id, bot_id)

    keyboard = {
        "inline_keyboard": [
            [whisper_button, default_button],
            [
                {
                    "text": "✏️ Ajustar texto padrão",
                    "callback_data": f"{_REPLY_PREFIX}{edit_token}",
                }
            ],
            [
                {"text": "🔙 Voltar", "callback_data": f"action_menu:{bot_id}"},
            ],
        ]
    }

    return {"text": "\n".join(info_lines), "keyboard": keyboard}


async def handle_audio_toggle(user_id: int, token: str) -> Dict[str, object]:
    data = await _validate_request(user_id, token, expected_action="o")
    if not data or not data.extra:
        return {
            "callback_alert": {
                "text": "⚠️ Ação inválida ou expirada.",
                "show_alert": True,
            }
        }

    extra_value = data.extra
    if extra_value == "w":
        mapped_value = "whisper"
    elif extra_value == "d":
        mapped_value = "default"
    else:
        mapped_value = extra_value

    try:
        target_mode = AudioPreferenceMode.from_value(mapped_value)
    except AudioPreferenceError as exc:  # pragma: no cover - defensive
        logger.error(
            "Modo inválido recebido", extra={"mode": mapped_value, "error": str(exc)}
        )
        return {"callback_alert": {"text": "⚠️ Modo inválido.", "show_alert": True}}

    if not with_cooldown(data.bot_id, user_id, "audio:config", seconds=2):
        return {
            "callback_alert": {
                "text": "⏳ Aguarde alguns segundos antes de alterar novamente.",
                "show_alert": False,
            }
        }

    try:
        AudioPreferencesService.set_mode(user_id, target_mode)
    except AudioPreferenceError as exc:
        logger.error(
            "Falha ao alterar modo de áudio",
            extra={"bot_id": data.bot_id, "user_id": user_id, "error": str(exc)},
        )
        return {"callback_alert": {"text": str(exc), "show_alert": True}}
    except Exception as exc:  # pragma: no cover - proteção extra
        logger.error(
            "Falha ao alterar modo de áudio",
            extra={"bot_id": data.bot_id, "user_id": user_id, "error": str(exc)},
        )
        return {
            "callback_alert": {
                "text": "⚠️ Não foi possível atualizar.",
                "show_alert": True,
            }
        }

    highlight = "✅ Modo atualizado!"
    return await handle_audio_menu(user_id, data.bot_id, highlight=highlight)


async def handle_audio_set_reply(user_id: int, token: str) -> Dict[str, object]:
    data = await _validate_request(user_id, token, expected_action="r")
    if not data:
        return {
            "callback_alert": {
                "text": "⚠️ Ação inválida ou expirada.",
                "show_alert": True,
            }
        }

    if not with_cooldown(data.bot_id, user_id, "audio:config", seconds=2):
        return {
            "callback_alert": {
                "text": "⏳ Aguarde alguns segundos antes de alterar novamente.",
                "show_alert": False,
            }
        }

    ConversationStateManager.set_state(
        user_id,
        "awaiting_audio_default_reply",
        {"bot_id": data.bot_id},
    )

    text = (
        "✍️ *Nova resposta padrão*\n\n"
        "Envie o texto que o bot deve usar quando receber um áudio em modo *Resposta padrão*.\n\n"
        "Máximo: 900 caracteres."
    )

    return {"text": text, "keyboard": None}


async def _owns_bot(user_id: int, bot_id: int) -> bool:
    bot = await BotRepository.get_bot_by_id(bot_id)
    if not bot:
        return False
    return bool(getattr(bot, "admin_id", None) == user_id)


async def _validate_request(
    user_id: int, token: str, expected_action: str
) -> Optional[_TokenData]:
    try:
        data = _decode_token(token)
    except ValueError:
        return None

    if not _action_matches(data.action, expected_action):
        return None

    if data.user_id != user_id:
        return None

    if not await _owns_bot(user_id, data.bot_id):
        return None

    return data


def _encode_token(
    action: str, user_id: int, bot_id: int, extra: Optional[str] = None
) -> str:
    timestamp = int(time.time())
    extra_part = extra or ""
    payload = f"{action}|{user_id}|{bot_id}|{extra_part}|{timestamp}".encode()
    mac = hmac.new(HMAC_SECRET, payload, sha256).digest()[:8]
    return base64.urlsafe_b64encode(payload + mac).decode()


def _decode_token(token: str) -> _TokenData:
    try:
        blob = base64.urlsafe_b64decode(token.encode())
    except Exception as exc:
        raise ValueError("invalid token") from exc

    if len(blob) <= 8:
        raise ValueError("token too short")

    payload, mac = blob[:-8], blob[-8:]
    expected = hmac.new(HMAC_SECRET, payload, sha256).digest()[:8]
    if not hmac.compare_digest(mac, expected):
        raise ValueError("bad signature")

    try:
        action, raw_user, raw_bot, extra, raw_ts = payload.decode().split("|", 4)
    except Exception as exc:
        raise ValueError("bad payload") from exc

    timestamp = int(raw_ts)
    if time.time() - timestamp > _TOKEN_TTL_SECONDS:
        raise ValueError("token expired")

    user_id = int(raw_user)
    bot_id = int(raw_bot)
    extra_value = extra or None

    return _TokenData(
        action=action,
        user_id=user_id,
        bot_id=bot_id,
        extra=extra_value,
        timestamp=timestamp,
    )


def _action_matches(actual: str, expected: str) -> bool:
    if actual == expected:
        return True

    legacy_map = {
        "i": "info",
        "m": "menu",
        "o": "mode",
        "r": "reply",
    }
    return legacy_map.get(expected) == actual
