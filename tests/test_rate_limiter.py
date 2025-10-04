"""
Testes para rate limiter
"""
import pytest
from core.rate_limiter import check_rate_limit
from core.redis_client import redis_client


@pytest.fixture(autouse=True)
def cleanup_redis():
    """Limpa Redis antes de cada teste"""
    redis_client.flushdb()
    yield
    redis_client.flushdb()


def test_rate_limit_allows_within_limit():
    """Deve permitir requests dentro do limite"""
    bot_id, user_id = 1, 12345

    # Deve permitir até 30 requests em 60s (limite padrão)
    for i in range(30):
        assert check_rate_limit(bot_id, user_id) is True


def test_rate_limit_blocks_over_limit():
    """Deve bloquear quando excede o limite"""
    bot_id, user_id = 1, 12345

    # Preenche o limite
    for i in range(30):
        check_rate_limit(bot_id, user_id)

    # 31º request deve bloquear
    assert check_rate_limit(bot_id, user_id) is False


def test_rate_limit_different_users():
    """Rate limit deve ser independente por usuário"""
    bot_id = 1

    # User 1 enche o limite
    for i in range(30):
        check_rate_limit(bot_id, 12345)

    # User 2 ainda deve ter limite disponível
    assert check_rate_limit(bot_id, 67890) is True


def test_rate_limit_different_bots():
    """Rate limit deve ser independente por bot"""
    user_id = 12345

    # Bot 1 enche o limite
    for i in range(30):
        check_rate_limit(1, user_id)

    # Bot 2 ainda deve ter limite disponível
    assert check_rate_limit(2, user_id) is True


def test_custom_rate_limit():
    """Deve respeitar limites customizados"""
    bot_id, user_id = 1, 12345

    # Limite de 5 em 60s
    for i in range(5):
        assert check_rate_limit(bot_id, user_id, limit=5) is True

    # 6º request deve bloquear
    assert check_rate_limit(bot_id, user_id, limit=5) is False
