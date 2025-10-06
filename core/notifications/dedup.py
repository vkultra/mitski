"""Helpers de idempotência para notificações de venda."""

from __future__ import annotations

from typing import Optional

from core.redis_client import redis_client

SALE_LOCK_TTL_SECONDS = 120


def _build_sale_lock_key(transaction_id: str, provider: Optional[str]) -> str:
    provider_slug = provider or "default"
    return f"sale:notification:{provider_slug}:{transaction_id}"


def acquire_sale_lock(
    transaction_id: str,
    provider: Optional[str] = None,
    *,
    ttl_seconds: int = SALE_LOCK_TTL_SECONDS,
) -> bool:
    """Tenta adquirir um lock efêmero para a transação.

    Retorna ``True`` se o lock foi obtido, ``False`` se já estava em uso.
    """

    key = _build_sale_lock_key(transaction_id, provider)
    return bool(redis_client.set(key, "1", nx=True, ex=ttl_seconds))


def release_sale_lock(transaction_id: str, provider: Optional[str] = None) -> None:
    """Libera explicitamente o lock (boa prática após processamento)."""

    key = _build_sale_lock_key(transaction_id, provider)
    redis_client.delete(key)


__all__ = [
    "acquire_sale_lock",
    "release_sale_lock",
    "SALE_LOCK_TTL_SECONDS",
]
