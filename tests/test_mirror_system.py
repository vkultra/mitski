"""
Testes para o sistema de espelhamento
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from core.redis_client import redis_client
from database.models import (
    Bot,
    MirrorBuffer,
    MirrorGlobalConfig,
    MirrorGroup,
    User,
    UserTopic,
)
from services.mirror import MirrorService
from workers.mirror_tasks import (
    add_to_mirror_buffer,
    flush_buffer,
    handle_mirror_control_action,
    mirror_message,
    recover_orphan_buffers,
)


class TestMirrorService:
    """Testes do serviço de espelhamento"""

    def test_get_mirror_config(self, db_session, sample_bot):
        """Testa obtenção de configuração de espelhamento"""
        # Cria configuração
        mirror_group = MirrorGroup(
            bot_id=sample_bot.id,
            group_id=-1001234567890,
            is_active=True,
            batch_size=5,
            batch_delay=2,
            flush_timeout=3,
        )
        db_session.add(mirror_group)
        db_session.commit()

        # Testa obtenção
        config = MirrorService.get_mirror_config(sample_bot.id)

        assert config is not None
        assert config["group_id"] == -1001234567890
        assert config["batch_size"] == 5
        assert config["batch_delay"] == 2
        assert config["flush_timeout"] == 3

    def test_mirror_config_cache(self, db_session, sample_bot):
        """Testa cache da configuração"""
        # Cria configuração
        mirror_group = MirrorGroup(
            bot_id=sample_bot.id, group_id=-1001234567890, is_active=True
        )
        db_session.add(mirror_group)
        db_session.commit()

        # Primeira chamada - busca do banco
        config1 = MirrorService.get_mirror_config(sample_bot.id)

        # Verifica se foi cacheado
        cache_key = f"mirror_config:{sample_bot.id}"
        cached = redis_client.get(cache_key)
        assert cached is not None

        # Segunda chamada - deve vir do cache
        with patch.object(db_session, "query") as mock_query:
            config2 = MirrorService.get_mirror_config(sample_bot.id)
            # Não deve ter consultado o banco
            mock_query.assert_not_called()

        assert config1 == config2

    def test_add_to_buffer(self, sample_bot, sample_user):
        """Testa adição de mensagens ao buffer"""
        message = {
            "role": "user",
            "content": "Test message",
            "user_name": "Test User",
            "timestamp": time.time(),
        }

        # Adiciona primeira mensagem
        should_flush = MirrorService.add_to_buffer(
            sample_bot.id, sample_user.telegram_id, message
        )
        assert should_flush is False

        # Verifica buffer no Redis
        buffer_key = f"buffer:{sample_bot.id}:{sample_user.telegram_id}"
        count = redis_client.hget(buffer_key, "count")
        assert count == "1"

        # Adiciona mais mensagens até atingir o limite
        for i in range(4):  # Assumindo BATCH_SIZE = 5
            should_flush = MirrorService.add_to_buffer(
                sample_bot.id, sample_user.telegram_id, message
            )

        # Última mensagem deve triggar flush
        assert should_flush is True

    def test_get_buffer_messages(self, sample_bot, sample_user):
        """Testa recuperação de mensagens do buffer"""
        messages = [
            {"role": "user", "content": f"Message {i}", "timestamp": time.time()}
            for i in range(3)
        ]

        # Adiciona mensagens ao buffer
        for msg in messages:
            MirrorService.add_to_buffer(sample_bot.id, sample_user.telegram_id, msg)

        # Recupera mensagens
        retrieved = MirrorService.get_buffer_messages(
            sample_bot.id, sample_user.telegram_id
        )

        assert len(retrieved) == 3
        assert retrieved[0]["content"] == "Message 0"
        assert retrieved[2]["content"] == "Message 2"

        # Buffer deve estar limpo após recuperação
        buffer_key = f"buffer:{sample_bot.id}:{sample_user.telegram_id}"
        assert not redis_client.exists(buffer_key)

    def test_format_batch_message(self):
        """Testa formatação de batch de mensagens"""
        messages = [
            {
                "role": "user",
                "content": "Olá",
                "user_name": "João",
                "timestamp": time.time(),
            },
            {
                "role": "bot",
                "content": "Olá João! Como posso ajudar?",
                "timestamp": time.time(),
            },
            {
                "role": "user",
                "content": "Quero saber sobre o produto",
                "user_name": "João",
                "timestamp": time.time(),
            },
        ]

        formatted = MirrorService.format_batch_message(messages)

        assert "💬 **Conversa**" in formatted
        assert "👤 **João**: Olá" in formatted
        assert "🤖 **Bot**: Olá João! Como posso ajudar?" in formatted
        assert "👤 **João**: Quero saber sobre o produto" in formatted

    def test_user_state_management(self, db_session, sample_bot, sample_user):
        """Testa gerenciamento de estado do usuário"""
        # Cria UserTopic
        user_topic = UserTopic(
            bot_id=sample_bot.id,
            user_telegram_id=sample_user.telegram_id,
            topic_id=123,
            is_banned=False,
            is_ai_paused=False,
        )
        db_session.add(user_topic)
        db_session.commit()

        # Testa ban
        MirrorService.update_user_state(
            sample_bot.id, sample_user.telegram_id, is_banned=True
        )
        assert (
            MirrorService.is_user_banned(sample_bot.id, sample_user.telegram_id) is True
        )

        # Testa pause IA
        MirrorService.update_user_state(
            sample_bot.id, sample_user.telegram_id, is_ai_paused=True
        )
        assert (
            MirrorService.is_ai_paused(sample_bot.id, sample_user.telegram_id) is True
        )

        # Testa unban
        MirrorService.update_user_state(
            sample_bot.id, sample_user.telegram_id, is_banned=False
        )
        assert (
            MirrorService.is_user_banned(sample_bot.id, sample_user.telegram_id)
            is False
        )

    def test_rate_limit(self, sample_bot):
        """Testa rate limiting do espelhamento"""
        # Simula múltiplas chamadas
        for i in range(30):
            result = MirrorService.check_rate_limit(sample_bot.id)
            assert result is True

        # Próxima chamada deve ser limitada (assumindo limite de 30/s)
        result = MirrorService.check_rate_limit(sample_bot.id)
        if MirrorService.RATE_LIMIT_ENABLED:
            assert result is False


class TestMirrorTasks:
    """Testes das tasks de espelhamento"""

    @patch("workers.mirror_tasks.MirrorService.get_mirror_config")
    @patch("workers.mirror_tasks.MirrorService.is_user_banned")
    @patch("workers.mirror_tasks.add_to_mirror_buffer.delay")
    def test_mirror_message_batch_mode(
        self, mock_add_buffer, mock_is_banned, mock_get_config, sample_bot, sample_user
    ):
        """Testa roteamento de mensagem no modo batch"""
        mock_is_banned.return_value = False
        mock_get_config.return_value = {"group_id": -1001234567890}

        with patch.dict("os.environ", {"MIRROR_MODE": "batch"}):
            message = {"role": "user", "content": "Test", "timestamp": time.time()}

            mirror_message(sample_bot.id, sample_user.telegram_id, message)

            # Deve ter chamado add_to_mirror_buffer
            mock_add_buffer.assert_called_once_with(
                sample_bot.id, sample_user.telegram_id, message
            )

    @patch("workers.mirror_tasks.MirrorService.get_mirror_config")
    @patch("workers.mirror_tasks.MirrorService.is_user_banned")
    @patch("workers.mirror_tasks.send_to_mirror_topic.delay")
    def test_mirror_message_realtime_mode(
        self, mock_send_topic, mock_is_banned, mock_get_config, sample_bot, sample_user
    ):
        """Testa roteamento de mensagem no modo realtime"""
        mock_is_banned.return_value = False
        mock_get_config.return_value = {"group_id": -1001234567890}

        with patch.dict("os.environ", {"MIRROR_MODE": "realtime"}):
            message = {"role": "user", "content": "Test", "timestamp": time.time()}

            mirror_message(sample_bot.id, sample_user.telegram_id, message)

            # Deve ter chamado send_to_mirror_topic
            mock_send_topic.assert_called_once_with(
                sample_bot.id, sample_user.telegram_id, message
            )

    def test_handle_mirror_control_action_ban(
        self, db_session, sample_bot, sample_user
    ):
        """Testa ação de banir usuário"""
        # Cria UserTopic
        user_topic = UserTopic(
            bot_id=sample_bot.id,
            user_telegram_id=sample_user.telegram_id,
            topic_id=123,
            is_banned=False,
        )
        db_session.add(user_topic)
        db_session.commit()

        # Executa ação de ban
        result = handle_mirror_control_action(
            "ban",
            sample_bot.id,
            sample_user.telegram_id,
            "callback_123",
            7443327757,  # Admin ID
        )

        assert "banido" in result["text"]
        assert result["show_alert"] is True

        # Verifica se foi banido
        assert (
            MirrorService.is_user_banned(sample_bot.id, sample_user.telegram_id) is True
        )

    def test_handle_mirror_control_action_reset(
        self, db_session, sample_bot, sample_user
    ):
        """Testa ação de resetar contexto"""
        # Cria UserTopic
        user_topic = UserTopic(
            bot_id=sample_bot.id, user_telegram_id=sample_user.telegram_id, topic_id=123
        )
        db_session.add(user_topic)
        db_session.commit()

        # Executa ação de reset
        result = handle_mirror_control_action(
            "reset",
            sample_bot.id,
            sample_user.telegram_id,
            "callback_123",
            7443327757,  # Admin ID
        )

        assert "resetado" in result["text"].lower()
        assert result["show_alert"] is True

    @patch("workers.mirror_tasks.redis_client")
    @patch("workers.mirror_tasks.SessionLocal")
    def test_recover_orphan_buffers(self, mock_session, mock_redis):
        """Testa recuperação de buffers órfãos"""
        # Simula buffers órfãos no Redis
        mock_redis.keys.return_value = ["buffer:1:123", "buffer:2:456"]
        mock_redis.hget.side_effect = [
            str(time.time() - 120),  # 2 minutos atrás
            str(time.time() - 180),  # 3 minutos atrás
        ]

        # Simula buffers órfãos no banco
        mock_db = MagicMock()
        mock_db.query().filter().all.return_value = [
            MagicMock(id=1, bot_id=1, user_telegram_id=123, messages="[]"),
            MagicMock(id=2, bot_id=2, user_telegram_id=456, messages="[]"),
        ]
        mock_session.return_value.__enter__.return_value = mock_db

        with patch("workers.mirror_tasks.flush_buffer.delay") as mock_flush:
            result = recover_orphan_buffers()

            # Deve ter recuperado 2 do Redis e 2 do banco
            assert result["redis"] == 2
            assert result["database"] == 2
            assert mock_flush.call_count == 4


class TestMirrorIntegration:
    """Testes de integração do sistema de espelhamento"""

    @patch("requests.post")
    @patch("workers.mirror_tasks.BotRepository.get_bot_by_id_sync")
    @patch("workers.mirror_tasks.MirrorService.get_or_create_topic")
    @patch("workers.mirror_tasks.MirrorService.get_mirror_config")
    def test_full_batch_flow(
        self, mock_config, mock_topic, mock_bot, mock_post, sample_bot, sample_user
    ):
        """Testa fluxo completo de batch"""
        # Configura mocks
        mock_config.return_value = {
            "group_id": -1001234567890,
            "batch_size": 3,
            "batch_delay": 1,
            "flush_timeout": 2,
        }
        mock_topic.return_value = 123
        mock_bot.return_value = sample_bot
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"ok": True}

        # Adiciona mensagens
        messages = [
            {"role": "user", "content": f"Msg {i}", "timestamp": time.time()}
            for i in range(3)
        ]

        for msg in messages:
            add_to_mirror_buffer(sample_bot.id, sample_user.telegram_id, msg)

        # Executa flush
        flush_buffer(sample_bot.id, sample_user.telegram_id)

        # Verifica se enviou para o Telegram
        mock_post.assert_called()
        call_args = mock_post.call_args
        assert call_args[1]["json"]["chat_id"] == -1001234567890
        assert call_args[1]["json"]["message_thread_id"] == 123
        assert "Msg 0" in call_args[1]["json"]["text"]
        assert "Msg 2" in call_args[1]["json"]["text"]


class TestCentralizedMode:
    """Testes do modo centralizado"""

    def test_centralized_config_creation(self, db_session):
        """Testa criação de configuração global centralizada"""
        admin_id = 7443327757

        # Cria configuração global
        global_config = MirrorGlobalConfig(
            admin_id=admin_id,
            use_centralized_mode=True,
            manager_group_id=-1001234567890,
            is_active=True,
            batch_size=5,
            batch_delay=2,
            flush_timeout=3,
        )
        db_session.add(global_config)
        db_session.commit()

        # Verifica criação
        config = (
            db_session.query(MirrorGlobalConfig).filter_by(admin_id=admin_id).first()
        )

        assert config is not None
        assert config.use_centralized_mode is True
        assert config.manager_group_id == -1001234567890
        assert config.batch_size == 5

    def test_mirror_group_centralized_mode(self, db_session, sample_bot):
        """Testa configuração de MirrorGroup para modo centralizado"""
        # Cria MirrorGroup com modo centralizado
        mirror_group = MirrorGroup(
            bot_id=sample_bot.id,
            group_id=-1001111111111,  # Grupo individual (não usado)
            use_manager_bot=True,
            manager_group_id=-1001234567890,  # Grupo centralizado
            is_active=True,
        )
        db_session.add(mirror_group)
        db_session.commit()

        # Obtém configuração via MirrorService
        config = MirrorService.get_mirror_config(sample_bot.id)

        assert config is not None
        assert config["use_manager_bot"] is True
        assert config["manager_group_id"] == -1001234567890

    @patch("os.getenv")
    @patch("requests.post")
    def test_topic_creation_centralized_mode(
        self, mock_post, mock_getenv, db_session, sample_bot, sample_user
    ):
        """Testa criação de tópico em modo centralizado"""
        # Configura mocks
        mock_getenv.return_value = "manager_token_123"
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "ok": True,
            "result": {"message_thread_id": 999},
        }

        # Cria configuração centralizada
        mirror_group = MirrorGroup(
            bot_id=sample_bot.id,
            group_id=-1001111111111,
            use_manager_bot=True,
            manager_group_id=-1001234567890,
            is_active=True,
        )
        db_session.add(mirror_group)
        db_session.commit()

        # Tenta criar tópico
        topic_id = MirrorService.get_or_create_topic(
            sample_bot.id, sample_user.telegram_id
        )

        # Verifica chamadas
        mock_getenv.assert_called_with("MANAGER_BOT_TOKEN")
        mock_post.assert_called()

        # Verifica parâmetros da chamada
        call_args = mock_post.call_args
        assert "manager_token_123" in call_args[0][0]  # Token do gerenciador
        assert call_args[1]["json"]["chat_id"] == -1001234567890  # Grupo centralizado

        # Verifica nome do tópico (deve incluir nome do bot)
        topic_name = call_args[1]["json"]["name"]
        assert "@" in topic_name  # Deve ter username do bot
        assert sample_bot.username in topic_name
        assert sample_user.first_name in topic_name

    @patch("os.getenv")
    @patch("workers.mirror_tasks.BotRepository.get_bot_by_id_sync")
    @patch("workers.mirror_tasks.MirrorService.get_or_create_topic")
    @patch("workers.mirror_tasks.MirrorService.get_mirror_config")
    @patch("requests.post")
    def test_send_message_centralized_mode(
        self,
        mock_post,
        mock_config,
        mock_topic,
        mock_bot,
        mock_getenv,
        sample_bot,
        sample_user,
    ):
        """Testa envio de mensagem em modo centralizado"""
        # Configura mocks
        mock_getenv.return_value = "manager_token_123"
        mock_config.return_value = {
            "group_id": -1001111111111,
            "use_manager_bot": True,
            "manager_group_id": -1001234567890,
        }
        mock_topic.return_value = 999
        mock_bot.return_value = sample_bot
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"ok": True}

        # Envia mensagem
        from workers.mirror_tasks import send_to_mirror_topic

        message = {
            "role": "user",
            "content": "Test centralized",
            "timestamp": time.time(),
        }

        send_to_mirror_topic(sample_bot.id, sample_user.telegram_id, message)

        # Verifica uso do token do gerenciador
        mock_getenv.assert_called_with("MANAGER_BOT_TOKEN")

        # Verifica envio para grupo centralizado
        call_args = mock_post.call_args
        assert "manager_token_123" in call_args[0][0]
        assert call_args[1]["json"]["chat_id"] == -1001234567890

    def test_isolation_by_admin(self, db_session):
        """Testa isolamento de configurações por administrador"""
        # Cria configurações para 2 admins diferentes
        admin1_config = MirrorGlobalConfig(
            admin_id=111111,
            use_centralized_mode=True,
            manager_group_id=-1001111111111,
            is_active=True,
        )

        admin2_config = MirrorGlobalConfig(
            admin_id=222222,
            use_centralized_mode=True,
            manager_group_id=-1001222222222,
            is_active=True,
        )

        db_session.add_all([admin1_config, admin2_config])
        db_session.commit()

        # Verifica isolamento
        config1 = (
            db_session.query(MirrorGlobalConfig).filter_by(admin_id=111111).first()
        )
        config2 = (
            db_session.query(MirrorGlobalConfig).filter_by(admin_id=222222).first()
        )

        assert config1.manager_group_id != config2.manager_group_id
        assert config1.admin_id != config2.admin_id

        # Verifica que cada admin só vê sua configuração
        all_configs = db_session.query(MirrorGlobalConfig).all()
        assert len(all_configs) == 2

        # Cada configuração é única por admin
        admin_ids = [c.admin_id for c in all_configs]
        assert len(set(admin_ids)) == len(admin_ids)  # Sem duplicatas
