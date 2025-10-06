"""Métricas Prometheus para o fluxo de notificações."""

from __future__ import annotations

from typing import Dict

try:
    from prometheus_client import Counter
except ImportError:  # pragma: no cover - fallback para ambientes sem prometheus
    class Counter:  # type: ignore[override]
        def __init__(self, *_args, **_kwargs):
            pass

        def labels(self, *_args, **_kwargs):  # noqa: D401 - API compatível
            return self

        def inc(self, *_args, **_kwargs):
            return None


NOTIFICATIONS_ENQUEUED = Counter(
    "sale_notifications_enqueued_total",
    "Quantidade de notificações de venda enfileiradas",
    labelnames=("origin",),
)

NOTIFICATIONS_PROCESSED = Counter(
    "sale_notifications_processed_total",
    "Resultado final das notificações de venda",
    labelnames=("status",),
)


def inc_enqueued(origin: str) -> None:
    NOTIFICATIONS_ENQUEUED.labels(origin=origin).inc()


def inc_processed(status: str) -> None:
    NOTIFICATIONS_PROCESSED.labels(status=status).inc()


__all__ = [
    "inc_enqueued",
    "inc_processed",
]
