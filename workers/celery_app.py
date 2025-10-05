"""
Configuração do Celery para processamento assíncrono
"""

import os

from celery import Celery

celery_app = Celery(
    "telegram_workers",
    broker=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,  # confirma após processar
    worker_prefetch_multiplier=10,  # pega 10 tarefas por vez (async tasks)
    task_track_started=True,
    task_time_limit=300,  # timeout de 5 minutos
    task_soft_time_limit=240,  # aviso aos 4 minutos
)

# Configurar rotas de tarefas para queues específicas
celery_app.conf.task_routes = {
    "workers.tasks.process_telegram_update": {"queue": "celery"},
    "workers.tasks.process_manager_update": {"queue": "celery"},
    "workers.tasks.ban_user_async": {"queue": "bans"},
    "workers.tasks.send_message": {"queue": "celery"},
    "workers.tasks.send_welcome": {"queue": "celery"},
    "workers.tasks.send_rate_limit_message": {"queue": "celery"},
    "workers.payment_tasks.*": {"queue": "celery"},
    "workers.ai_tasks.*": {"queue": "celery"},
    "workers.upsell_tasks.*": {"queue": "celery"},
}

# Configurar tarefas periódicas (Celery Beat)
celery_app.conf.beat_schedule = {
    "check-pending-upsells": {
        "task": "workers.upsell_tasks.check_pending_upsells",
        "schedule": 300.0,  # 5 minutos
    },
}

# Importar tasks para registro
celery_app.autodiscover_tasks(["workers"])

# Importar tasks explicitamente
from workers import ai_tasks  # noqa: F401, E402
from workers import payment_tasks  # noqa: F401, E402
from workers import upsell_tasks  # noqa: F401, E402
