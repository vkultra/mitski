"""Serviço de preferências de áudio (modo padrão vs. Whisper)."""

from __future__ import annotations

import json
from contextlib import contextmanager
from enum import Enum
from typing import Dict, Final, cast

from core.redis_client import redis_client
from core.telemetry import logger
from database.audio_preferences_repo import (
    DEFAULT_AUDIO_REPLY,
    AudioPreferencesRepository,
)

CACHE_TTL_SECONDS = 60
LOCK_TTL_SECONDS = 5
CACHED_DEFAULT_REPLY: Final[str] = DEFAULT_AUDIO_REPLY


class AudioPreferenceError(RuntimeError):
    """Erro genérico ao manipular preferências de áudio"""


class AudioPreferenceMode(str, Enum):
    DEFAULT = "default"
    WHISPER = "whisper"

    @classmethod
    def from_value(cls, value: str) -> "AudioPreferenceMode":
        try:
            return cls(value)
        except ValueError as exc:
            raise AudioPreferenceError(f"Modo de áudio inválido: {value}") from exc


class AudioPreferencesService:
    """Camada de serviço com cache + lock para preferências de áudio"""

    @staticmethod
    def _cache_key(admin_id: int) -> str:
        return f"audio:prefs:{admin_id}"

    @staticmethod
    @contextmanager
    def _lock(admin_id: int):
        lock_key = f"lock:audio:prefs:{admin_id}"
        acquired = redis_client.set(lock_key, "1", nx=True, ex=LOCK_TTL_SECONDS)
        if not acquired:
            raise AudioPreferenceError(
                "Configuração de áudio em andamento. Tente novamente."
            )
        try:
            yield
        finally:
            redis_client.delete(lock_key)

    @classmethod
    def get_preferences(cls, admin_id: int) -> Dict[str, str]:
        cache_key = cls._cache_key(admin_id)
        cached = redis_client.get(cache_key)
        if cached:
            try:
                data = cast(Dict[str, str], json.loads(cached))
                if {"mode", "default_reply"}.issubset(data):
                    return data
            except json.JSONDecodeError:
                logger.warning(
                    "Invalid audio preference cache payload",
                    extra={"admin_id": admin_id},
                )

        pref = AudioPreferencesRepository.get_or_create(admin_id)
        data = {
            "mode": pref.mode,
            "default_reply": pref.default_reply or DEFAULT_AUDIO_REPLY,
        }
        redis_client.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(data))
        return data

    @classmethod
    def set_mode(cls, admin_id: int, mode: AudioPreferenceMode) -> Dict[str, str]:
        with cls._lock(admin_id):
            pref = AudioPreferencesRepository.update_mode(admin_id, mode.value)
            data: Dict[str, str] = {
                "mode": pref.mode,
                "default_reply": pref.default_reply or DEFAULT_AUDIO_REPLY,
            }
            redis_client.setex(
                cls._cache_key(admin_id), CACHE_TTL_SECONDS, json.dumps(data)
            )
            return data

    @classmethod
    def set_default_reply(cls, admin_id: int, reply: str) -> Dict[str, str]:
        sanitized = reply.strip()
        if not sanitized:
            raise AudioPreferenceError("A resposta padrão não pode ser vazia.")
        if len(sanitized) > 900:
            raise AudioPreferenceError("A resposta padrão deve ter até 900 caracteres.")

        with cls._lock(admin_id):
            pref = AudioPreferencesRepository.update_default_reply(admin_id, sanitized)
            data: Dict[str, str] = {
                "mode": pref.mode,
                "default_reply": pref.default_reply,
            }
            redis_client.setex(
                cls._cache_key(admin_id), CACHE_TTL_SECONDS, json.dumps(data)
            )
            return data

    @staticmethod
    def get_default_reply() -> str:
        return CACHED_DEFAULT_REPLY
