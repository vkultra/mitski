"""Métricas Prometheus para o fluxo de notificações."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - usado somente para tipagem
    from prometheus_client import Counter
else:  # pragma: no cover
    try:
        from prometheus_client import Counter
    except ImportError:

        class Counter:  # type: ignore[override]
            def __init__(self, *_args: Any, **_kwargs: Any) -> None:
                return None

            def labels(self, *_args: Any, **_kwargs: Any) -> "Counter":
                return self

            def inc(self, *_args: Any, **_kwargs: Any) -> None:
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
