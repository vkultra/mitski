"""
Mirror Service - Gerencia espelhamento de conversas em grupos de tópicos
"""

import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

from core.redis_client import redis_client
from core.telemetry import logger
from database.models import Bot, MirrorBuffer, MirrorGroup, User, UserTopic
from database.repos import SessionLocal


class MirrorService:
    """Serviço de espelhamento de conversas"""

    # Configurações do .env
    MODE = os.getenv("MIRROR_MODE", "batch").lower()
    BATCH_SIZE = int(os.getenv("MIRROR_BATCH_SIZE", 5))
    BATCH_DELAY = int(os.getenv("MIRROR_BATCH_DELAY", 2))
    FLUSH_TIMEOUT = int(os.getenv("MIRROR_FLUSH_TIMEOUT", 3))
    MAX_BUFFER = int(os.getenv("MIRROR_MAX_BUFFER", 1000))
    PERSIST_BUFFERS = os.getenv("MIRROR_PERSIST_BUFFERS", "true").lower() == "true"
    RATE_LIMIT_ENABLED = (
        os.getenv("MIRROR_RATE_LIMIT_ENABLED", "true").lower() == "true"
    )
    RATE_LIMIT_MESSAGES = int(os.getenv("MIRROR_RATE_LIMIT_MESSAGES", 30))

    @classmethod
    def get_mirror_config(cls, bot_id: int) -> Optional[Dict]:
        """Obtém configuração de espelhamento do bot (com cache)"""
        cache_key = f"mirror_config:{bot_id}"

        # Tenta cache primeiro
        config_json = redis_client.get(cache_key)
        if config_json:
            return json.loads(config_json)

        # Busca no banco
        with SessionLocal() as session:
            mirror_group = (
                session.query(MirrorGroup)
                .filter_by(bot_id=bot_id, is_active=True)
                .first()
            )

            if not mirror_group:
                return None

            config = {
                "group_id": mirror_group.group_id,
                "batch_size": mirror_group.batch_size,
                "batch_delay": mirror_group.batch_delay,
                "flush_timeout": mirror_group.flush_timeout,
                "use_manager_bot": mirror_group.use_manager_bot,
                "manager_group_id": mirror_group.manager_group_id,
            }

            # Cache por 10 minutos
            redis_client.setex(cache_key, 600, json.dumps(config))

            return config

    @classmethod
    def get_or_create_topic(
        cls, bot_id: int, user_telegram_id: int, bot_token: str = None
    ) -> Optional[int]:
        """Obtém ou cria tópico para o usuário"""
        # Verifica cache primeiro
        cache_key = f"user_topic:{bot_id}:{user_telegram_id}"
        topic_id = redis_client.get(cache_key)
        if topic_id:
            return int(topic_id)

        with SessionLocal() as session:
            # Busca tópico existente
            user_topic = (
                session.query(UserTopic)
                .filter_by(bot_id=bot_id, user_telegram_id=user_telegram_id)
                .first()
            )

            if user_topic:
                # Cache por 5 minutos
                redis_client.setex(cache_key, 300, str(user_topic.topic_id))
                return user_topic.topic_id

            # Obtém configuração do grupo
            mirror_config = cls.get_mirror_config(bot_id)
            if not mirror_config:
                return None

            # Verifica se está em modo centralizado
            bot = session.query(Bot).filter_by(id=bot_id).first()
            if not bot:
                return None

            use_manager = mirror_config.get("use_manager_bot", False)

            if use_manager:
                # Modo centralizado - usa token do gerenciador
                bot_token = os.getenv("MANAGER_BOT_TOKEN")
                group_id = mirror_config.get(
                    "manager_group_id", mirror_config["group_id"]
                )

                # Nome do tópico inclui o bot de origem
                user = (
                    session.query(User)
                    .filter_by(bot_id=bot_id, telegram_id=user_telegram_id)
                    .first()
                )

                if not user:
                    return None

                topic_name = f"🤖 @{bot.username} - {user.first_name or 'Usuário'}"
            else:
                # Modo individual - mantém formato atual
                user = (
                    session.query(User)
                    .filter_by(bot_id=bot_id, telegram_id=user_telegram_id)
                    .first()
                )

                if not user:
                    return None

                topic_name = f"👤 {user.first_name or 'Usuário'}"
                if user.username:
                    topic_name += f" (@{user.username})"
                group_id = mirror_config["group_id"]

            try:
                # Cria tópico via API do Telegram
                response = requests.post(
                    f"https://api.telegram.org/bot{bot_token}/createForumTopic",
                    json={
                        "chat_id": group_id,
                        "name": topic_name[:128],  # Limite da API
                    },
                    timeout=10,
                )

                if response.status_code != 200:
                    logger.error(f"Failed to create topic: {response.text}")
                    return None

                data = response.json()
                if not data.get("ok"):
                    logger.error(f"Topic creation failed: {data}")
                    return None

                topic_id = data["result"]["message_thread_id"]

                # Salva no banco
                user_topic = UserTopic(
                    bot_id=bot_id,
                    user_telegram_id=user_telegram_id,
                    topic_id=topic_id,
                    is_banned=False,
                    is_ai_paused=False,
                )
                session.add(user_topic)
                session.commit()

                # Envia mensagem fixada com informações e botões
                cls._create_pinned_control_message(
                    bot_token, group_id, topic_id, user, bot_id, user_topic.id, session
                )

                # Cache
                redis_client.setex(cache_key, 300, str(topic_id))

                logger.info(f"Created topic {topic_id} for user {user_telegram_id}")
                return topic_id

            except Exception as e:
                logger.error(f"Error creating topic: {e}")
                return None

    @classmethod
    def _create_pinned_control_message(
        cls,
        bot_token: str,
        group_id: int,
        topic_id: int,
        user: User,
        bot_id: int,
        user_topic_id: int,
        session,
    ):
        """Cria mensagem fixada com controles"""
        bot = session.query(Bot).filter_by(id=bot_id).first()
        if not bot:
            return

        # Monta texto da mensagem
        text = (
            "📊 **INFORMAÇÕES DO USUÁRIO**\n"
            "─────────────────\n"
            f"👤 **Nome**: {user.first_name or 'N/A'} {user.last_name or ''}\n"
            f"🆔 **ID**: `{user.telegram_id}`\n"
            f"📱 **Username**: @{user.username or 'sem_username'}\n"
            f"🤖 **Bot**: @{bot.username}\n"
            f"📅 **Primeira interação**: {user.first_interaction.strftime('%d/%m/%Y %H:%M')}\n"
            "─────────────────\n"
            "⚙️ **CONTROLES**"
        )

        # Botões inline
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "🚫 Banir",
                        "callback_data": f"mirror_ban_{user_topic_id}",
                    },
                    {
                        "text": "✅ Desbanir",
                        "callback_data": f"mirror_unban_{user_topic_id}",
                    },
                ],
                [
                    {
                        "text": "🔄 Resetar Contexto",
                        "callback_data": f"mirror_reset_{user_topic_id}",
                    }
                ],
                [
                    {
                        "text": "⏸️ Pausar IA",
                        "callback_data": f"mirror_pause_ai_{user_topic_id}",
                    },
                    {
                        "text": "▶️ Retomar IA",
                        "callback_data": f"mirror_resume_ai_{user_topic_id}",
                    },
                ],
            ]
        }

        try:
            # Envia mensagem
            response = requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": group_id,
                    "message_thread_id": topic_id,
                    "text": text,
                    "parse_mode": "Markdown",
                    "reply_markup": keyboard,
                },
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    message_id = data["result"]["message_id"]

                    # Fixa mensagem
                    requests.post(
                        f"https://api.telegram.org/bot{bot_token}/pinChatMessage",
                        json={
                            "chat_id": group_id,
                            "message_id": message_id,
                            "disable_notification": True,
                        },
                        timeout=5,
                    )

                    # Atualiza no banco
                    user_topic = (
                        session.query(UserTopic).filter_by(id=user_topic_id).first()
                    )
                    if user_topic:
                        user_topic.pinned_message_id = message_id
                        session.commit()

        except Exception as e:
            logger.error(f"Error creating pinned message: {e}")

    @classmethod
    def is_user_banned(cls, bot_id: int, user_telegram_id: int) -> bool:
        """Verifica se usuário está banido (cache primeiro)"""
        cache_key = f"user_state:{bot_id}:{user_telegram_id}"

        # Verifica cache
        state = redis_client.hget(cache_key, "is_banned")
        if state is not None:
            return state == "1"

        # Busca no banco
        with SessionLocal() as session:
            user_topic = (
                session.query(UserTopic)
                .filter_by(bot_id=bot_id, user_telegram_id=user_telegram_id)
                .first()
            )

            if not user_topic:
                return False

            # Atualiza cache (5 minutos)
            redis_client.hset(
                cache_key, "is_banned", "1" if user_topic.is_banned else "0"
            )
            redis_client.expire(cache_key, 300)

            return user_topic.is_banned

    @classmethod
    def is_ai_paused(cls, bot_id: int, user_telegram_id: int) -> bool:
        """Verifica se IA está pausada para o usuário"""
        cache_key = f"user_state:{bot_id}:{user_telegram_id}"

        # Verifica cache
        state = redis_client.hget(cache_key, "is_ai_paused")
        if state is not None:
            return state == "1"

        # Busca no banco
        with SessionLocal() as session:
            user_topic = (
                session.query(UserTopic)
                .filter_by(bot_id=bot_id, user_telegram_id=user_telegram_id)
                .first()
            )

            if not user_topic:
                return False

            # Atualiza cache
            redis_client.hset(
                cache_key, "is_ai_paused", "1" if user_topic.is_ai_paused else "0"
            )
            redis_client.expire(cache_key, 300)

            return user_topic.is_ai_paused

    @classmethod
    def add_to_buffer(cls, bot_id: int, user_telegram_id: int, message: Dict) -> bool:
        """Adiciona mensagem ao buffer"""
        buffer_key = f"buffer:{bot_id}:{user_telegram_id}"

        try:
            # Adiciona mensagem ao buffer
            message_json = json.dumps(message)
            redis_client.rpush(f"{buffer_key}:messages", message_json)

            # Atualiza contador
            count = redis_client.hincrby(buffer_key, "count", 1)

            # Se primeira mensagem, salva timestamp
            if count == 1:
                redis_client.hset(buffer_key, "first_message_time", str(time.time()))

            # Verifica se deve fazer flush
            if count >= cls.BATCH_SIZE:
                return True  # Sinaliza para fazer flush

            # Define TTL do buffer
            redis_client.expire(buffer_key, cls.FLUSH_TIMEOUT + 5)
            redis_client.expire(f"{buffer_key}:messages", cls.FLUSH_TIMEOUT + 5)

            # Persiste no banco se configurado
            if cls.PERSIST_BUFFERS:
                cls._persist_buffer_message(bot_id, user_telegram_id, message)

            return False

        except Exception as e:
            logger.error(f"Error adding to buffer: {e}")
            return False

    @classmethod
    def _persist_buffer_message(cls, bot_id: int, user_telegram_id: int, message: Dict):
        """Persiste mensagem no banco como backup"""
        try:
            with SessionLocal() as session:
                # Busca buffer existente ou cria novo
                buffer = (
                    session.query(MirrorBuffer)
                    .filter_by(
                        bot_id=bot_id,
                        user_telegram_id=user_telegram_id,
                        status="pending",
                    )
                    .first()
                )

                if buffer:
                    # Adiciona à lista existente
                    messages = json.loads(buffer.messages)
                    messages.append(message)
                    buffer.messages = json.dumps(messages)
                    buffer.message_count = len(messages)
                else:
                    # Cria novo buffer
                    buffer = MirrorBuffer(
                        bot_id=bot_id,
                        user_telegram_id=user_telegram_id,
                        messages=json.dumps([message]),
                        message_count=1,
                        status="pending",
                        scheduled_flush=datetime.now()
                        + timedelta(seconds=cls.FLUSH_TIMEOUT),
                    )
                    session.add(buffer)

                session.commit()

        except Exception as e:
            logger.error(f"Error persisting buffer: {e}")

    @classmethod
    def get_buffer_messages(cls, bot_id: int, user_telegram_id: int) -> List[Dict]:
        """Obtém mensagens do buffer"""
        buffer_key = f"buffer:{bot_id}:{user_telegram_id}"
        messages_key = f"{buffer_key}:messages"

        try:
            # Obtém todas as mensagens
            messages_raw = redis_client.lrange(messages_key, 0, -1)
            messages = [json.loads(msg) for msg in messages_raw]

            # Limpa buffer após obter
            redis_client.delete(buffer_key, messages_key)

            return messages

        except Exception as e:
            logger.error(f"Error getting buffer messages: {e}")
            return []

    @classmethod
    def format_batch_message(cls, messages: List[Dict]) -> str:
        """Formata batch de mensagens para envio"""
        if not messages:
            return ""

        # Obtém timestamps
        start_time = messages[0].get("timestamp", time.time())
        end_time = messages[-1].get("timestamp", time.time())

        start_dt = datetime.fromtimestamp(start_time)
        end_dt = datetime.fromtimestamp(end_time)

        # Cabeçalho
        text = f"💬 **Conversa** ({start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')})\n"
        text += "─" * 20 + "\n\n"

        # Mensagens
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Trunca mensagens muito longas
            if len(content) > 500:
                content = content[:497] + "..."

            if role == "user":
                name = msg.get("user_name", "Usuário")
                text += f"👤 **{name}**: {content}\n\n"
            else:
                text += f"🤖 **Bot**: {content}\n\n"

        text += "─" * 20

        return text

    @classmethod
    def check_rate_limit(cls, bot_id: int) -> bool:
        """Verifica rate limit do espelhamento"""
        if not cls.RATE_LIMIT_ENABLED:
            return True

        key = f"mirror_rate:{bot_id}"
        current = redis_client.incr(key)

        if current == 1:
            redis_client.expire(key, 1)  # 1 segundo de janela

        return current <= cls.RATE_LIMIT_MESSAGES

    @classmethod
    def update_user_state(
        cls,
        bot_id: int,
        user_telegram_id: int,
        is_banned: Optional[bool] = None,
        is_ai_paused: Optional[bool] = None,
    ):
        """Atualiza estado do usuário"""
        cache_key = f"user_state:{bot_id}:{user_telegram_id}"

        # Atualiza cache imediatamente
        if is_banned is not None:
            redis_client.hset(cache_key, "is_banned", "1" if is_banned else "0")
        if is_ai_paused is not None:
            redis_client.hset(cache_key, "is_ai_paused", "1" if is_ai_paused else "0")

        redis_client.expire(cache_key, 300)

        # Atualiza banco
        with SessionLocal() as session:
            user_topic = (
                session.query(UserTopic)
                .filter_by(bot_id=bot_id, user_telegram_id=user_telegram_id)
                .first()
            )

            if user_topic:
                if is_banned is not None:
                    user_topic.is_banned = is_banned
                if is_ai_paused is not None:
                    user_topic.is_ai_paused = is_ai_paused

                user_topic.updated_at = datetime.now()
                session.commit()

    @classmethod
    def reset_conversation_context(cls, bot_id: int, user_telegram_id: int):
        """Reseta contexto de conversa do usuário"""
        from database.models import ConversationHistory, UserAISession

        with SessionLocal() as session:
            # Remove histórico de conversa
            session.query(ConversationHistory).filter_by(
                bot_id=bot_id, user_telegram_id=user_telegram_id
            ).delete()

            # Reseta sessão de IA
            session.query(UserAISession).filter_by(
                bot_id=bot_id, user_telegram_id=user_telegram_id
            ).update({"message_count": 0, "current_phase_id": None})

            session.commit()

        # Limpa cache relacionado
        redis_client.delete(
            f"conversation:{bot_id}:{user_telegram_id}",
            f"ai_session:{bot_id}:{user_telegram_id}",
        )

        logger.info(f"Reset context for user {user_telegram_id} in bot {bot_id}")
