"""Testes de idempotência (locks Redis) para notificações de venda."""

from __future__ import annotations

from unittest.mock import patch

from core.notifications.dedup import (
    acquire_sale_lock,
    release_sale_lock,
)


def test_sale_lock_acquire_and_release(fake_redis):
    # Substitui o redis_client usado no módulo por nossa instância fake
    with patch("core.notifications.dedup.redis_client", fake_redis):
        tx = "tx-abc-123"

        # Primeiro acquire deve obter o lock
        assert acquire_sale_lock(tx) is True

        # Segundo acquire (sem liberar) deve falhar
        assert acquire_sale_lock(tx) is False

        # Release e acquire novamente deve funcionar
        release_sale_lock(tx)
        assert acquire_sale_lock(tx) is True

