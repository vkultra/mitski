"""
Configuração global do pytest
"""

from datetime import datetime
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fakeredis import FakeRedis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database.models import (
    AIPhase,
    Base,
    Bot,
    BotAIConfig,
    BotAntiSpamConfig,
    ConversationHistory,
    Offer,
    User,
)


@pytest.fixture(scope="session")
def db_engine():
    """Cria engine de teste"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """Cria sessão de teste"""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()

    # Mock SessionLocal para repositórios usarem a mesma sessão
    with patch("database.repos.SessionLocal") as repo_session_factory, patch(
        "database.notifications.repos.SessionLocal"
    ) as notification_session_factory:
        for factory in (repo_session_factory, notification_session_factory):
            factory.return_value.__enter__ = lambda self: session
            factory.return_value.__exit__ = lambda self, *args: None

        yield session

    session.rollback()
    session.close()
    # Limpa todas as tabelas após cada teste
    Base.metadata.drop_all(db_engine)
    Base.metadata.create_all(db_engine)


@pytest.fixture(scope="function")
def fake_redis():
    """Cria instância fake do Redis para testes"""
    redis = FakeRedis(decode_responses=True)
    yield redis
    redis.flushall()


@pytest.fixture(scope="function")
def sample_bot(db_session) -> Bot:
    """Cria bot de exemplo para testes"""
    bot = Bot(
        admin_id=123456789,
        username="testbot",
        display_name="Test Bot",
        token=b"encrypted_token",
        is_active=True,
    )
    db_session.add(bot)
    db_session.commit()
    db_session.refresh(bot)
    return bot


@pytest.fixture(scope="function")
def sample_user(db_session, sample_bot) -> User:
    """Cria usuário de exemplo para testes"""
    user = User(
        bot_id=sample_bot.id,
        telegram_id=987654321,
        username="testuser",
        first_name="Test",
        last_name="User",
        is_blocked=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def sample_offer(db_session, sample_bot) -> Offer:
    """Cria oferta de exemplo para testes"""
    offer = Offer(
        bot_id=sample_bot.id,
        name="Test Offer",
        value="R$ 99,90",
        is_active=True,
    )
    db_session.add(offer)
    db_session.commit()
    db_session.refresh(offer)
    return offer


@pytest.fixture(scope="function")
def sample_ai_config(db_session, sample_bot) -> BotAIConfig:
    """Cria configuração de AI de exemplo para testes"""
    config = BotAIConfig(
        bot_id=sample_bot.id,
        model_type="reasoning",
        general_prompt="You are a helpful assistant",
        is_enabled=True,
    )
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)
    return config


@pytest.fixture(scope="function")
def sample_ai_phase(db_session, sample_ai_config) -> AIPhase:
    """Cria fase de AI de exemplo para testes"""
    phase = AIPhase(
        ai_config_id=sample_ai_config.id,
        name="greeting",
        trigger="hello",
        prompt="Greet the user warmly",
        order=1,
    )
    db_session.add(phase)
    db_session.commit()
    db_session.refresh(phase)
    return phase


@pytest.fixture(scope="function")
def sample_antispam_config(db_session, sample_bot) -> BotAntiSpamConfig:
    """Cria configuração de anti-spam de exemplo para testes"""
    config = BotAntiSpamConfig(
        bot_id=sample_bot.id,
        dot_after_start=True,
        repetition=True,
        flood=True,
        links_mentions=True,
        short_messages=True,
        loop_start=True,
        total_limit=True,
        total_limit_value=100,
    )
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)
    return config


@pytest.fixture(scope="function")
def mock_telegram_api():
    """Cria mock da API do Telegram"""
    with patch("workers.api_clients.TelegramAPI") as mock:
        instance = mock.return_value
        instance.send_message_sync = Mock(return_value={"message_id": 123})
        instance.send_message = AsyncMock(return_value={"message_id": 123})
        instance.edit_message_sync = Mock(return_value=True)
        instance.edit_message = AsyncMock(return_value=True)
        instance.ban_chat_member_sync = Mock(return_value=True)
        instance.ban_chat_member = AsyncMock(return_value=True)
        instance.answer_callback_query_sync = Mock(return_value=True)
        instance.answer_callback_query = AsyncMock(return_value=True)
        yield instance


@pytest.fixture(scope="function")
def mock_grok_client():
    """Cria mock do cliente Grok"""
    with patch("services.ai.grok_client.GrokAPIClient") as mock:
        instance = mock.return_value
        instance.chat = AsyncMock(
            return_value={
                "id": "chatcmpl-123",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Hello! How can I help you?",
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 8,
                    "total_tokens": 18,
                },
            }
        )
        instance.check_rate_limit = AsyncMock(return_value=True)
        yield instance


@pytest.fixture(scope="function")
def mock_redis_client(fake_redis):
    """Cria mock do cliente Redis usando FakeRedis"""
    with patch("core.redis_client.redis_client", fake_redis):
        yield fake_redis


@pytest.fixture(scope="function")
def mock_telegram_webhook():
    """Mock para set_webhook do Telegram"""
    with patch(
        "workers.api_clients.TelegramAPI.set_webhook", new_callable=AsyncMock
    ) as mock:
        mock.return_value = None
        yield mock


@pytest.fixture(autouse=True)
def reset_db_session_factory():
    """Reset SessionLocal factory entre testes"""
    yield
    # Cleanup após cada teste


@pytest.fixture
def telegram_update():
    """Update básico do Telegram para testes"""
    return {
        "update_id": 123456789,
        "message": {
            "message_id": 1,
            "from": {
                "id": 987654321,
                "is_bot": False,
                "first_name": "Test",
                "last_name": "User",
                "username": "testuser",
            },
            "chat": {"id": 987654321, "type": "private"},
            "date": int(datetime.utcnow().timestamp()),
            "text": "Hello",
        },
    }


@pytest.fixture
def telegram_callback_query():
    """Callback query do Telegram para testes"""
    return {
        "update_id": 123456790,
        "callback_query": {
            "id": "123",
            "from": {
                "id": 987654321,
                "is_bot": False,
                "first_name": "Test",
                "username": "testuser",
            },
            "message": {
                "message_id": 1,
                "chat": {"id": 987654321, "type": "private"},
            },
            "data": "test_callback",
        },
    }
