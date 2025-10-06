# -*- coding: utf-8 -*-
"""
Testes para handlers de mensagens e callbacks
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestManagerHandlers:
    """Testes para handlers do bot manager"""

    @pytest.mark.asyncio
    async def test_handle_start(self):
        """Testa handler de /start"""
        from handlers.manager_handlers import handle_start

        # Mock settings para incluir o user_id nos admins permitidos
        with patch("handlers.manager_handlers.settings") as mock_settings:
            mock_settings.allowed_admin_ids_list = [123456789]

            result = await handle_start(user_id=123456789)

            assert "text" in result
            assert "keyboard" in result
            assert "Bot" in result["text"] or "bem-vindo" in result["text"].lower()

    @pytest.mark.asyncio
    async def test_handle_add_bot_menu(self):
        """Testa menu de adicionar bot"""
        from handlers.manager_handlers import handle_callback_add_bot

        # Mock settings para incluir o user_id nos admins permitidos
        with patch("handlers.manager_handlers.settings") as mock_settings:
            mock_settings.allowed_admin_ids_list = [123456789]

            result = await handle_callback_add_bot(user_id=123456789)

            assert "text" in result
            assert "token" in result["text"].lower() or "bot" in result["text"].lower()


class TestPauseHandlers:
    """Testes para handlers de pause/unpause"""

    @pytest.mark.asyncio
    async def test_handle_pause_menu(self, sample_bot):
        """Testa menu de pausar bots"""
        from handlers.manager_handlers import handle_pause_menu

        result = await handle_pause_menu(user_id=sample_bot.admin_id)

        assert "text" in result
        assert "keyboard" in result


class TestErrorHandling:
    """Testes para tratamento de erros nos handlers"""

    @pytest.mark.asyncio
    async def test_handle_invalid_bot_id(self):
        """Testa handler com bot_id invalido usando deactivate"""
        from handlers.manager_handlers import handle_deactivate

        # Mock settings para incluir o user_id nos admins permitidos
        with patch("handlers.manager_handlers.settings") as mock_settings:
            mock_settings.allowed_admin_ids_list = [123456789]

            # Bot que nao existe
            result = await handle_deactivate(user_id=123456789, bot_id=999999)

            # Deve retornar mensagem (string)
            assert isinstance(result, str)


class TestKeyboardGeneration:
    """Testes para geracao de teclados inline"""

    def test_keyboard_structure(self):
        """Testa estrutura basica de teclado inline"""
        keyboard = {
            "inline_keyboard": [
                [{"text": "Button 1", "callback_data": "btn1"}],
                [
                    {"text": "Button 2", "callback_data": "btn2"},
                    {"text": "Button 3", "callback_data": "btn3"},
                ],
            ]
        }

        assert "inline_keyboard" in keyboard
        assert isinstance(keyboard["inline_keyboard"], list)
        assert all(isinstance(row, list) for row in keyboard["inline_keyboard"])
        assert all(
            "text" in button and "callback_data" in button
            for row in keyboard["inline_keyboard"]
            for button in row
        )
