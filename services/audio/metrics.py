"""Métricas Prometheus para processamento de áudios."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from prometheus_client import Counter, Histogram
else:  # pragma: no cover
    try:
        from prometheus_client import Counter, Histogram
    except ImportError:  # pragma: no cover

        class _NoopMetric:  # type: ignore[override]
            def __init__(self, *_args: Any, **_kwargs: Any) -> None:
                return None

            def labels(self, *_args: Any, **_kwargs: Any) -> "_NoopMetric":
                return self

            def inc(self, *_args: Any, **_kwargs: Any) -> None:
                return None

            def observe(self, *_args: Any, **_kwargs: Any) -> None:
                return None

        class Counter(_NoopMetric):  # type: ignore[override]
            pass

        class Histogram(_NoopMetric):  # type: ignore[override]
            pass


AUDIO_UPDATES_TOTAL = Counter(
    "audio_updates_total",
    "Quantidade de atualizações com mídia de áudio recebidas pelo webhook",
    labelnames=("bot_id", "media_type"),
)

AUDIO_TRANSCRIPTION_TOTAL = Counter(
    "audio_transcription_total",
    "Resultado do processamento de áudio (cache ou transcrição nova)",
    labelnames=("bot_id", "result"),
)

AUDIO_FAILURE_TOTAL = Counter(
    "audio_transcription_failures_total",
    "Falhas ao processar áudios recebidos",
    labelnames=("bot_id", "reason"),
)

AUDIO_PROCESSING_SECONDS = Histogram(
    "audio_processing_seconds",
    "Duração do processamento de áudios em segundos",
    labelnames=("bot_id", "media_type"),
)


def _to_label(value: int | str) -> str:
    return str(value)


def record_audio_update(bot_id: int, media_type: str) -> None:
    AUDIO_UPDATES_TOTAL.labels(bot_id=_to_label(bot_id), media_type=media_type).inc()


def record_audio_processing(
    bot_id: int, media_type: str, duration_seconds: float, cached: bool
) -> None:
    result = "cached" if cached else "success"
    AUDIO_TRANSCRIPTION_TOTAL.labels(bot_id=_to_label(bot_id), result=result).inc()
    AUDIO_PROCESSING_SECONDS.labels(
        bot_id=_to_label(bot_id), media_type=media_type
    ).observe(duration_seconds)


def record_audio_failure(bot_id: int, reason: str) -> None:
    AUDIO_FAILURE_TOTAL.labels(bot_id=_to_label(bot_id), reason=reason).inc()


__all__ = [
    "record_audio_failure",
    "record_audio_processing",
    "record_audio_update",
]
