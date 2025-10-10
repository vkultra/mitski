"""Credits metrics with safe no-op fallback if prometheus_client is missing."""

from __future__ import annotations

from typing import Any

try:  # pragma: no cover - optional dependency
    from prometheus_client import Counter
except Exception:  # pragma: no cover

    class _NoopMetric:
        def labels(self, *_args: Any, **_kwargs: Any) -> "_NoopMetric":
            return self

        def inc(self, *_args: Any, **_kwargs: Any) -> None:
            return None

        def observe(self, *_args: Any, **_kwargs: Any) -> None:
            return None

    class Counter(_NoopMetric):  # type: ignore[override]
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass


CREDITS_BLOCKED_TOTAL = Counter(
    "credits_blocked_total", "Total de bloqueios por saldo insuficiente", ["type"]
)

CREDITS_DEBIT_CENTS_TOTAL = Counter(
    "credits_debit_cents_total", "Total debitado em centavos", ["type"]
)

CREDITS_TOPUP_CREATED_TOTAL = Counter(
    "credits_topup_created_total", "Total de recargas iniciadas"
)

CREDITS_TOPUP_CREDITED_TOTAL = Counter(
    "credits_topup_credited_total", "Total de recargas creditadas"
)
