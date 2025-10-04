"""
Testes abrangentes para o serviço de efeito de digitação
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.typing_effect import TypingEffectService


class TestTypingEffectService:
    """Testes para o TypingEffectService"""

    def test_calculate_typing_delay(self):
        """Testa cálculo de delay baseado no tamanho do texto"""
        # Texto vazio deve retornar delay mínimo
        assert TypingEffectService.calculate_typing_delay("") == 2.0

        # Texto curto (5 chars) - 5/1.33 = 3.75 segundos
        assert TypingEffectService.calculate_typing_delay("Hello") == 3.75

        # Texto médio (100 chars) - 100/1.33 = 75 segundos, mas limitado a 7.0
        text_100 = "a" * 100
        delay = TypingEffectService.calculate_typing_delay(text_100)
        assert delay == 7.0  # Máximo de 7 segundos

        # Texto longo (300 chars) - também retorna o máximo
        text_300 = "a" * 300
        delay = TypingEffectService.calculate_typing_delay(text_300)
        assert delay == 7.0

        # Texto muito longo (600+ chars) deve retornar delay máximo
        text_600 = "a" * 600
        delay = TypingEffectService.calculate_typing_delay(text_600)
        assert delay == 7.0

    def test_split_message(self):
        """Testa divisão de mensagens com separador |"""
        # Mensagem sem separador
        assert TypingEffectService.split_message("Hello world") == ["Hello world"]

        # Mensagem com um separador
        assert TypingEffectService.split_message("Hello | World") == ["Hello", "World"]

        # Mensagem com múltiplos separadores
        assert TypingEffectService.split_message("Part 1 | Part 2 | Part 3") == [
            "Part 1",
            "Part 2",
            "Part 3",
        ]

        # Mensagem com espaços extras
        assert TypingEffectService.split_message("  Hello  |  World  ") == [
            "Hello",
            "World",
        ]

        # Mensagem vazia
        assert TypingEffectService.split_message("") == []

        # Apenas separadores
        assert TypingEffectService.split_message("|||") == []

    def test_get_action_for_media(self):
        """Testa obtenção da ação correta para cada tipo de mídia"""
        assert TypingEffectService.get_action_for_media("photo") == "upload_photo"
        assert TypingEffectService.get_action_for_media("video") == "upload_video"
        assert TypingEffectService.get_action_for_media("audio") == "upload_audio"
        assert TypingEffectService.get_action_for_media("voice") == "upload_voice"
        assert TypingEffectService.get_action_for_media("document") == "upload_document"
        assert (
            TypingEffectService.get_action_for_media("animation") == "upload_document"
        )
        assert (
            TypingEffectService.get_action_for_media("video_note")
            == "upload_video_note"
        )
        assert TypingEffectService.get_action_for_media("location") == "find_location"
        assert TypingEffectService.get_action_for_media("sticker") == "choose_sticker"
        assert TypingEffectService.get_action_for_media("unknown") == "typing"
        assert TypingEffectService.get_action_for_media(None) == "typing"

    @pytest.mark.asyncio
    async def test_apply_typing_effect_short_delay(self):
        """Testa aplicação de efeito com delay curto"""
        mock_api = AsyncMock()
        mock_api.send_chat_action = AsyncMock(return_value={"ok": True})

        await TypingEffectService.apply_typing_effect(
            api=mock_api,
            token="test_token",
            chat_id=123,
            text="Hello",
            media_type=None,
        )

        # Deve ter chamado send_chat_action uma vez (delay < 4 segundos)
        mock_api.send_chat_action.assert_called_once_with(
            token="test_token",
            chat_id=123,
            action="typing",
        )

    @pytest.mark.asyncio
    async def test_apply_typing_effect_long_delay(self):
        """Testa aplicação de efeito com delay longo"""
        mock_api = AsyncMock()
        mock_api.send_chat_action = AsyncMock(return_value={"ok": True})

        # Texto longo para gerar delay > 4 segundos
        long_text = "a" * 400  # ~5 segundos de delay

        await TypingEffectService.apply_typing_effect(
            api=mock_api,
            token="test_token",
            chat_id=123,
            text=long_text,
            media_type=None,
        )

        # Deve ter chamado send_chat_action múltiplas vezes (delay > 4 segundos)
        assert mock_api.send_chat_action.call_count >= 2

    @pytest.mark.asyncio
    async def test_apply_typing_effect_with_media(self):
        """Testa efeito com diferentes tipos de mídia"""
        mock_api = AsyncMock()
        mock_api.send_chat_action = AsyncMock(return_value={"ok": True})

        await TypingEffectService.apply_typing_effect(
            api=mock_api,
            token="test_token",
            chat_id=123,
            text="Photo caption",
            media_type="photo",
        )

        mock_api.send_chat_action.assert_called_with(
            token="test_token",
            chat_id=123,
            action="upload_photo",
        )

    @pytest.mark.asyncio
    async def test_apply_typing_effect_custom_delay(self):
        """Testa efeito com delay customizado"""
        mock_api = AsyncMock()
        mock_api.send_chat_action = AsyncMock(return_value={"ok": True})

        start_time = time.time()
        await TypingEffectService.apply_typing_effect(
            api=mock_api,
            token="test_token",
            chat_id=123,
            text="Text",
            media_type=None,
            custom_delay=3.0,
        )
        elapsed = time.time() - start_time

        # Deve respeitar o delay customizado (3 segundos)
        assert 2.9 <= elapsed <= 3.2

    @pytest.mark.asyncio
    async def test_apply_typing_effect_error_handling(self):
        """Testa tratamento de erros no typing effect"""
        mock_api = AsyncMock()
        mock_api.send_chat_action = AsyncMock(side_effect=Exception("API Error"))

        # Não deve lançar exceção mesmo com erro na API
        await TypingEffectService.apply_typing_effect(
            api=mock_api,
            token="test_token",
            chat_id=123,
            text="Test",
            media_type=None,
        )

    def test_apply_typing_effect_sync(self):
        """Testa versão síncrona do typing effect"""
        mock_api = MagicMock()
        mock_api.send_chat_action_sync = MagicMock(return_value={"ok": True})

        TypingEffectService.apply_typing_effect_sync(
            api=mock_api,
            token="test_token",
            chat_id=123,
            text="Hello",
            media_type=None,
        )

        mock_api.send_chat_action_sync.assert_called_once_with(
            token="test_token",
            chat_id=123,
            action="typing",
        )

    def test_apply_typing_effect_sync_long_delay(self):
        """Testa versão síncrona com delay longo"""
        mock_api = MagicMock()
        mock_api.send_chat_action_sync = MagicMock(return_value={"ok": True})

        # Texto longo para gerar delay > 4 segundos
        long_text = "a" * 400  # ~5 segundos de delay

        with patch("time.sleep"):  # Mock sleep para não esperar de verdade
            TypingEffectService.apply_typing_effect_sync(
                api=mock_api,
                token="test_token",
                chat_id=123,
                text=long_text,
                media_type=None,
            )

        # Deve ter chamado múltiplas vezes
        assert mock_api.send_chat_action_sync.call_count >= 2

    @pytest.mark.asyncio
    async def test_send_messages_with_typing(self):
        """Testa envio de múltiplas mensagens com typing"""
        mock_api = AsyncMock()
        mock_api.send_chat_action = AsyncMock(return_value={"ok": True})

        messages = [
            ("First message", None),
            ("Second message with photo", "photo"),
            ("Third message", None),
        ]

        await TypingEffectService.send_messages_with_typing(
            api=mock_api,
            token="test_token",
            chat_id=123,
            messages=messages,
        )

        # Deve ter chamado send_chat_action para cada mensagem
        assert mock_api.send_chat_action.call_count >= 3

    @patch("services.typing_effect.settings")
    def test_custom_settings(self, mock_settings):
        """Testa uso de configurações customizadas"""
        mock_settings.TYPING_CHARS_PER_MINUTE = 120  # Mais rápido
        mock_settings.MIN_TYPING_DELAY = 1.0
        mock_settings.MAX_TYPING_DELAY = 5.0

        # Com 120 chars/min (2 chars/seg), 100 chars = 50 segundos
        # Mas limitado ao MAX de 5 segundos
        text_100 = "a" * 100
        delay = TypingEffectService.calculate_typing_delay(text_100)
        assert delay <= 5.0
