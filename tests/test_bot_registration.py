"""
Testes para serviço de registro de bots
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from database.models import Bot
from services.bot_registration import BotRegistrationService


class TestBotRegistrationService:
    """Testes para serviço de registro de bots"""

    @pytest.mark.asyncio
    async def test_register_new_bot(self, db_session):
        """Testa registro de novo bot"""
        with patch("services.bot_registration.verify_bot_token") as mock_verify:
            # Mock da verificação do token
            mock_verify.return_value = {
                "username": "newtestbot",
                "first_name": "New Test Bot",
            }

            # Registra bot
            bot_id = await BotRegistrationService.register_bot(
                admin_id=123456789,
                token="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
                display_name="My Bot",
            )

            assert bot_id is not None

            # Verifica que foi criado
            bot = db_session.query(Bot).filter_by(id=bot_id).first()
            assert bot is not None
            assert bot.username == "newtestbot"
            assert bot.admin_id == 123456789
            assert bot.is_active is True

    @pytest.mark.asyncio
    async def test_register_bot_invalid_token(self, db_session):
        """Testa registro com token inválido"""
        with patch("services.bot_registration.verify_bot_token") as mock_verify:
            # Simula token inválido
            mock_verify.side_effect = ValueError("Invalid token")

            # Deve levantar exceção
            with pytest.raises(ValueError):
                await BotRegistrationService.register_bot(
                    admin_id=123456789,
                    token="invalid_token",
                    display_name="My Bot",
                )

    @pytest.mark.asyncio
    async def test_register_duplicate_bot(self, db_session, sample_bot):
        """Testa registro de bot duplicado"""
        with patch("services.bot_registration.verify_bot_token") as mock_verify:
            # Mock retorna mesmo username do sample_bot
            mock_verify.return_value = {
                "username": sample_bot.username,
                "first_name": "Duplicate",
            }

            # Deve levantar exceção de bot duplicado
            with pytest.raises(ValueError, match="já está registrado"):
                await BotRegistrationService.register_bot(
                    admin_id=123456789,
                    token="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
                    display_name="Duplicate Bot",
                )

    @pytest.mark.asyncio
    async def test_list_bots(self, db_session):
        """Testa listagem de bots"""
        admin_id = 999888777

        # Cria bots
        for i in range(3):
            bot = Bot(
                admin_id=admin_id,
                username=f"listbot{i}",
                display_name=f"List Bot {i}",
                token=b"token",
                max_users=100,
            )
            db_session.add(bot)
        db_session.commit()

        # Lista
        bots = await BotRegistrationService.list_bots(admin_id)

        assert len(bots) == 3
        assert all(b.admin_id == admin_id for b in bots)

    @pytest.mark.asyncio
    async def test_deactivate_bot(self, db_session, sample_bot):
        """Testa desativação de bot"""
        success = await BotRegistrationService.deactivate_bot(
            admin_id=sample_bot.admin_id, bot_id=sample_bot.id
        )

        assert success is True

        # Verifica
        db_session.refresh(sample_bot)
        assert sample_bot.is_active is False

    @pytest.mark.asyncio
    async def test_deactivate_bot_unauthorized(self, db_session, sample_bot):
        """Testa desativação de bot por admin não autorizado"""
        wrong_admin = 999999999

        # Deve levantar exceção de permissão
        with pytest.raises(ValueError, match="permissão"):
            await BotRegistrationService.deactivate_bot(
                admin_id=wrong_admin, bot_id=sample_bot.id
            )

    @pytest.mark.asyncio
    async def test_activate_bot(self, db_session, sample_bot):
        """Testa reativação de bot"""
        # Desativa primeiro
        sample_bot.is_active = False
        db_session.commit()

        # Reativa
        success = await BotRegistrationService.activate_bot(
            admin_id=sample_bot.admin_id, bot_id=sample_bot.id
        )

        assert success is True

        # Verifica
        db_session.refresh(sample_bot)
        assert sample_bot.is_active is True

    @pytest.mark.asyncio
    async def test_activate_bot_unauthorized(self, db_session, sample_bot):
        """Testa reativação de bot por admin não autorizado"""
        wrong_admin = 999999999

        with pytest.raises(ValueError, match="permissão"):
            await BotRegistrationService.activate_bot(
                admin_id=wrong_admin, bot_id=sample_bot.id
            )

    @pytest.mark.asyncio
    async def test_get_bot_details(self, db_session, sample_bot):
        """Testa buscar detalhes de bot"""
        bot = await BotRegistrationService.get_bot_details(
            admin_id=sample_bot.admin_id, bot_id=sample_bot.id
        )

        assert bot is not None
        assert bot.id == sample_bot.id
        assert bot.username == sample_bot.username

    @pytest.mark.asyncio
    async def test_get_bot_details_unauthorized(self, db_session, sample_bot):
        """Testa buscar detalhes de bot sem permissão"""
        wrong_admin = 999999999

        with pytest.raises(ValueError, match="permissão"):
            await BotRegistrationService.get_bot_details(
                admin_id=wrong_admin, bot_id=sample_bot.id
            )


class TestBotRegistrationEdgeCases:
    """Testes de casos extremos do registro de bots"""

    @pytest.mark.asyncio
    async def test_register_bot_with_special_characters(self, db_session):
        """Testa registro de bot com caracteres especiais no nome"""
        with patch("services.bot_registration.verify_bot_token") as mock_verify:
            mock_verify.return_value = {
                "username": "special_bot_123",
                "first_name": "Special !@# Bot",
            }

            bot_id = await BotRegistrationService.register_bot(
                admin_id=123456789,
                token="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
                display_name="Bot !@#$%",
            )

            assert bot_id is not None

    @pytest.mark.asyncio
    async def test_register_bot_max_users_limit(self, db_session):
        """Testa registro com limite de usuários"""
        with patch("services.bot_registration.verify_bot_token") as mock_verify:
            mock_verify.return_value = {
                "username": "limitedbot",
                "first_name": "Limited Bot",
            }

            bot_id = await BotRegistrationService.register_bot(
                admin_id=123456789,
                token="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
                display_name="Limited Bot",
                max_users=10,
            )

            bot = db_session.query(Bot).filter_by(id=bot_id).first()
            assert bot.max_users == 10

    @pytest.mark.asyncio
    async def test_deactivate_nonexistent_bot(self, db_session):
        """Testa desativar bot que não existe"""
        with pytest.raises(ValueError, match="não encontrado"):
            await BotRegistrationService.deactivate_bot(
                admin_id=123456789, bot_id=999999
            )

    @pytest.mark.asyncio
    async def test_list_bots_empty(self, db_session):
        """Testa listar bots quando admin não tem nenhum"""
        bots = await BotRegistrationService.list_bots(admin_id=111222333)
        assert len(bots) == 0

    @pytest.mark.asyncio
    async def test_register_bot_very_long_display_name(self, db_session):
        """Testa registro com display_name muito longo"""
        with patch("services.bot_registration.verify_bot_token") as mock_verify:
            mock_verify.return_value = {
                "username": "longname_bot",
                "first_name": "Bot",
            }

            long_name = "A" * 500
            bot_id = await BotRegistrationService.register_bot(
                admin_id=123456789,
                token="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
                display_name=long_name,
            )

            bot = db_session.query(Bot).filter_by(id=bot_id).first()
            # Verificar se foi truncado conforme modelo


class TestBotRegistrationIntegration:
    """Testes de integração do registro de bots"""

    @pytest.mark.asyncio
    async def test_full_bot_lifecycle(self, db_session):
        """Testa ciclo de vida completo de um bot"""
        admin_id = 123456789

        with patch("services.bot_registration.verify_bot_token") as mock_verify:
            mock_verify.return_value = {
                "username": "lifecycle_bot",
                "first_name": "Lifecycle Bot",
            }

            # 1. Registra bot
            bot_id = await BotRegistrationService.register_bot(
                admin_id=admin_id,
                token="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
                display_name="Lifecycle Bot",
            )

            # 2. Verifica que está ativo
            bot = await BotRegistrationService.get_bot_details(admin_id, bot_id)
            assert bot.is_active is True

            # 3. Desativa
            await BotRegistrationService.deactivate_bot(admin_id, bot_id)
            db_session.refresh(bot)
            assert bot.is_active is False

            # 4. Reativa
            await BotRegistrationService.activate_bot(admin_id, bot_id)
            db_session.refresh(bot)
            assert bot.is_active is True

            # 5. Lista bots (deve aparecer)
            bots = await BotRegistrationService.list_bots(admin_id)
            bot_ids = [b.id for b in bots]
            assert bot_id in bot_ids

    @pytest.mark.asyncio
    async def test_multiple_admins_separate_bots(self, db_session):
        """Testa que bots de diferentes admins são separados"""
        admin1 = 111111
        admin2 = 222222

        with patch("services.bot_registration.verify_bot_token") as mock_verify:
            # Admin 1 registra bot
            mock_verify.return_value = {"username": "admin1_bot", "first_name": "Bot1"}
            bot1_id = await BotRegistrationService.register_bot(
                admin_id=admin1,
                token="token1",
                display_name="Admin1 Bot",
            )

            # Admin 2 registra bot
            mock_verify.return_value = {"username": "admin2_bot", "first_name": "Bot2"}
            bot2_id = await BotRegistrationService.register_bot(
                admin_id=admin2,
                token="token2",
                display_name="Admin2 Bot",
            )

        # Admin 1 vê apenas seu bot
        admin1_bots = await BotRegistrationService.list_bots(admin1)
        assert len(admin1_bots) == 1
        assert admin1_bots[0].id == bot1_id

        # Admin 2 vê apenas seu bot
        admin2_bots = await BotRegistrationService.list_bots(admin2)
        assert len(admin2_bots) == 1
        assert admin2_bots[0].id == bot2_id

        # Admin 1 não pode gerenciar bot do Admin 2
        with pytest.raises(ValueError):
            await BotRegistrationService.deactivate_bot(admin1, bot2_id)
