"""
Rate Limiter distribuído usando Redis
"""

import json
import os
import time

from core.redis_client import redis_client

# Carrega limites do ambiente
RATE_LIMITS = json.loads(
    os.environ.get("RATE_LIMITS_JSON", '{"default":{"limit":30,"window":60}}')
)


def check_rate_limit(
    bot_id: int,
    user_id: int,
    action: str = "default",
    limit: int = None,
    window: int = None,
) -> bool:
    """
    Verifica rate limit usando janela deslizante

    Args:
        bot_id: ID do bot
        user_id: ID do usuário
        action: Tipo de ação (default, cmd:/start, cb:action, etc)
        limit: Número máximo de requests (override)
        window: Janela em segundos (override)

    Returns:
        True se dentro do limite, False se excedeu
    """
    # Pega limites da configuração ou usa padrões
    config = RATE_LIMITS.get(action, RATE_LIMITS.get("default", {}))
    limit = limit or config.get("limit", 30)
    window = window or config.get("window", 60)

    now = int(time.time())
    key = f"rl:{bot_id}:{user_id}:{action}:{now // window}"

    with redis_client.pipeline() as pipe:
        pipe.incr(key, 1)
        pipe.expire(key, window + 5)
        result = pipe.execute()
        current_count = result[0]

    return current_count <= limit


def with_cooldown(bot_id: int, user_id: int, action: str, seconds: int = 3) -> bool:
    """
    Implementa cooldown para prevenir duplo clique

    Args:
        bot_id: ID do bot
        user_id: ID do usuário
        action: Identificador da ação
        seconds: Tempo de cooldown em segundos

    Returns:
        True se pode executar (não está em cooldown), False se ainda em cooldown
    """
    key = f"cd:{bot_id}:{user_id}:{action}"

    if redis_client.exists(key):
        return False

    redis_client.setex(key, seconds, "1")
    return True


def with_lock(key: str, ttl: int = 5):
    """
    Decorator para lock distribuído em operações críticas

    Args:
        key: Chave do lock
        ttl: Tempo de vida do lock em segundos

    Usage:
        @with_lock("payment:{user_id}", ttl=10)
        def process_payment(user_id):
            ...
    """

    def decorator(fn):
        def wrapper(*args, **kwargs):
            lock_key = f"lock:{key}"

            # Tenta adquirir lock
            if not redis_client.setnx(lock_key, "1"):
                return {"error": "operation in progress"}

            redis_client.expire(lock_key, ttl)

            try:
                return fn(*args, **kwargs)
            finally:
                redis_client.delete(lock_key)

        return wrapper

    return decorator
