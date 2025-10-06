"""
Mirror Tasks - Tarefas assíncronas para espelhamento de conversas
"""

import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict

import requests

from core.redis_client import redis_client
from core.security import decrypt
from core.telemetry import logger
from database.models import MirrorBuffer, UserTopic
from database.repos import BotRepository, SessionLocal
from services.mirror import MirrorService

from .celery_app import celery_app


@celery_app.task(bind=True, max_retries=3)
def mirror_message(self, bot_id: int, user_telegram_id: int, message: Dict):
    """
    Roteia mensagem para espelhamento baseado no modo configurado
    """
    try:
        logger.info(
            "Mirror message task received",
            extra={
                "bot_id": bot_id,
                "user_telegram_id": user_telegram_id,
                "message_role": message.get("role"),
                "message_preview": message.get("content", "")[:50],
            },
        )

        # Verifica se usuário está banido
        if MirrorService.is_user_banned(bot_id, user_telegram_id):
            logger.info(
                "User banned, skipping mirror",
                extra={"bot_id": bot_id, "user_telegram_id": user_telegram_id},
            )
            return

        # Verifica configuração de espelhamento
        mirror_config = MirrorService.get_mirror_config(bot_id)
        if not mirror_config:
            logger.warning(
                "No mirror config found for bot - espelhamento não configurado",
                extra={"bot_id": bot_id, "user_telegram_id": user_telegram_id},
            )
            return

        logger.info(
            "Mirror config loaded",
            extra={
                "bot_id": bot_id,
                "use_manager_bot": mirror_config.get("use_manager_bot"),
                "group_id": mirror_config.get("group_id"),
                "manager_group_id": mirror_config.get("manager_group_id"),
            },
        )

        # Roteamento baseado no modo
        mode = os.getenv("MIRROR_MODE", "batch").lower()

        if mode == "realtime":
            # Modo realtime - envia imediatamente
            logger.info(f"Routing to realtime mode for bot {bot_id}")
            send_to_mirror_topic.delay(bot_id, user_telegram_id, message)
        else:
            # Modo batch - adiciona ao buffer
            logger.info(f"Routing to batch mode for bot {bot_id}")
            add_to_mirror_buffer.delay(bot_id, user_telegram_id, message)

    except Exception as e:
        logger.error(f"Error in mirror_message: {e}")
        self.retry(countdown=2**self.request.retries)


@celery_app.task(bind=True, max_retries=3, rate_limit="30/s")
def send_to_mirror_topic(self, bot_id: int, user_telegram_id: int, message: Dict):
    """
    Envia mensagem imediatamente ao tópico (modo realtime)
    """
    try:
        # Obtém configuração do grupo primeiro
        mirror_config = MirrorService.get_mirror_config(bot_id)
        if not mirror_config:
            return

        # Obtém bot
        bot = BotRepository.get_bot_by_id_sync(bot_id)
        if not bot:
            return

        # Decide qual token usar
        if mirror_config.get("use_manager_bot", False):
            # Modo centralizado - usa token do gerenciador
            bot_token = os.getenv("MANAGER_BOT_TOKEN")
            group_id = mirror_config.get("manager_group_id", mirror_config["group_id"])
        else:
            # Modo individual - usa token do próprio bot
            bot_token = decrypt(bot.token)
            group_id = mirror_config["group_id"]

        # Obtém ou cria tópico
        topic_id = MirrorService.get_or_create_topic(
            bot_id, user_telegram_id, bot_token
        )
        if not topic_id:
            logger.error(f"Failed to get/create topic for user {user_telegram_id}")
            return

        # Formata mensagem individual
        role = message.get("role", "user")
        content = message.get("content", "")
        timestamp = datetime.fromtimestamp(message.get("timestamp", time.time()))

        if role == "user":
            name = message.get("user_name", "Usuário")
            text = f"👤 **{name}** [{timestamp.strftime('%H:%M')}]:\n{content}"
        else:
            text = f"🤖 **Bot** [{timestamp.strftime('%H:%M')}]:\n{content}"

        # Envia mensagem
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": group_id,
                "message_thread_id": topic_id,
                "text": text,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )

        if response.status_code != 200:
            raise Exception(f"Failed to send message: {response.text}")

        # Atualiza métricas
        with SessionLocal() as session:
            user_topic = (
                session.query(UserTopic)
                .filter_by(bot_id=bot_id, user_telegram_id=user_telegram_id)
                .first()
            )
            if user_topic:
                user_topic.messages_mirrored += 1
                user_topic.last_batch_sent = datetime.now()
                session.commit()

    except Exception as e:
        logger.error(f"Error sending to mirror topic: {e}")
        self.retry(countdown=2**self.request.retries)


@celery_app.task(bind=True, max_retries=3)
def add_to_mirror_buffer(self, bot_id: int, user_telegram_id: int, message: Dict):
    """
    Adiciona mensagem ao buffer (modo batch)
    """
    try:
        # Adiciona timestamp se não tiver
        if "timestamp" not in message:
            message["timestamp"] = time.time()

        # Adiciona ao buffer
        should_flush = MirrorService.add_to_buffer(bot_id, user_telegram_id, message)

        if should_flush:
            # Buffer cheio, fazer flush imediato
            flush_buffer.delay(bot_id, user_telegram_id)
        else:
            # Agenda flush por timeout
            flush_timeout = int(os.getenv("MIRROR_FLUSH_TIMEOUT", 3))
            schedule_buffer_flush.apply_async(
                args=[bot_id, user_telegram_id], countdown=flush_timeout, queue="mirror"
            )

    except Exception as e:
        logger.error(f"Error adding to buffer: {e}")
        self.retry(countdown=2**self.request.retries)


@celery_app.task(bind=True, max_retries=3)
def flush_buffer(self, bot_id: int, user_telegram_id: int):
    """
    Envia batch de mensagens do buffer
    """
    try:
        # Verifica rate limit
        if not MirrorService.check_rate_limit(bot_id):
            # Reagenda para depois
            self.retry(countdown=1)
            return

        # Obtém mensagens do buffer
        messages = MirrorService.get_buffer_messages(bot_id, user_telegram_id)
        if not messages:
            logger.debug(f"No messages to flush for user {user_telegram_id}")
            return

        # Obtém configuração do grupo primeiro
        mirror_config = MirrorService.get_mirror_config(bot_id)
        if not mirror_config:
            return

        # Obtém bot
        bot = BotRepository.get_bot_by_id_sync(bot_id)
        if not bot:
            return

        # Decide qual token e grupo usar
        if mirror_config.get("use_manager_bot", False):
            # Modo centralizado - usa token do gerenciador
            bot_token = os.getenv("MANAGER_BOT_TOKEN")
            group_id = mirror_config.get("manager_group_id", mirror_config["group_id"])
        else:
            # Modo individual - usa token do próprio bot
            bot_token = decrypt(bot.token)
            group_id = mirror_config["group_id"]

        # Obtém ou cria tópico
        topic_id = MirrorService.get_or_create_topic(
            bot_id, user_telegram_id, bot_token
        )
        if not topic_id:
            logger.error(f"Failed to get/create topic for user {user_telegram_id}")
            return

        # Formata batch de mensagens
        text = MirrorService.format_batch_message(messages)

        # Envia mensagem agregada
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": group_id,
                "message_thread_id": topic_id,
                "text": text,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )

        if response.status_code != 200:
            raise Exception(f"Failed to send batch: {response.text}")

        # Atualiza métricas
        with SessionLocal() as session:
            user_topic = (
                session.query(UserTopic)
                .filter_by(bot_id=bot_id, user_telegram_id=user_telegram_id)
                .first()
            )
            if user_topic:
                user_topic.messages_mirrored += len(messages)
                user_topic.last_batch_sent = datetime.now()
                session.commit()

            # Marca buffer como enviado se estava persistido
            buffer = (
                session.query(MirrorBuffer)
                .filter_by(
                    bot_id=bot_id, user_telegram_id=user_telegram_id, status="pending"
                )
                .first()
            )
            if buffer:
                buffer.status = "sent"
                buffer.sent_at = datetime.now()
                session.commit()

        logger.info(f"Flushed {len(messages)} messages for user {user_telegram_id}")

        # Aguarda delay pós-flush configurado via .env (pacing global)
        delay = int(os.getenv("MIRROR_BATCH_DELAY", 2))
        time.sleep(delay)

    except Exception as e:
        logger.error(f"Error flushing buffer: {e}")
        self.retry(countdown=2**self.request.retries)


@celery_app.task
def schedule_buffer_flush(bot_id: int, user_telegram_id: int):
    """
    Verifica e agenda flush do buffer se ainda tiver mensagens
    """
    buffer_key = f"buffer:{bot_id}:{user_telegram_id}"

    # Verifica se buffer ainda existe e tem mensagens
    count = redis_client.hget(buffer_key, "count")
    if count and int(count) > 0:
        flush_buffer.delay(bot_id, user_telegram_id)


@celery_app.task
def recover_orphan_buffers():
    """
    Recupera buffers órfãos (executado no startup)
    """
    logger.info("Starting orphan buffer recovery...")

    recovered_redis = 0
    recovered_db = 0

    try:
        # 1. Recuperar buffers do Redis
        buffer_keys = redis_client.keys("buffer:*:*")

        for buffer_key in buffer_keys:
            # Extrai bot_id e user_id
            parts = buffer_key.split(":")
            if len(parts) != 3:
                continue

            bot_id = int(parts[1])
            user_telegram_id = int(parts[2])

            # Verifica idade do buffer
            first_time = redis_client.hget(buffer_key, "first_message_time")
            if first_time:
                age = time.time() - float(first_time)
                if age > 60:  # Mais de 1 minuto = órfão
                    logger.info(f"Recovering orphan Redis buffer: {buffer_key}")
                    flush_buffer.delay(bot_id, user_telegram_id)
                    recovered_redis += 1

        # 2. Recuperar buffers do banco
        with SessionLocal() as session:
            # Busca buffers pendentes antigos
            cutoff_time = datetime.now() - timedelta(minutes=5)
            orphan_buffers = (
                session.query(MirrorBuffer)
                .filter(
                    MirrorBuffer.status == "pending",
                    MirrorBuffer.created_at < cutoff_time,
                )
                .all()
            )

            for buffer in orphan_buffers:
                logger.info(f"Recovering orphan DB buffer: {buffer.id}")

                # Recria no Redis se não existir
                buffer_key = f"buffer:{buffer.bot_id}:{buffer.user_telegram_id}"
                if not redis_client.exists(buffer_key):
                    # Restaura mensagens
                    messages = json.loads(buffer.messages)
                    for msg in messages:
                        redis_client.rpush(f"{buffer_key}:messages", json.dumps(msg))
                    redis_client.hset(buffer_key, "count", str(len(messages)))

                # Agenda flush
                flush_buffer.delay(buffer.bot_id, buffer.user_telegram_id)
                recovered_db += 1

                # Marca como em processamento
                buffer.status = "sending"
                buffer.retry_count += 1

            session.commit()

    except Exception as e:
        logger.error(f"Error recovering orphan buffers: {e}")

    logger.info(
        f"Recovery complete: {recovered_redis} from Redis, {recovered_db} from DB"
    )

    return {"redis": recovered_redis, "database": recovered_db}


@celery_app.task
def flush_all_buffers():
    """
    Força flush de todos os buffers (usado no graceful shutdown)
    """
    logger.info("Flushing all buffers for graceful shutdown...")

    flushed = 0

    try:
        # Lista todos os buffers no Redis
        buffer_keys = redis_client.keys("buffer:*:*")

        for buffer_key in buffer_keys:
            # Extrai bot_id e user_id
            parts = buffer_key.split(":")
            if len(parts) != 3:
                continue

            bot_id = int(parts[1])
            user_telegram_id = int(parts[2])

            # Enfileira flush com alta prioridade
            flush_buffer.apply_async(
                args=[bot_id, user_telegram_id], priority=10, queue="mirror_high"
            )
            flushed += 1

        logger.info(f"Queued {flushed} buffers for flush")

    except Exception as e:
        logger.error(f"Error flushing all buffers: {e}")

    return flushed


@celery_app.task
def handle_mirror_control_action(
    action: str, bot_id: int, user_telegram_id: int, callback_id: str, admin_id: int
):
    """
    Processa ações dos botões de controle
    """
    try:
        if action == "ban":
            MirrorService.update_user_state(bot_id, user_telegram_id, is_banned=True)
            result = f"🚫 Usuário {user_telegram_id} foi banido"

        elif action == "unban":
            MirrorService.update_user_state(bot_id, user_telegram_id, is_banned=False)
            result = f"✅ Usuário {user_telegram_id} foi desbanido"

        elif action == "reset":
            MirrorService.reset_conversation_context(bot_id, user_telegram_id)
            result = f"🔄 Contexto de conversa resetado para usuário {user_telegram_id}"

        elif action == "pause_ai":
            MirrorService.update_user_state(bot_id, user_telegram_id, is_ai_paused=True)
            result = f"⏸️ IA pausada para usuário {user_telegram_id}"

        elif action == "resume_ai":
            MirrorService.update_user_state(
                bot_id, user_telegram_id, is_ai_paused=False
            )
            result = f"▶️ IA retomada para usuário {user_telegram_id}"

        else:
            result = f"❌ Ação desconhecida: {action}"

        logger.info(
            f"Mirror control action: {action} for user {user_telegram_id} by admin {admin_id}"
        )

        # Retorna resultado para callback
        return {"callback_id": callback_id, "text": result, "show_alert": True}

    except Exception as e:
        logger.error(f"Error handling mirror control action: {e}")
        return {
            "callback_id": callback_id,
            "text": f"❌ Erro ao processar ação: {str(e)}",
            "show_alert": True,
        }
