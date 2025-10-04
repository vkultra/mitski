"""
Redis Connection Pool
"""
import os
import redis

redis_pool = redis.ConnectionPool(
    host=os.environ.get('REDIS_HOST', 'localhost'),
    port=int(os.environ.get('REDIS_PORT', 6379)),
    db=0,
    max_connections=int(os.environ.get('REDIS_MAX_CONNECTIONS', 100)),
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True
)

redis_client = redis.Redis(connection_pool=redis_pool)
