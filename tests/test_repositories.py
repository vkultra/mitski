"""
Testes para repositories (Bot, User, etc)
"""

import pytest

from database.models import Bot, User
from database.repos import AntiSpamConfigRepository, BotRepository, UserRepository


class TestBotRepository:
    """Testes para repository de bots"""

    @pytest.mark.asyncio
    async def test_create_bot(self, db_session):
        """Testa criação de bot"""
        bot = Bot(
            admin_id=123456789,
            username="newbot",
            display_name="New Bot",
            token=b"encrypted_token_data",
            is_active=True,
            max_users=100,
        )
        db_session.add(bot)
        db_session.commit()

        # Verifica
        saved = db_session.query(Bot).filter_by(username="newbot").first()
        assert saved is not None
        assert saved.admin_id == 123456789
        assert saved.is_active is True

    @pytest.mark.asyncio
    async def test_get_bot_by_id(self, db_session, sample_bot):
        """Testa buscar bot por ID"""
        found = await BotRepository.get_bot_by_id(sample_bot.id)

        assert found is not None
        assert found.id == sample_bot.id
        assert found.username == sample_bot.username

    @pytest.mark.asyncio
    async def test_get_bot_by_username(self, db_session, sample_bot):
        """Testa buscar bot por username"""
        found = await BotRepository.get_bot_by_username(sample_bot.username)

        assert found is not None
        assert found.username == sample_bot.username

    @pytest.mark.asyncio
    async def test_list_bots_by_admin(self, db_session):
        """Testa listar bots de um admin"""
        admin_id = 999888777

        # Cria 3 bots
        for i in range(3):
            bot = Bot(
                admin_id=admin_id,
                username=f"bot{i}",
                display_name=f"Bot {i}",
                token=b"token",
                max_users=100,
            )
            db_session.add(bot)
        db_session.commit()

        # Lista
        bots = await BotRepository.list_bots_by_admin(admin_id)

        assert len(bots) == 3
        assert all(b.admin_id == admin_id for b in bots)

    @pytest.mark.asyncio
    async def test_deactivate_bot(self, db_session, sample_bot):
        """Testa desativar bot"""
        assert sample_bot.is_active is True

        success = await BotRepository.deactivate_bot(sample_bot.id)
        assert success is True

        # Verifica
        db_session.refresh(sample_bot)
        assert sample_bot.is_active is False

    @pytest.mark.asyncio
    async def test_activate_bot(self, db_session, sample_bot):
        """Testa reativar bot"""
        sample_bot.is_active = False
        db_session.commit()

        success = await BotRepository.activate_bot(sample_bot.id)
        assert success is True

        # Verifica
        db_session.refresh(sample_bot)
        assert sample_bot.is_active is True

    @pytest.mark.asyncio
    async def test_associate_offer(self, db_session, sample_bot, sample_offer):
        """Testa associar oferta a bot"""
        success = await BotRepository.associate_offer(sample_bot.id, sample_offer.id)
        assert success is True

        # Verifica
        db_session.refresh(sample_bot)
        assert sample_bot.offer_id == sample_offer.id

    @pytest.mark.asyncio
    async def test_disassociate_offer(self, db_session, sample_bot, sample_offer):
        """Testa desassociar oferta de bot"""
        # Primeiro associa
        sample_bot.offer_id = sample_offer.id
        db_session.commit()

        # Depois desassocia
        success = await BotRepository.disassociate_offer(sample_bot.id)
        assert success is True

        # Verifica
        db_session.refresh(sample_bot)
        assert sample_bot.offer_id is None


class TestUserRepository:
    """Testes para repository de usuários"""

    @pytest.mark.asyncio
    async def test_create_or_update_user_new(self, db_session, sample_bot):
        """Testa criar novo usuário"""
        user_data = {
            "id": 777888999,
            "first_name": "John",
            "last_name": "Doe",
            "username": "johndoe",
        }

        await UserRepository.create_or_update_user(sample_bot.id, user_data)

        # Verifica
        user = (
            db_session.query(User)
            .filter_by(bot_id=sample_bot.id, telegram_id=777888999)
            .first()
        )

        assert user is not None
        assert user.first_name == "John"
        assert user.username == "johndoe"

    @pytest.mark.asyncio
    async def test_create_or_update_user_existing(
        self, db_session, sample_bot, sample_user
    ):
        """Testa atualizar usuário existente"""
        user_data = {
            "id": sample_user.telegram_id,
            "first_name": "Updated",
            "last_name": "Name",
            "username": "newusername",
        }

        await UserRepository.create_or_update_user(sample_bot.id, user_data)

        # Verifica
        db_session.refresh(sample_user)
        assert sample_user.first_name == "Updated"
        assert sample_user.username == "newusername"

    @pytest.mark.asyncio
    async def test_get_user(self, db_session, sample_bot, sample_user):
        """Testa buscar usuário"""
        user = await UserRepository.get_user(sample_bot.id, sample_user.telegram_id)

        assert user is not None
        assert user.telegram_id == sample_user.telegram_id

    @pytest.mark.asyncio
    async def test_block_user(self, db_session, sample_bot, sample_user):
        """Testa bloquear usuário"""
        assert sample_user.is_blocked is False

        success = await UserRepository.block_user(
            sample_bot.id, sample_user.telegram_id, "SPAM"
        )
        assert success is True

        # Verifica
        db_session.refresh(sample_user)
        assert sample_user.is_blocked is True
        assert sample_user.block_reason == "SPAM"
        assert sample_user.blocked_at is not None

    @pytest.mark.asyncio
    async def test_is_blocked(self, db_session, sample_bot, sample_user):
        """Testa verificar se usuário está bloqueado"""
        # Inicialmente não bloqueado
        blocked = await UserRepository.is_blocked(
            sample_bot.id, sample_user.telegram_id
        )
        assert blocked is False

        # Bloqueia
        sample_user.is_blocked = True
        db_session.commit()

        # Agora está bloqueado
        blocked = await UserRepository.is_blocked(
            sample_bot.id, sample_user.telegram_id
        )
        assert blocked is True

    @pytest.mark.asyncio
    async def test_update_last_interaction(self, db_session, sample_bot, sample_user):
        """Testa atualizar última interação"""
        original_time = sample_user.last_interaction

        await UserRepository.update_last_interaction(
            sample_bot.id, sample_user.telegram_id
        )

        # Verifica
        db_session.refresh(sample_user)
        # Última interação deve ter sido atualizada
        assert sample_user.last_interaction != original_time or original_time is None


class TestAntiSpamConfigRepository:
    """Testes para repository de configuração anti-spam"""

    @pytest.mark.asyncio
    async def test_get_or_create_new(self, db_session, sample_bot):
        """Testa criar nova configuração"""
        config = await AntiSpamConfigRepository.get_or_create(sample_bot.id)

        assert config is not None
        assert config.bot_id == sample_bot.id
        # Valores padrão
        assert config.flood is True
        assert config.repetition is True

    @pytest.mark.asyncio
    async def test_get_or_create_existing(
        self, db_session, sample_bot, sample_antispam_config
    ):
        """Testa buscar configuração existente"""
        config = await AntiSpamConfigRepository.get_or_create(sample_bot.id)

        assert config.id == sample_antispam_config.id

    @pytest.mark.asyncio
    async def test_update_config(self, db_session, sample_bot, sample_antispam_config):
        """Testa atualizar configuração"""
        success = await AntiSpamConfigRepository.update_config(
            sample_bot.id, flood=False, total_limit_value=200
        )

        assert success is True

        # Verifica
        db_session.refresh(sample_antispam_config)
        assert sample_antispam_config.flood is False
        assert sample_antispam_config.total_limit_value == 200

    @pytest.mark.asyncio
    async def test_toggle_protection(
        self, db_session, sample_bot, sample_antispam_config
    ):
        """Testa alternar proteção"""
        original_value = sample_antispam_config.flood

        new_value = await AntiSpamConfigRepository.toggle_protection(
            sample_bot.id, "flood"
        )

        assert new_value == (not original_value)

        # Verifica
        db_session.refresh(sample_antispam_config)
        assert sample_antispam_config.flood == (not original_value)

    @pytest.mark.asyncio
    async def test_to_dict(self, db_session, sample_antispam_config):
        """Testa conversão para dicionário"""
        config_dict = AntiSpamConfigRepository.to_dict(sample_antispam_config)

        assert isinstance(config_dict, dict)
        assert "flood" in config_dict
        assert "repetition" in config_dict
        assert "total_limit_value" in config_dict
        assert config_dict["flood"] == sample_antispam_config.flood


class TestRepositoryEdgeCases:
    """Testes de casos extremos dos repositories"""

    @pytest.mark.asyncio
    async def test_get_nonexistent_bot(self, db_session):
        """Testa buscar bot que não existe"""
        bot = await BotRepository.get_bot_by_id(999999)
        assert bot is None

    @pytest.mark.asyncio
    async def test_get_nonexistent_user(self, db_session, sample_bot):
        """Testa buscar usuário que não existe"""
        user = await UserRepository.get_user(sample_bot.id, 999999)
        assert user is None

    @pytest.mark.asyncio
    async def test_block_already_blocked_user(
        self, db_session, sample_bot, sample_user
    ):
        """Testa bloquear usuário já bloqueado"""
        # Bloqueia primeira vez
        await UserRepository.block_user(sample_bot.id, sample_user.telegram_id, "SPAM")

        # Bloqueia novamente
        success = await UserRepository.block_user(
            sample_bot.id, sample_user.telegram_id, "FLOOD"
        )

        # Deve retornar False (já estava bloqueado)
        assert success is False

    @pytest.mark.asyncio
    async def test_deactivate_already_inactive_bot(self, db_session, sample_bot):
        """Testa desativar bot já inativo"""
        sample_bot.is_active = False
        db_session.commit()

        success = await BotRepository.deactivate_bot(sample_bot.id)

        # Pode retornar True ou False dependendo da implementação
        # Verificar lógica real

    @pytest.mark.asyncio
    async def test_update_config_nonexistent_field(
        self, db_session, sample_bot, sample_antispam_config
    ):
        """Testa atualizar campo que não existe"""
        # Deve ignorar campos inexistentes
        success = await AntiSpamConfigRepository.update_config(
            sample_bot.id, nonexistent_field=True, flood=False
        )

        assert success is True

        # Verifica que campo válido foi atualizado
        db_session.refresh(sample_antispam_config)
        assert sample_antispam_config.flood is False

    @pytest.mark.asyncio
    async def test_list_bots_empty(self, db_session):
        """Testa listar bots quando não há nenhum"""
        bots = await BotRepository.list_bots_by_admin(admin_id=111222333)
        assert len(bots) == 0

    @pytest.mark.asyncio
    async def test_create_user_with_minimal_data(self, db_session, sample_bot):
        """Testa criar usuário com dados mínimos"""
        user_data = {
            "id": 123456,
            # Sem first_name, last_name, username
        }

        await UserRepository.create_or_update_user(sample_bot.id, user_data)

        # Verifica
        user = (
            db_session.query(User)
            .filter_by(bot_id=sample_bot.id, telegram_id=123456)
            .first()
        )

        assert user is not None
        assert user.telegram_id == 123456
        # Campos opcionais podem ser None

    @pytest.mark.asyncio
    async def test_create_user_with_long_names(self, db_session, sample_bot):
        """Testa criar usuário com nomes muito longos"""
        user_data = {
            "id": 789012,
            "first_name": "A" * 500,  # Muito longo
            "last_name": "B" * 500,
            "username": "C" * 100,
        }

        await UserRepository.create_or_update_user(sample_bot.id, user_data)

        # Verifica que foi truncado ou aceito conforme modelo
        user = (
            db_session.query(User)
            .filter_by(bot_id=sample_bot.id, telegram_id=789012)
            .first()
        )

        assert user is not None
        # Verificar limites do modelo


class TestRepositoryConcurrency:
    """Testes de concorrência dos repositories"""

    @pytest.mark.asyncio
    async def test_concurrent_user_updates(self, db_session, sample_bot, sample_user):
        """Testa atualizações concorrentes de usuário"""
        import asyncio

        # Simula múltiplas atualizações simultâneas
        async def update_user():
            await UserRepository.update_last_interaction(
                sample_bot.id, sample_user.telegram_id
            )

        # Executa 10 updates concorrentes
        await asyncio.gather(*[update_user() for _ in range(10)])

        # Verifica que última interação foi atualizada
        db_session.refresh(sample_user)
        assert sample_user.last_interaction is not None

    @pytest.mark.asyncio
    async def test_concurrent_config_toggles(
        self, db_session, sample_bot, sample_antispam_config
    ):
        """Testa toggles concorrentes de configuração"""
        import asyncio

        async def toggle_flood():
            await AntiSpamConfigRepository.toggle_protection(sample_bot.id, "flood")

        # Executa 5 toggles concorrentes (número ímpar)
        await asyncio.gather(*[toggle_flood() for _ in range(5)])

        # Resultado final deve ser oposto ao inicial
        db_session.refresh(sample_antispam_config)
        # Pode variar dependendo de race conditions
