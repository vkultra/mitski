"""Tasks específicas para processamento de áudios e voz."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from core.config import settings
from core.rate_limiter import check_rate_limit
from core.redis_client import redis_client
from core.security import decrypt
from core.telemetry import logger
from database.repos import AIConfigRepository, BotRepository
from services.audio import (
    AudioPreferenceMode,
    AudioPreferencesService,
    TelegramAudioService,
    record_audio_failure,
    record_audio_processing,
)
from services.typing_effect import TypingEffectService
from workers.celery_app import celery_app
from workers.whisper_client import WhisperAPIError, WhisperClient

TRANSCRIPTION_CACHE_TTL = 86_400  # 24 horas


def _get_cache_key(file_unique_id: str) -> str:
    return f"audio:transcription:{file_unique_id}"


def _should_reject_media(media: Dict[str, Optional[Any]]) -> bool:
    duration_val = media.get("duration")
    duration = (
        int(duration_val)
        if isinstance(duration_val, (int, float)) and duration_val is not None
        else 0
    )
    if duration and duration > settings.AUDIO_MAX_DURATION:
        logger.warning(
            "Audio duration exceeded",
            extra={"duration": duration, "limit": settings.AUDIO_MAX_DURATION},
        )
        return True

    size_val = media.get("file_size")
    file_size = (
        int(size_val)
        if isinstance(size_val, (int, float)) and size_val is not None
        else 0
    )
    max_bytes = settings.AUDIO_MAX_SIZE_MB * 1024 * 1024
    if file_size and file_size > max_bytes:
        logger.warning(
            "Audio size exceeded",
            extra={"size_bytes": file_size, "limit_bytes": max_bytes},
        )
        return True
    return False


def _send_default_reply(encrypted_token: bytes, chat_id: int, reply: str) -> None:
    token = decrypt(encrypted_token)
    from workers.api_clients import TelegramAPI

    telegram_api = TelegramAPI()
    TypingEffectService.apply_typing_effect_sync(
        api=telegram_api, token=token, chat_id=chat_id, text=reply, media_type=None
    )
    telegram_api.send_message_sync(token=token, chat_id=chat_id, text=reply)


def _determine_filename(media_type: str, mime_type: Optional[str]) -> str:
    if media_type == "voice":
        return "voice.ogg"
    if mime_type:
        if "mpeg" in mime_type:
            return "audio.mp3"
        if "ogg" in mime_type:
            return "audio.ogg"
        if "wav" in mime_type:
            return "audio.wav"
        if "mp4" in mime_type or "m4a" in mime_type:
            return "audio.m4a"
    return "audio.webm"


def _determine_mime_type(media_type: str, mime_type: Optional[str]) -> str:
    if mime_type:
        return mime_type
    return "audio/ogg" if media_type == "voice" else "audio/mpeg"


@celery_app.task(bind=True, max_retries=2, queue="audio")
def process_audio_message(
    self,
    bot_id: int,
    user_id: int,
    chat_id: int,
    media: Dict[str, Optional[str]],
) -> None:
    """Processa áudio enviado para bot secundário"""
    start_time = time.perf_counter()
    bot = BotRepository.get_bot_by_id_sync(bot_id)
    if not bot or not bot.is_active:
        logger.info("Bot inativo para processamento de áudio", extra={"bot_id": bot_id})
        return

    media_type = media.get("type") or "voice"
    file_id = media.get("file_id")
    file_unique_id = media.get("file_unique_id") or file_id

    if not file_id or not file_unique_id:
        logger.warning(
            "Audio payload inválido",
            extra={"bot_id": bot_id, "user_id": user_id},
        )
        record_audio_failure(bot_id, "invalid_payload")
        return

    # Rate limit dedicado para áudios
    if not check_rate_limit(bot_id, user_id, action="audio:upload"):
        logger.info(
            "Audio rate limit reached",
            extra={"bot_id": bot_id, "user_id": user_id},
        )
        record_audio_failure(bot_id, "audio_rate_limit")
        return

    admin_id = int(getattr(bot, "admin_id", 0))
    bot_token_encrypted = getattr(bot, "token", None)
    if not isinstance(bot_token_encrypted, (bytes, bytearray)):
        logger.error(
            "Bot token inválido para áudio",
            extra={"bot_id": bot_id, "type": type(bot_token_encrypted).__name__},
        )
        record_audio_failure(bot_id, "token_missing")
        return

    try:
        preferences = AudioPreferencesService.get_preferences(admin_id)
        mode = AudioPreferenceMode.from_value(preferences.get("mode", "default"))
    except Exception as exc:  # pragma: no cover - proteção adicional
        logger.error(
            "Falha ao carregar preferências de áudio",
            extra={"bot_id": bot_id, "admin_id": admin_id, "error": str(exc)},
        )
        record_audio_failure(bot_id, "preferences_error")
        return

    logger.info(
        "Audio preferences loaded",
        extra={
            "bot_id": bot_id,
            "admin_id": admin_id,
            "mode": mode.value,
        },
    )

    if mode == AudioPreferenceMode.DEFAULT:
        reply = (
            preferences.get("default_reply")
            or AudioPreferencesService.get_default_reply()
        )
        _send_default_reply(bytes(bot_token_encrypted), chat_id, reply)
        return

    # Whisper ativo
    limits_payload = {
        "duration": media.get("duration"),
        "file_size": media.get("file_size"),
    }
    if _should_reject_media(limits_payload):
        record_audio_failure(bot_id, "media_limits")
        return

    ai_config = AIConfigRepository.get_by_bot_id_sync(bot_id)
    if not ai_config or not ai_config.is_enabled:
        logger.warning(
            "IA desativada para bot em modo Whisper",
            extra={"bot_id": bot_id, "user_id": user_id},
        )
        record_audio_failure(bot_id, "ai_disabled")
        return

    # Credit precheck (silent block)
    try:
        from services.credits.credit_service import CreditService

        if not CreditService.precheck_audio(bot_id, media.get("duration")):
            logger.info(
                "Audio processing blocked due to insufficient credits",
                extra={"bot_id": bot_id, "user": user_id},
            )
            record_audio_failure(bot_id, "credits")
            try:
                from services.credits.metrics import CREDITS_BLOCKED_TOTAL

                CREDITS_BLOCKED_TOTAL.labels(type="audio").inc()
            except Exception:
                pass
            return
    except Exception as e:  # pragma: no cover
        logger.error(
            "Credit precheck error (audio)",
            extra={"bot_id": bot_id, "error": str(e)},
        )

    cache_key = _get_cache_key(file_unique_id)
    cached_transcription = redis_client.get(cache_key)
    if cached_transcription:
        transcription = cached_transcription
    else:
        token = decrypt(bytes(bot_token_encrypted))
        audio_service = TelegramAudioService(token)
        try:
            audio_bytes = audio_service.fetch(file_id)
        except Exception as exc:  # pragma: no cover - falha de rede
            logger.error(
                "Falha ao baixar áudio do Telegram",
                extra={"bot_id": bot_id, "file_id": file_id, "error": str(exc)},
            )
            record_audio_failure(bot_id, "telegram_download_error")
            raise self.retry(exc=exc, countdown=2**self.request.retries)

        mime_type = _determine_mime_type(media_type, media.get("mime_type"))
        filename = _determine_filename(media_type, media.get("mime_type"))

        try:
            client = WhisperClient()
            transcription = client.transcribe(audio_bytes, filename, mime_type)
        except WhisperAPIError as exc:
            logger.error(
                "Transcrição Whisper falhou",
                extra={"bot_id": bot_id, "user_id": user_id, "error": str(exc)},
            )
            record_audio_failure(bot_id, "whisper_error")
            return

        redis_client.setex(cache_key, TRANSCRIPTION_CACHE_TTL, transcription)

    logger.info(
        "Áudio transcrito com sucesso",
        extra={"bot_id": bot_id, "user_id": user_id},
    )

    duration = time.perf_counter() - start_time
    record_audio_processing(
        bot_id=bot_id,
        media_type=media_type,
        duration_seconds=duration,
        cached=cached_transcription is not None,
    )

    # Debit credits based on duration (post‑usage)
    try:
        from services.credits.credit_service import CreditService as _CS

        deb = _CS.debit_audio(bot_id, media.get("duration"))
        try:
            from services.credits.metrics import CREDITS_DEBIT_CENTS_TOTAL

            CREDITS_DEBIT_CENTS_TOTAL.labels(type="audio").inc(int(deb or 0))
        except Exception:
            pass
    except Exception as e:  # pragma: no cover
        logger.error(
            "Credit debit failed (audio)",
            extra={"bot_id": bot_id, "error": str(e)},
        )

    # Enfileira IA para responder como se fosse mensagem do usuário
    from workers.ai_tasks import process_ai_message  # Import lazy para evitar ciclo
    from workers.mirror_tasks import mirror_message

    token = decrypt(bytes(bot_token_encrypted))
    process_ai_message.delay(
        bot_id=bot_id,
        user_telegram_id=user_id,
        text=transcription,
        photo_file_ids=[],
        bot_token=token,
    )

    mirror_message.delay(
        bot_id,
        user_id,
        {
            "role": "user",
            "content": transcription,
            "user_name": "Usuário (áudio)",
            "timestamp": media.get("timestamp") or time.time(),
        },
    )
