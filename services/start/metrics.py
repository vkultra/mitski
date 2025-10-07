"""Métricas Prometheus para o fluxo de mensagem inicial."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
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


START_TEMPLATE_SCHEDULED = Counter(
    "start_template_scheduled_total",
    "Quantidade de envios /start agendados",
    labelnames=("result",),
)

START_TEMPLATE_DELIVERED = Counter(
    "start_template_delivered_total",
    "Resultado final do envio da mensagem inicial",
    labelnames=("status",),
)


def inc_scheduled(result: str) -> None:
    START_TEMPLATE_SCHEDULED.labels(result=result).inc()


def inc_delivered(status: str) -> None:
    START_TEMPLATE_DELIVERED.labels(status=status).inc()


__all__ = ["inc_scheduled", "inc_delivered"]
