"""Cliente para Whisper API (OpenAI) com retry e circuit breaker."""

from __future__ import annotations

import random
import time
from typing import Optional, cast

import httpx
from pybreaker import CircuitBreaker, CircuitBreakerError

from core.config import settings
from core.telemetry import logger

TRANSCRIPTION_PATH = "/audio/transcriptions"
MAX_RETRIES = 3
_JITTER = random.SystemRandom()


class WhisperAPIError(RuntimeError):
    """Erro ao chamar Whisper API"""


class WhisperClient:
    """Cliente simples para OpenAI Whisper via HTTP"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        self.api_key = api_key or settings.WHISPER_API_KEY
        self.api_base = api_base or settings.WHISPER_API_BASE
        self.model = model or settings.WHISPER_MODEL
        self.timeout = timeout or settings.WHISPER_TIMEOUT
        if not self.api_key:
            raise WhisperAPIError("WHISPER_API_KEY não configurado no ambiente")

        # pybreaker expects 'reset_timeout' (not 'timeout_duration')
        self.breaker = CircuitBreaker(
            fail_max=settings.CIRCUIT_BREAKER_FAIL_MAX,
            reset_timeout=settings.CIRCUIT_BREAKER_TIMEOUT,
        )

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str,
        mime_type: str,
        language: Optional[str] = None,
    ) -> str:
        last_error: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = self.breaker.call(
                    self._perform_request, audio_bytes, filename, mime_type, language
                )
                return cast(str, result)
            except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                last_error = exc
                retry_delay = (2 ** (attempt - 1)) + _JITTER.uniform(0.1, 0.5)
                status = None
                retry_after = None
                if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
                    status = exc.response.status_code
                    # Respeita Retry-After quando 429
                    if status == 429:
                        hdr = exc.response.headers.get("Retry-After")
                        try:
                            retry_after = float(hdr) if hdr is not None else None
                        except ValueError:
                            retry_after = None
                        if retry_after is not None:
                            retry_delay = max(retry_delay, retry_after)
                logger.warning(
                    "Whisper HTTP failure",
                    extra={
                        "attempt": attempt,
                        "status": status,
                        "retry_after": retry_after,
                        "error": str(exc),
                    },
                )
                time.sleep(retry_delay)
            except CircuitBreakerError as exc:
                last_error = exc
                logger.error("Whisper circuit breaker open", extra={"error": str(exc)})
                break
            except WhisperAPIError as exc:
                last_error = exc
                logger.warning(
                    "Whisper API business error",
                    extra={"attempt": attempt, "error": str(exc)},
                )
            # Non-HTTP/non-timeout errors already slept or broke; loop continues

        if last_error:
            raise WhisperAPIError(str(last_error)) from last_error
        raise WhisperAPIError("Falha desconhecida ao transcrever áudio")

    def _perform_request(
        self,
        audio_bytes: bytes,
        filename: str,
        mime_type: str,
        language: Optional[str],
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        files = {
            "file": (filename, audio_bytes, mime_type or "application/octet-stream"),
        }
        data = {
            "model": self.model,
            "response_format": "text",
            "temperature": "0",
        }
        if language:
            data["language"] = language

        logger.info(
            "Calling Whisper API",
            extra={"model": self.model, "bytes": len(audio_bytes)},
        )

        with httpx.Client(base_url=self.api_base, timeout=self.timeout) as client:
            response: httpx.Response = client.post(
                TRANSCRIPTION_PATH, headers=headers, data=data, files=files
            )
            response.raise_for_status()
            raw_text = response.text
            if not isinstance(raw_text, str):
                raise WhisperAPIError("Whisper retornou resposta inválida")
            text = raw_text.strip()
            if not text:
                raise WhisperAPIError("Whisper retornou resposta vazia")
            return text
