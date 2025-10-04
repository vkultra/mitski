"""
Configurações da aplicação usando Pydantic
"""

from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configurações globais da aplicação"""

    # Ambiente
    APP_ENV: str = "dev"

    # Bot Gerenciador
    MANAGER_BOT_TOKEN: str = ""
    TELEGRAM_WEBHOOK_SECRET: str = ""
    WEBHOOK_BASE_URL: str = "http://localhost:8000"

    # Database & Queue
    DB_URL: str = "postgresql+psycopg://admin:senha_segura@localhost:5432/telegram_bots"
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Security
    ENCRYPTION_KEY: str = ""
    ALLOWED_ADMIN_IDS: str = ""

    # Monitoring
    LOG_LEVEL: str = "INFO"
    SENTRY_DSN: str = ""

    # Rate Limits
    RATE_LIMITS_JSON: str = '{"default":{"limit":30,"window":60}}'

    # Connection Pools
    REDIS_MAX_CONNECTIONS: int = 100
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40

    # Circuit Breaker
    CIRCUIT_BREAKER_FAIL_MAX: int = 5
    CIRCUIT_BREAKER_TIMEOUT: int = 60

    # Grok API (xAI)
    XAI_API_KEY: str = ""
    GROK_API_BASE_URL: str = "https://api.x.ai/v1"
    GROK_TIMEOUT: int = 30

    # IA Features
    AI_HISTORY_LIMIT: int = 7  # mensagens (7 pares user+assistant = 14 total)
    AI_DEFAULT_TEMPERATURE: float = 0.7
    AI_MAX_TOKENS: int = 2000
    AI_RATE_LIMIT_PER_MINUTE: int = 480

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignora campos extras do .env

    @property
    def allowed_admin_ids_list(self) -> List[int]:
        """Retorna lista de IDs de admins permitidos"""
        if not self.ALLOWED_ADMIN_IDS:
            return []
        return [int(x) for x in self.ALLOWED_ADMIN_IDS.split(",") if x.strip()]


settings = Settings()
