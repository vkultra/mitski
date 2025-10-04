"""
Testes para os clientes de API, incluindo sendChatAction
"""

import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from workers.api_clients import TelegramAPI


class TestTelegramAPI:
    """Testes para TelegramAPI"""

    @pytest.mark.asyncio
    async def test_send_chat_action_success(self):
        """Testa envio bem-sucedido de chat action"""
        api = TelegramAPI()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {"ok": True, "result": True}
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await api.send_chat_action(
                token="test_token",
                chat_id=123456,
                action="typing",
            )

            assert result == {"ok": True, "result": True}
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert "sendChatAction" in call_args[0][0]
            assert call_args[1]["json"]["chat_id"] == 123456
            assert call_args[1]["json"]["action"] == "typing"

    @pytest.mark.asyncio
    async def test_send_chat_action_all_types(self):
        """Testa todos os tipos de ação suportados"""
        api = TelegramAPI()
        action_types = [
            "typing",
            "upload_photo",
            "record_video",
            "upload_video",
            "record_voice",
            "upload_voice",
            "upload_document",
            "find_location",
            "record_video_note",
            "upload_video_note",
            "choose_sticker",
        ]

        for action in action_types:
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.json.return_value = {"ok": True}
                mock_response.raise_for_status = MagicMock()
                mock_client.post.return_value = mock_response
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                result = await api.send_chat_action(
                    token="test_token",
                    chat_id=123456,
                    action=action,
                )

                assert result == {"ok": True}
                call_args = mock_client.post.call_args
                assert call_args[1]["json"]["action"] == action

    def test_send_chat_action_sync_success(self):
        """Testa versão síncrona do sendChatAction"""
        api = TelegramAPI()

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {"ok": True, "result": True}
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__.return_value = mock_client
            mock_client.__exit__.return_value = None
            mock_client_class.return_value = mock_client

            result = api.send_chat_action_sync(
                token="test_token",
                chat_id=123456,
                action="typing",
            )

            assert result == {"ok": True, "result": True}
            mock_client.post.assert_called_once()

    def test_send_chat_action_sync_retry(self):
        """Testa retry em caso de erro de conexão"""
        api = TelegramAPI()

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            # Primeira tentativa falha, segunda sucede
            mock_response_success = MagicMock()
            mock_response_success.json.return_value = {"ok": True}
            mock_response_success.raise_for_status = MagicMock()

            mock_client.post.side_effect = [
                httpx.ConnectError("Connection failed"),
                mock_response_success,
            ]
            mock_client.__enter__.return_value = mock_client
            mock_client.__exit__.return_value = None
            mock_client_class.return_value = mock_client

            with patch("time.sleep"):  # Mock sleep para não esperar
                result = api.send_chat_action_sync(
                    token="test_token",
                    chat_id=123456,
                    action="typing",
                )

            assert result == {"ok": True}
            assert mock_client.post.call_count == 2

    def test_send_chat_action_sync_max_retries(self):
        """Testa falha após máximo de tentativas"""
        api = TelegramAPI()

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post.side_effect = httpx.ConnectError("Connection failed")
            mock_client.__enter__.return_value = mock_client
            mock_client.__exit__.return_value = None
            mock_client_class.return_value = mock_client

            with patch("time.sleep"):  # Mock sleep para não esperar
                with pytest.raises(httpx.ConnectError):
                    api.send_chat_action_sync(
                        token="test_token",
                        chat_id=123456,
                        action="typing",
                    )

            # Deve ter tentado 3 vezes
            assert mock_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_send_message_integration(self):
        """Testa integração do send_message existente"""
        api = TelegramAPI()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "ok": True,
                "result": {"message_id": 789},
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await api.send_message(
                token="test_token",
                chat_id=123456,
                text="Test message",
                parse_mode="Markdown",
            )

            assert result["ok"] is True
            assert result["result"]["message_id"] == 789
