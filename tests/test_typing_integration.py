"""
Testes de integração para o typing effect em todos os componentes
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.config import settings


class TestTypingEffectIntegration:
    """Testes de integração do typing effect com todos os componentes"""

    @pytest.mark.asyncio
    async def test_ai_message_with_split(self):
        """Testa mensagem de IA com divisão por |"""
        from services.typing_effect import TypingEffectService

        messages = TypingEffectService.split_message(
            "Olá, como vai? | Espero que esteja bem | Posso ajudá-lo?"
        )

        assert len(messages) == 3
        assert messages[0] == "Olá, como vai?"
        assert messages[1] == "Espero que esteja bem"
        assert messages[2] == "Posso ajudá-lo?"

    @patch("workers.tasks.decrypt")
    @patch("workers.tasks.BotRepository")
    @patch("workers.api_clients.TelegramAPI")
    @patch("services.typing_effect.TypingEffectService")
    def test_send_message_task_integration(
        self, mock_typing_service, mock_api_class, mock_repo, mock_decrypt
    ):
        """Testa integração do send_message com typing effect"""
        from workers.tasks import send_message

        # Setup mocks
        mock_bot = MagicMock()
        mock_bot.token = "encrypted_token"
        mock_repo.get_bot_by_id_sync.return_value = mock_bot
        mock_decrypt.return_value = "decrypted_token"

        mock_api = MagicMock()
        mock_api_class.return_value = mock_api

        mock_typing_service.split_message.return_value = ["Test message"]
        mock_typing_service.apply_typing_effect_sync.return_value = None

        # Execute
        send_message(123, 456789, "Test message")

        # Verify
        mock_typing_service.split_message.assert_called_once_with("Test message")
        mock_typing_service.apply_typing_effect_sync.assert_called_once()
        mock_api.send_message_sync.assert_called_once_with(
            token="decrypted_token", chat_id=456789, text="Test message"
        )

    @patch("workers.tasks.decrypt")
    @patch("workers.tasks.BotRepository")
    @patch("workers.api_clients.TelegramAPI")
    @patch("services.typing_effect.TypingEffectService")
    def test_send_message_multiple_parts(
        self, mock_typing_service, mock_api_class, mock_repo, mock_decrypt
    ):
        """Testa envio de mensagem com múltiplas partes"""
        from workers.tasks import send_message

        # Setup mocks
        mock_bot = MagicMock()
        mock_bot.token = "encrypted_token"
        mock_repo.get_bot_by_id_sync.return_value = mock_bot
        mock_decrypt.return_value = "decrypted_token"

        mock_api = MagicMock()
        mock_api_class.return_value = mock_api

        mock_typing_service.split_message.return_value = ["Part 1", "Part 2", "Part 3"]
        mock_typing_service.apply_typing_effect_sync.return_value = None

        # Execute
        send_message(123, 456789, "Part 1 | Part 2 | Part 3")

        # Verify - deve ter chamado typing e send para cada parte
        assert mock_typing_service.apply_typing_effect_sync.call_count == 3
        assert mock_api.send_message_sync.call_count == 3

    @pytest.mark.asyncio
    async def test_pitch_sender_integration(self):
        """Testa integração com pitch sender"""
        from services.offers.pitch_sender import PitchSenderService

        with patch("services.offers.pitch_sender.OfferPitchRepository") as mock_repo:
            with patch("workers.api_clients.TelegramAPI") as mock_api_class:
                with patch("services.typing_effect.TypingEffectService") as mock_typing:
                    # Setup
                    mock_block = MagicMock()
                    mock_block.text = "Oferta especial!"
                    mock_block.media_file_id = None
                    mock_block.media_type = None
                    mock_block.delay_seconds = 3
                    mock_block.auto_delete_seconds = 0

                    # Use AsyncMock para métodos assíncronos
                    mock_repo.get_blocks_by_offer = AsyncMock(return_value=[mock_block])

                    mock_api = AsyncMock()
                    mock_api.send_message.return_value = {"result": {"message_id": 123}}
                    mock_api_class.return_value = mock_api

                    # Mock apply_typing_effect como async
                    mock_typing.apply_typing_effect = AsyncMock()

                    # Execute
                    sender = PitchSenderService("test_token")
                    result = await sender.send_pitch(
                        offer_id=1, chat_id=456789, preview_mode=False
                    )

                    # Verify - deve ter aplicado typing effect
                    mock_typing.apply_typing_effect.assert_called_once()

    @pytest.mark.asyncio
    async def test_action_sender_integration(self):
        """Testa integração com action sender"""
        from services.ai.actions.action_sender import ActionSenderService

        with patch(
            "services.ai.actions.action_sender.AIActionBlockRepository"
        ) as mock_repo:
            with patch("workers.api_clients.TelegramAPI") as mock_api_class:
                with patch("services.typing_effect.TypingEffectService") as mock_typing:
                    # Setup
                    mock_block = MagicMock()
                    mock_block.text = "Ação executada!"
                    mock_block.media_file_id = None
                    mock_block.media_type = None
                    mock_block.delay_seconds = 0
                    mock_block.auto_delete_seconds = 0

                    # Use AsyncMock para métodos assíncronos
                    mock_repo.get_blocks_by_action = AsyncMock(
                        return_value=[mock_block]
                    )

                    mock_api = AsyncMock()
                    mock_api.send_message.return_value = {"result": {"message_id": 456}}
                    mock_api_class.return_value = mock_api

                    # Mock apply_typing_effect como async
                    mock_typing.apply_typing_effect = AsyncMock()

                    # Execute
                    sender = ActionSenderService("test_token")
                    result = await sender.send_action_blocks(
                        action_id=1, chat_id=789012, preview_mode=False
                    )

                    # Verify
                    mock_typing.apply_typing_effect.assert_called_once()

    def test_typing_delays_configuration(self):
        """Testa se as configurações de delay estão corretas"""
        assert settings.TYPING_CHARS_PER_MINUTE == 80
        assert settings.MIN_TYPING_DELAY == 2.0
        assert settings.MAX_TYPING_DELAY == 7.0
        assert settings.TYPING_ACTION_INTERVAL == 4.0

    @pytest.mark.asyncio
    async def test_media_typing_effect(self):
        """Testa typing effect para diferentes tipos de mídia"""
        from services.typing_effect import TypingEffectService

        mock_api = AsyncMock()
        mock_api.send_chat_action = AsyncMock(return_value={"ok": True})

        # Teste com foto
        await TypingEffectService.apply_typing_effect(
            api=mock_api,
            token="test_token",
            chat_id=123,
            text="Legenda da foto",
            media_type="photo",
        )

        # Verifica que usou upload_photo ao invés de typing
        call_args = mock_api.send_chat_action.call_args
        assert call_args[1]["action"] == "upload_photo"

    def test_deliverable_sender_sync_integration(self):
        """Testa versão síncrona do deliverable sender"""
        from services.offers.deliverable_sender import DeliverableSender

        with patch(
            "services.offers.deliverable_sender.OfferDeliverableBlockRepository"
        ) as mock_repo:
            with patch("services.typing_effect.TypingEffectService") as mock_typing:
                # Setup
                mock_block = MagicMock()
                mock_block.text = "Conteúdo entregue"
                mock_block.media_file_id = None
                mock_block.media_type = None
                mock_block.delay_seconds = 2
                mock_block.auto_delete_seconds = 0

                mock_repo.get_blocks_by_offer_sync.return_value = [mock_block]

                # Mock apply_typing_effect_sync
                mock_typing.apply_typing_effect_sync = MagicMock()

                # Create sender and patch its telegram_api
                sender = DeliverableSender("test_token")

                # Mock the telegram_api.send_message_sync method
                with patch.object(
                    sender.telegram_api, "send_message_sync"
                ) as mock_send:
                    mock_send.return_value = {"result": {"message_id": 789}}

                    # Execute
                    result = sender.send_deliverable_sync(
                        offer_id=2, chat_id=345678, preview_mode=False
                    )

                    # Verify
                    mock_typing.apply_typing_effect_sync.assert_called_once()
                    assert 789 in result

    @pytest.mark.asyncio
    async def test_manual_verification_sender_integration(self):
        """Testa manual verification sender com typing effect"""
        from services.offers.manual_verification_sender import ManualVerificationSender

        with patch(
            "services.offers.manual_verification_sender.OfferManualVerificationBlockRepository"
        ) as mock_repo:
            with patch("services.typing_effect.TypingEffectService") as mock_typing:
                # Setup
                mock_block = MagicMock()
                mock_block.text = "Por favor, verifique o pagamento"
                mock_block.media_file_id = None
                mock_block.media_type = None
                mock_block.delay_seconds = 1
                mock_block.auto_delete_seconds = 0

                # Use AsyncMock para métodos assíncronos
                mock_repo.get_blocks_by_offer = AsyncMock(return_value=[mock_block])

                # Mock apply_typing_effect como async
                mock_typing.apply_typing_effect = AsyncMock()

                # Create sender and patch its telegram_api
                sender = ManualVerificationSender("test_token")

                # Mock the telegram_api.send_message method
                with patch.object(
                    sender.telegram_api, "send_message", new_callable=AsyncMock
                ) as mock_send:
                    mock_send.return_value = {"result": {"message_id": 999}}

                    # Execute
                    result = await sender.send_manual_verification(
                        offer_id=3, chat_id=987654
                    )

                    # Verify
                    mock_typing.apply_typing_effect.assert_called_once()
                    assert 999 in result
