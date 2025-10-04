"""
Configuração do Celery para processamento assíncrono
"""
import os
from celery import Celery

celery_app = Celery(
    'telegram_workers',
    broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_acks_late=True,           # confirma após processar
    worker_prefetch_multiplier=1,  # pega 1 tarefa por vez
    task_track_started=True,
    task_time_limit=300,           # timeout de 5 minutos
    task_soft_time_limit=240       # aviso aos 4 minutos
)

# Importar tasks para registro
celery_app.autodiscover_tasks(['workers'])
