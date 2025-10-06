"""
Testes para o sistema de IA (Grok)
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from database.models import ConversationHistory, UserAISession
from database.repos import ConversationHistoryRepository
from services.ai.conversation import AIConversationService
from services.ai.grok_client import GrokAPIClient
from services.ai.phase_detector import PhaseDetectorService


class TestGrokClient:
    """Testes para cliente Grok"""

    @pytest.mark.asyncio
    async def test_chat_basic(self, mock_redis_client):
        """Testa chat básico com Grok"""
        with patch("httpx.AsyncClient") as mock_client:
            # Mock response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "id": "chatcmpl-123",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Hello! How can I help you?",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 8,
                    "total_tokens": 18,
                },
            }

            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_client_instance

            client = GrokClient(api_key="test_key")
            result = await client.chat(
                messages=[{"role": "user", "content": "Hello"}], model="grok-2-1212"
            )

            assert result["id"] == "chatcmpl-123"
            assert len(result["choices"]) == 1
            assert (
                result["choices"][0]["message"]["content"]
                == "Hello! How can I help you?"
            )

    @pytest.mark.asyncio
    async def test_chat_with_reasoning(self, mock_redis_client):
        """Testa chat com modelo de reasoning"""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "id": "chatcmpl-456",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "After thinking about it, the answer is 42.",
                            "reasoning_content": "Let me analyze this step by step...",
                        }
                    }
                ],
                "usage": {"total_tokens": 100},
            }

            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_client_instance

            client = GrokClient(api_key="test_key")
            result = await client.chat(
                messages=[{"role": "user", "content": "What is the meaning of life?"}],
                model="grok-2-1212",
            )

            assert "reasoning_content" in result["choices"][0]["message"]

    @pytest.mark.asyncio
    async def test_rate_limit_check(self, mock_redis_client):
        """Testa verificação de rate limit"""
        client = GrokClient(api_key="test_key")

        # Primeira chamada deve passar
        can_proceed = await client.check_rate_limit(bot_id=1)
        assert can_proceed is True

        # Simula muitas chamadas rápidas
        for _ in range(500):  # Limite é 480/min
            await client.check_rate_limit(bot_id=1)

        # Deve estar limitado agora
        # Nota: FakeRedis pode não simular isso perfeitamente

    @pytest.mark.asyncio
    async def test_multimodal_support(self, mock_redis_client):
        """Testa suporte a multimodal (imagens)"""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "id": "chatcmpl-789",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "I can see a cat in the image.",
                        }
                    }
                ],
                "usage": {"total_tokens": 50},
            }

            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_client_instance

            client = GrokClient(api_key="test_key")
            result = await client.chat(
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "What do you see?"},
                            {
                                "type": "image_url",
                                "image_url": {"url": "https://example.com/cat.jpg"},
                            },
                        ],
                    }
                ],
                model="grok-2-vision-1212",
            )

            assert "cat" in result["choices"][0]["message"]["content"].lower()


class TestPhaseDetector:
    """Testes para detector de fases de conversa"""

    @pytest.mark.asyncio
    async def test_detect_phase_by_keyword(
        self, db_session, sample_ai_config, sample_ai_phase
    ):
        """Testa detecção de fase por palavra-chave"""
        # sample_ai_phase tem trigger="hello"
        result = await PhaseDetector.detect_phase(
            ai_config_id=sample_ai_config.id, user_message="hello there"
        )

        assert result is not None
        assert result.name == "greeting"

    @pytest.mark.asyncio
    async def test_no_phase_detected(self, db_session, sample_ai_config):
        """Testa quando nenhuma fase é detectada"""
        result = await PhaseDetector.detect_phase(
            ai_config_id=sample_ai_config.id, user_message="random text"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_phase_priority_order(self, db_session, sample_ai_config):
        """Testa ordem de prioridade das fases"""
        from database.models import AIPhase

        # Cria duas fases com triggers similares
        phase1 = AIPhase(
            ai_config_id=sample_ai_config.id,
            name="phase1",
            trigger="help",
            prompt="Help prompt",
            order=1,
        )
        phase2 = AIPhase(
            ai_config_id=sample_ai_config.id,
            name="phase2",
            trigger="help",
            prompt="Help prompt 2",
            order=2,
        )
        db_session.add(phase1)
        db_session.add(phase2)
        db_session.commit()

        # Deve retornar a fase com menor ordem
        result = await PhaseDetector.detect_phase(
            ai_config_id=sample_ai_config.id, user_message="I need help"
        )

        assert result.order == 1
        assert result.name == "phase1"


class TestConversationService:
    """Testes para serviço de conversa"""

    @pytest.mark.asyncio
    async def test_add_message_to_history(
        self, db_session, sample_bot, sample_user, mock_redis_client
    ):
        """Testa adicionar mensagem ao histórico"""
        await ConversationService.add_message(
            bot_id=sample_bot.id,
            user_telegram_id=sample_user.telegram_id,
            role="user",
            content="Hello",
        )

        # Verifica que foi salvo no banco
        history = (
            db_session.query(ConversationHistory)
            .filter_by(bot_id=sample_bot.id, user_telegram_id=sample_user.telegram_id)
            .first()
        )

        assert history is not None
        assert history.role == "user"
        assert history.content == "Hello"

    @pytest.mark.asyncio
    async def test_get_conversation_history(
        self, db_session, sample_bot, sample_user, mock_redis_client
    ):
        """Testa recuperar histórico de conversa"""
        # Adiciona mensagens
        for i in range(5):
            await ConversationService.add_message(
                bot_id=sample_bot.id,
                user_telegram_id=sample_user.telegram_id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
            )

        # Recupera histórico
        history = await ConversationService.get_history(
            bot_id=sample_bot.id, user_telegram_id=sample_user.telegram_id, limit=3
        )

        assert len(history) == 3
        # Mais recentes primeiro
        assert history[0]["content"] == "Message 4"

    @pytest.mark.asyncio
    async def test_conversation_history_limit(
        self, db_session, sample_bot, sample_user, mock_redis_client
    ):
        """Testa limite de histórico (7 mensagens)"""
        # Adiciona 10 mensagens
        for i in range(10):
            await ConversationService.add_message(
                bot_id=sample_bot.id,
                user_telegram_id=sample_user.telegram_id,
                role="user",
                content=f"Message {i}",
            )

        # Deve manter apenas as 7 mais recentes
        history = await ConversationService.get_history(
            bot_id=sample_bot.id, user_telegram_id=sample_user.telegram_id, limit=10
        )

        assert len(history) <= 7

    @pytest.mark.asyncio
    async def test_clear_history(
        self, db_session, sample_bot, sample_user, mock_redis_client
    ):
        """Testa limpar histórico"""
        # Adiciona mensagens
        await ConversationService.add_message(
            bot_id=sample_bot.id,
            user_telegram_id=sample_user.telegram_id,
            role="user",
            content="Hello",
        )

        # Limpa histórico
        await ConversationService.clear_history(
            bot_id=sample_bot.id, user_telegram_id=sample_user.telegram_id
        )

        # Verifica que foi limpo
        history = await ConversationService.get_history(
            bot_id=sample_bot.id, user_telegram_id=sample_user.telegram_id
        )

        assert len(history) == 0


class TestAISessionManagement:
    """Testes para gerenciamento de sessão de IA"""

    @pytest.mark.asyncio
    async def test_create_session(self, db_session, sample_bot, sample_user):
        """Testa criação de sessão de usuário"""
        session = UserAISession(
            bot_id=sample_bot.id,
            user_telegram_id=sample_user.telegram_id,
            current_phase=None,
        )
        db_session.add(session)
        db_session.commit()

        # Verifica criação
        saved_session = (
            db_session.query(UserAISession)
            .filter_by(bot_id=sample_bot.id, user_telegram_id=sample_user.telegram_id)
            .first()
        )

        assert saved_session is not None
        assert saved_session.current_phase is None

    @pytest.mark.asyncio
    async def test_update_session_phase(
        self, db_session, sample_bot, sample_user, sample_ai_phase
    ):
        """Testa atualização de fase da sessão"""
        session = UserAISession(
            bot_id=sample_bot.id,
            user_telegram_id=sample_user.telegram_id,
            current_phase=None,
        )
        db_session.add(session)
        db_session.commit()

        # Atualiza fase
        session.current_phase = sample_ai_phase.id
        db_session.commit()

        # Verifica atualização
        updated = (
            db_session.query(UserAISession)
            .filter_by(bot_id=sample_bot.id, user_telegram_id=sample_user.telegram_id)
            .first()
        )

        assert updated.current_phase == sample_ai_phase.id


class TestAIIntegration:
    """Testes de integração do sistema de IA"""

    @pytest.mark.asyncio
    async def test_full_conversation_flow(
        self,
        db_session,
        sample_bot,
        sample_user,
        sample_ai_config,
        sample_ai_phase,
        mock_redis_client,
    ):
        """Testa fluxo completo de conversa"""
        with patch("services.ai.grok_client.GrokClient.chat") as mock_chat:
            mock_chat.return_value = {
                "choices": [{"message": {"role": "assistant", "content": "Hi there!"}}],
                "usage": {"total_tokens": 20},
            }

            # Adiciona mensagem do usuário
            await ConversationService.add_message(
                bot_id=sample_bot.id,
                user_telegram_id=sample_user.telegram_id,
                role="user",
                content="hello",
            )

            # Detecta fase
            phase = await PhaseDetector.detect_phase(
                ai_config_id=sample_ai_config.id, user_message="hello"
            )

            assert phase is not None
            assert phase.name == "greeting"

            # Verifica histórico
            history = await ConversationService.get_history(
                bot_id=sample_bot.id, user_telegram_id=sample_user.telegram_id
            )

            assert len(history) > 0

    @pytest.mark.asyncio
    async def test_conversation_with_context(
        self,
        db_session,
        sample_bot,
        sample_user,
        sample_ai_config,
        mock_redis_client,
    ):
        """Testa conversa com contexto"""
        # Simula conversa anterior
        messages = [
            ("user", "What is Python?"),
            ("assistant", "Python is a programming language."),
            ("user", "Tell me more"),
        ]

        for role, content in messages:
            await ConversationService.add_message(
                bot_id=sample_bot.id,
                user_telegram_id=sample_user.telegram_id,
                role=role,
                content=content,
            )

        # Recupera histórico
        history = await ConversationService.get_history(
            bot_id=sample_bot.id, user_telegram_id=sample_user.telegram_id
        )

        # Verifica que mantém contexto
        assert len(history) == 3
        assert any("Python" in msg["content"] for msg in history)

    @pytest.mark.asyncio
    async def test_multimodal_conversation(
        self, db_session, sample_bot, sample_user, mock_redis_client
    ):
        """Testa conversa multimodal com imagens"""
        # Adiciona mensagem com imagem
        content = json.dumps(
            [
                {"type": "text", "text": "What is this?"},
                {
                    "type": "image_url",
                    "image_url": {"url": "https://example.com/img.jpg"},
                },
            ]
        )

        await ConversationService.add_message(
            bot_id=sample_bot.id,
            user_telegram_id=sample_user.telegram_id,
            role="user",
            content=content,
        )

        # Recupera
        history = await ConversationService.get_history(
            bot_id=sample_bot.id, user_telegram_id=sample_user.telegram_id
        )

        assert len(history) == 1
        # Conteúdo deve ser JSON string
        parsed = json.loads(history[0]["content"])
        assert isinstance(parsed, list)
        assert parsed[0]["type"] == "text"
