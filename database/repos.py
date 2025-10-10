"""
Repository Pattern para acesso ao banco
"""

import os
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import create_engine, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from core.telemetry import logger

from .models import Bot, BotAIConfig, Event, User

if TYPE_CHECKING:
    from .models import (
        AIAction,
        AIActionBlock,
        Offer,
        OfferDeliverable,
        OfferPitchBlock,
        StartTemplate,
        StartTemplateBlock,
        UserActionStatus,
    )

# Configuração do engine
engine = create_engine(
    os.environ.get(
        "DB_URL", "postgresql+psycopg://admin:senha_segura@localhost:5432/telegram_bots"
    ),
    pool_size=int(os.environ.get("DB_POOL_SIZE", 20)),
    max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", 40)),
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
)

SessionLocal = sessionmaker(bind=engine)


class BotRepository:
    """Repository para operações com Bot"""

    @staticmethod
    async def get_bot_by_id(bot_id: int) -> Optional[Bot]:
        """Busca bot por ID (async)"""
        with SessionLocal() as session:
            return session.query(Bot).filter(Bot.id == bot_id).first()

    @staticmethod
    def get_bot_by_id_sync(bot_id: int) -> Optional[Bot]:
        """Busca bot por ID (sync para workers)"""
        with SessionLocal() as session:
            return session.query(Bot).filter(Bot.id == bot_id).first()

    @staticmethod
    async def get_bot_by_username(username: str) -> Optional[Bot]:
        """Busca bot por username"""
        with SessionLocal() as session:
            return session.query(Bot).filter(Bot.username == username).first()

    @staticmethod
    async def get_bots_by_admin(admin_id: int) -> List[Bot]:
        """Lista todos os bots de um admin"""
        with SessionLocal() as session:
            return session.query(Bot).filter(Bot.admin_id == admin_id).all()

    @staticmethod
    async def create_bot(data: dict) -> Bot:
        """Cria novo bot"""
        with SessionLocal() as session:
            bot = Bot(**data)
            session.add(bot)
            session.commit()
            session.refresh(bot)
            return bot

    @staticmethod
    async def deactivate_bot(bot_id: int) -> bool:
        """Desativa bot e sua IA se configurada"""
        with SessionLocal() as session:
            bot = session.query(Bot).filter(Bot.id == bot_id).first()
            if bot:
                bot.is_active = False

                # Desativar IA se existir configuração
                ai_config = session.query(BotAIConfig).filter_by(bot_id=bot_id).first()
                if ai_config:
                    ai_config.is_enabled = False

                session.commit()
                return True
            return False

    @staticmethod
    async def activate_bot(bot_id: int) -> bool:
        """Reativa bot e sua IA se configurada"""
        with SessionLocal() as session:
            bot = session.query(Bot).filter(Bot.id == bot_id).first()
            if bot:
                bot.is_active = True

                # Ativar IA se existir configuração
                ai_config = session.query(BotAIConfig).filter_by(bot_id=bot_id).first()
                if ai_config:
                    ai_config.is_enabled = True

                session.commit()
                return True
            return False

    @staticmethod
    async def delete_bot(bot_id: int) -> bool:
        """Deleta bot e remove dependências sem CASCADE explícito."""
        with SessionLocal() as session:
            bot = session.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                return False

            session.query(Event).filter(Event.bot_id == bot_id).delete(
                synchronize_session=False
            )
            session.query(User).filter(User.bot_id == bot_id).delete(
                synchronize_session=False
            )

            session.delete(bot)
            session.commit()
            return True

    @staticmethod
    async def associate_offer(bot_id: int, offer_id: int) -> bool:
        """Associa oferta ao bot (1 bot = 1 oferta)"""
        from datetime import datetime

        with SessionLocal() as session:
            bot = session.query(Bot).filter(Bot.id == bot_id).first()
            if bot:
                bot.associated_offer_id = offer_id
                bot.updated_at = datetime.utcnow()
                session.commit()
                return True
            return False

    @staticmethod
    async def dissociate_offer(bot_id: int) -> bool:
        """Remove associação de oferta do bot"""
        from datetime import datetime

        with SessionLocal() as session:
            bot = session.query(Bot).filter(Bot.id == bot_id).first()
            if bot:
                bot.associated_offer_id = None
                bot.updated_at = datetime.utcnow()
                session.commit()
                return True
            return False

    @staticmethod
    async def get_associated_offer_id(bot_id: int) -> Optional[int]:
        """Retorna ID da oferta associada ao bot"""
        with SessionLocal() as session:
            bot = session.query(Bot).filter(Bot.id == bot_id).first()
            return bot.associated_offer_id if bot else None


class UserRepository:
    """Repository para operações com User"""

    @staticmethod
    async def get_or_create_user(telegram_id: int, bot_id: int, **kwargs) -> User:
        """Busca ou cria usuário"""
        with SessionLocal() as session:
            # Tenta localizar usuário pelo telegram_id (único na tabela)
            user = session.query(User).filter(User.telegram_id == telegram_id).first()

            if user:
                updated = False
                if user.bot_id != bot_id:
                    user.bot_id = bot_id
                    updated = True
                for field, value in kwargs.items():
                    if value is not None and hasattr(user, field):
                        setattr(user, field, value)
                        updated = True
                if updated:
                    session.commit()
                    session.refresh(user)
                return user

            user = User(telegram_id=telegram_id, bot_id=bot_id, **kwargs)
            session.add(user)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                existing = (
                    session.query(User).filter(User.telegram_id == telegram_id).first()
                )
                if existing:
                    if existing.bot_id != bot_id:
                        existing.bot_id = bot_id
                    for field, value in kwargs.items():
                        if value is not None and hasattr(existing, field):
                            setattr(existing, field, value)
                    session.commit()
                    session.refresh(existing)
                    return existing
                raise

            session.refresh(user)
            return user

    @staticmethod
    async def update_last_interaction(telegram_id: int, bot_id: int):
        """Atualiza última interação do usuário"""
        with SessionLocal() as session:
            user = (
                session.query(User)
                .filter(User.telegram_id == telegram_id, User.bot_id == bot_id)
                .first()
            )

            if user:
                from datetime import datetime

                user.last_interaction = datetime.utcnow()
                session.commit()

    @staticmethod
    def get_user_id_sync(bot_id: int, telegram_id: int) -> Optional[int]:
        """Retorna ID interno do usuário ou None."""
        with SessionLocal() as session:
            user = (
                session.query(User.id)
                .filter(User.bot_id == bot_id, User.telegram_id == telegram_id)
                .first()
            )
            return user[0] if user else None

    @staticmethod
    def get_user_sync(bot_id: int, telegram_id: int) -> Optional[User]:
        """Retorna metadados básicos do usuário (sync para workers)."""
        with SessionLocal() as session:
            return (
                session.query(User)
                .filter(User.bot_id == bot_id, User.telegram_id == telegram_id)
                .first()
            )

    @staticmethod
    def block_user_sync(bot_id: int, telegram_id: int, reason: str) -> bool:
        """Bloqueia usuário (versão síncrona para workers)"""
        from datetime import datetime

        from sqlalchemy import text

        with SessionLocal() as session:
            try:
                # Usa NOWAIT para evitar lock wait
                result = session.execute(
                    text(
                        """
                        UPDATE users
                        SET is_blocked = TRUE,
                            block_reason = :reason,
                            blocked_at = :blocked_at
                        WHERE bot_id = :bot_id
                        AND telegram_id = :telegram_id
                        AND is_blocked = FALSE
                    """
                    ),
                    {
                        "bot_id": bot_id,
                        "telegram_id": telegram_id,
                        "reason": reason,
                        "blocked_at": datetime.utcnow(),
                    },
                )
                session.commit()
                return result.rowcount > 0
            except Exception as e:
                session.rollback()
                raise e

    @staticmethod
    async def block_user(bot_id: int, telegram_id: int, reason: str) -> bool:
        """Bloqueia usuário (versão assíncrona)"""
        return UserRepository.block_user_sync(bot_id, telegram_id, reason)

    @staticmethod
    def is_blocked_sync(bot_id: int, telegram_id: int) -> bool:
        """Verifica se usuário está bloqueado (sync para workers)"""
        with SessionLocal() as session:
            user = (
                session.query(User)
                .filter(
                    User.bot_id == bot_id,
                    User.telegram_id == telegram_id,
                    User.is_blocked == True,  # noqa: E712
                )
                .first()
            )
            return user is not None

    @staticmethod
    async def is_blocked(bot_id: int, telegram_id: int) -> bool:
        """Verifica se usuário está bloqueado"""
        return UserRepository.is_blocked_sync(bot_id, telegram_id)


class AIConfigRepository:
    """Repository para configurações de IA"""

    @staticmethod
    async def get_by_bot_id(bot_id: int):
        """Busca configuração de IA por bot_id"""
        from .models import BotAIConfig

        with SessionLocal() as session:
            return (
                session.query(BotAIConfig).filter(BotAIConfig.bot_id == bot_id).first()
            )

    @staticmethod
    def get_by_bot_id_sync(bot_id: int):
        """Busca configuração de IA por bot_id (sync para workers)"""
        from .models import BotAIConfig

        with SessionLocal() as session:
            return (
                session.query(BotAIConfig).filter(BotAIConfig.bot_id == bot_id).first()
            )

    @staticmethod
    async def create_config(
        bot_id: int, model_type: str, general_prompt: str, **kwargs
    ):
        """Cria nova configuração de IA"""
        from .models import BotAIConfig

        with SessionLocal() as session:
            config = BotAIConfig(
                bot_id=bot_id,
                model_type=model_type,
                general_prompt=general_prompt,
                **kwargs,
            )
            session.add(config)
            session.commit()
            session.refresh(config)
            return config

    @staticmethod
    async def update_general_prompt(bot_id: int, prompt: str):
        """Atualiza prompt geral"""
        from .models import BotAIConfig

        with SessionLocal() as session:
            config = (
                session.query(BotAIConfig).filter(BotAIConfig.bot_id == bot_id).first()
            )
            if config:
                config.general_prompt = prompt
                session.commit()
                return True
            return False

    @staticmethod
    async def update_model_type(bot_id: int, model_type: str):
        """Atualiza tipo de modelo (reasoning/non-reasoning)"""
        from .models import BotAIConfig

        with SessionLocal() as session:
            config = (
                session.query(BotAIConfig).filter(BotAIConfig.bot_id == bot_id).first()
            )
            if config:
                config.model_type = model_type
                session.commit()
                return True
            return False

    @staticmethod
    async def toggle_enabled(bot_id: int):
        """Ativa/desativa IA do bot"""
        from .models import BotAIConfig

        with SessionLocal() as session:
            config = (
                session.query(BotAIConfig).filter(BotAIConfig.bot_id == bot_id).first()
            )
            if config:
                config.is_enabled = not config.is_enabled
                session.commit()
                return config.is_enabled
            return None


class AIPhaseRepository:
    """Repository para fases da IA"""

    @staticmethod
    async def create_phase(
        bot_id: int,
        name: str,
        prompt: str,
        trigger: str = None,
        is_initial: bool = False,
        order: int = 0,
    ):
        """
        Cria nova fase

        Args:
            bot_id: ID do bot
            name: Nome legível da fase
            prompt: Prompt da fase
            trigger: Termo único (None para fase inicial)
            is_initial: Se é fase inicial
            order: Ordem de exibição
        """
        from .models import AIPhase

        with SessionLocal() as session:
            # Se marcar como inicial, desmarcar outras fases iniciais
            if is_initial:
                session.query(AIPhase).filter(
                    AIPhase.bot_id == bot_id, AIPhase.is_initial.is_(True)
                ).update({"is_initial": False})

            phase = AIPhase(
                bot_id=bot_id,
                phase_name=name,
                phase_trigger=trigger,
                phase_prompt=prompt,
                is_initial=is_initial,
                order=order,
            )
            session.add(phase)
            session.commit()
            session.refresh(phase)
            return phase

    @staticmethod
    async def get_phases_by_bot(bot_id: int) -> List:
        """Lista todas as fases de um bot"""
        from .models import AIPhase

        with SessionLocal() as session:
            return (
                session.query(AIPhase)
                .filter(AIPhase.bot_id == bot_id)
                .order_by(AIPhase.order)
                .all()
            )

    @staticmethod
    def get_phases_by_bot_sync(bot_id: int) -> List:
        """Lista todas as fases de um bot (sync)"""
        from .models import AIPhase

        with SessionLocal() as session:
            return (
                session.query(AIPhase)
                .filter(AIPhase.bot_id == bot_id)
                .order_by(AIPhase.order)
                .all()
            )

    @staticmethod
    async def get_phase_by_trigger(bot_id: int, trigger: str):
        """Busca fase por trigger"""
        from .models import AIPhase

        with SessionLocal() as session:
            return (
                session.query(AIPhase)
                .filter(AIPhase.bot_id == bot_id, AIPhase.phase_trigger == trigger)
                .first()
            )

    @staticmethod
    async def get_by_id(phase_id: int):
        """Busca fase por ID"""
        from .models import AIPhase

        with SessionLocal() as session:
            return session.query(AIPhase).filter(AIPhase.id == phase_id).first()

    @staticmethod
    async def delete_phase(phase_id: int) -> bool:
        """Deleta fase"""
        from .models import AIPhase

        with SessionLocal() as session:
            phase = session.query(AIPhase).filter(AIPhase.id == phase_id).first()
            if phase:
                session.delete(phase)
                session.commit()
                return True
            return False

    @staticmethod
    async def get_initial_phase(bot_id: int):
        """Busca fase inicial do bot"""
        from .models import AIPhase

        with SessionLocal() as session:
            return (
                session.query(AIPhase)
                .filter(AIPhase.bot_id == bot_id, AIPhase.is_initial.is_(True))
                .first()
            )

    @staticmethod
    def get_initial_phase_sync(bot_id: int):
        """Busca fase inicial do bot (sync)"""
        from .models import AIPhase

        with SessionLocal() as session:
            return (
                session.query(AIPhase)
                .filter(AIPhase.bot_id == bot_id, AIPhase.is_initial.is_(True))
                .first()
            )

    @staticmethod
    def ensure_initial_phase_sync(bot_id: int):
        """
        Garante que existe uma fase inicial (sync)
        Se não existir, cria uma padrão

        Returns:
            AIPhase inicial (existente ou recém-criada)
        """
        from .models import AIPhase

        with SessionLocal() as session:
            # Buscar fase inicial
            initial_phase = (
                session.query(AIPhase)
                .filter(AIPhase.bot_id == bot_id, AIPhase.is_initial.is_(True))
                .first()
            )

            if not initial_phase:
                # Criar fase inicial padrão
                initial_phase = AIPhase(
                    bot_id=bot_id,
                    phase_name="Inicial",
                    phase_trigger=None,
                    phase_prompt=(
                        "Você está na fase inicial. "
                        "Seja acolhedor e pergunte como pode ajudar."
                    ),
                    is_initial=True,
                    order=0,
                )
                session.add(initial_phase)
                session.commit()
                session.refresh(initial_phase)

                logger.info(
                    "Default initial phase created in session (sync)",
                    extra={
                        "bot_id": bot_id,
                        "phase_id": initial_phase.id,
                    },
                )

            return initial_phase

    @staticmethod
    async def set_initial_phase(bot_id: int, phase_id: int) -> bool:
        """Define fase como inicial (desmarca outras)"""
        from .models import AIPhase

        with SessionLocal() as session:
            # Verifica se fase existe
            phase = session.query(AIPhase).filter(AIPhase.id == phase_id).first()
            if not phase or phase.bot_id != bot_id:
                return False

            # Desmarcar todas as fases iniciais do bot
            session.query(AIPhase).filter(
                AIPhase.bot_id == bot_id, AIPhase.is_initial.is_(True)
            ).update({"is_initial": False})

            # Marcar nova fase como inicial
            phase.is_initial = True
            session.commit()
            return True

    @staticmethod
    async def update_phase(
        phase_id: int, name: str = None, trigger: str = None, prompt: str = None
    ) -> bool:
        """Atualiza dados de uma fase"""
        from .models import AIPhase

        with SessionLocal() as session:
            phase = session.query(AIPhase).filter(AIPhase.id == phase_id).first()
            if not phase:
                return False

            if name is not None:
                phase.phase_name = name
            if trigger is not None:
                phase.phase_trigger = trigger
            if prompt is not None:
                phase.phase_prompt = prompt

            session.commit()
            return True


class ConversationHistoryRepository:
    """Repository para histórico de conversas"""

    @staticmethod
    async def add_message(
        bot_id: int,
        user_telegram_id: int,
        role: str,
        content: str,
        has_image: bool = False,
        image_url: str = None,
        prompt_tokens: int = 0,
        cached_tokens: int = 0,
        completion_tokens: int = 0,
        reasoning_tokens: int = 0,
    ):
        """Adiciona mensagem ao histórico"""
        from .models import ConversationHistory

        with SessionLocal() as session:
            message = ConversationHistory(
                bot_id=bot_id,
                user_telegram_id=user_telegram_id,
                role=role,
                content=content,
                has_image=has_image,
                image_url=image_url,
                prompt_tokens=prompt_tokens,
                cached_tokens=cached_tokens,
                completion_tokens=completion_tokens,
                reasoning_tokens=reasoning_tokens,
            )
            session.add(message)
            session.commit()
            session.refresh(message)
            return message

    @staticmethod
    async def get_recent_messages(
        bot_id: int, user_telegram_id: int, limit: int = 14
    ) -> List:
        """
        Busca mensagens recentes (últimas N)

        Args:
            limit: Número de mensagens (default 14 = 7 pares user+assistant)
        """
        from .models import ConversationHistory

        with SessionLocal() as session:
            return (
                session.query(ConversationHistory)
                .filter(
                    ConversationHistory.bot_id == bot_id,
                    ConversationHistory.user_telegram_id == user_telegram_id,
                )
                .order_by(ConversationHistory.created_at.desc())
                .limit(limit)
                .all()[::-1]
            )  # Reverse para ordem cronológica

    @staticmethod
    def get_recent_messages_sync(
        bot_id: int, user_telegram_id: int, limit: int = 14
    ) -> List:
        """Busca mensagens recentes (sync)"""
        from .models import ConversationHistory

        with SessionLocal() as session:
            return (
                session.query(ConversationHistory)
                .filter(
                    ConversationHistory.bot_id == bot_id,
                    ConversationHistory.user_telegram_id == user_telegram_id,
                )
                .order_by(ConversationHistory.created_at.desc())
                .limit(limit)
                .all()[::-1]
            )

    @staticmethod
    async def clean_old_messages(bot_id: int, user_telegram_id: int, keep: int = 14):
        """Remove mensagens antigas, mantendo apenas as últimas N"""
        from .models import ConversationHistory

        with SessionLocal() as session:
            # Busca IDs das mensagens a manter
            keep_ids_query = (
                session.query(ConversationHistory.id)
                .filter(
                    ConversationHistory.bot_id == bot_id,
                    ConversationHistory.user_telegram_id == user_telegram_id,
                )
                .order_by(ConversationHistory.created_at.desc())
                .limit(keep)
            )

            keep_ids = [row[0] for row in keep_ids_query.all()]

            # Deleta as que não estão na lista
            if keep_ids:
                session.query(ConversationHistory).filter(
                    ConversationHistory.bot_id == bot_id,
                    ConversationHistory.user_telegram_id == user_telegram_id,
                    ConversationHistory.id.notin_(keep_ids),
                ).delete(synchronize_session=False)
                session.commit()

    @staticmethod
    async def count_messages(bot_id: int, user_telegram_id: int) -> int:
        """Conta total de mensagens"""
        from .models import ConversationHistory

        with SessionLocal() as session:
            return (
                session.query(ConversationHistory)
                .filter(
                    ConversationHistory.bot_id == bot_id,
                    ConversationHistory.user_telegram_id == user_telegram_id,
                )
                .count()
            )


class UserAISessionRepository:
    """Repository para sessões de IA"""

    @staticmethod
    async def get_or_create_session(bot_id: int, user_telegram_id: int):
        """Busca ou cria sessão"""
        from datetime import datetime

        from .models import UserAISession

        with SessionLocal() as session:
            ai_session = (
                session.query(UserAISession)
                .filter(
                    UserAISession.bot_id == bot_id,
                    UserAISession.user_telegram_id == user_telegram_id,
                )
                .first()
            )

            if not ai_session:
                # Garantir que existe fase inicial
                initial_phase = AIPhaseRepository.ensure_initial_phase_sync(bot_id)

                ai_session = UserAISession(
                    bot_id=bot_id,
                    user_telegram_id=user_telegram_id,
                    current_phase_id=initial_phase.id,  # Sempre terá fase inicial
                    message_count=0,
                    last_interaction=datetime.utcnow(),
                )
                session.add(ai_session)
                session.commit()
                session.refresh(ai_session)

            return ai_session

    @staticmethod
    def get_or_create_session_sync(bot_id: int, user_telegram_id: int):
        """Busca ou cria sessão (sync)"""
        from datetime import datetime

        from .models import UserAISession

        with SessionLocal() as session:
            ai_session = (
                session.query(UserAISession)
                .filter(
                    UserAISession.bot_id == bot_id,
                    UserAISession.user_telegram_id == user_telegram_id,
                )
                .first()
            )

            if not ai_session:
                # Garantir que existe fase inicial
                initial_phase = AIPhaseRepository.ensure_initial_phase_sync(bot_id)

                ai_session = UserAISession(
                    bot_id=bot_id,
                    user_telegram_id=user_telegram_id,
                    current_phase_id=initial_phase.id,  # Sempre terá fase inicial
                    message_count=0,
                    last_interaction=datetime.utcnow(),
                )
                session.add(ai_session)
                session.commit()
                session.refresh(ai_session)

            return ai_session

    @staticmethod
    async def update_current_phase(bot_id: int, user_telegram_id: int, phase_id: int):
        """Atualiza fase atual"""
        from datetime import datetime

        from .models import UserAISession

        with SessionLocal() as session:
            ai_session = (
                session.query(UserAISession)
                .filter(
                    UserAISession.bot_id == bot_id,
                    UserAISession.user_telegram_id == user_telegram_id,
                )
                .first()
            )

            if ai_session:
                ai_session.current_phase_id = phase_id
                ai_session.last_interaction = datetime.utcnow()
                session.commit()
                return True
            return False

    @staticmethod
    def update_current_phase_sync(bot_id: int, user_telegram_id: int, phase_id: int):
        """Atualiza fase atual (sync)"""
        from datetime import datetime

        from .models import UserAISession

        with SessionLocal() as session:
            ai_session = (
                session.query(UserAISession)
                .filter(
                    UserAISession.bot_id == bot_id,
                    UserAISession.user_telegram_id == user_telegram_id,
                )
                .first()
            )

            if ai_session:
                ai_session.current_phase_id = phase_id
                ai_session.last_interaction = datetime.utcnow()
                session.commit()
                return True
            return False

    @staticmethod
    async def increment_message_count(bot_id: int, user_telegram_id: int):
        """Incrementa contador de mensagens"""
        from datetime import datetime

        from .models import UserAISession

        with SessionLocal() as session:
            ai_session = (
                session.query(UserAISession)
                .filter(
                    UserAISession.bot_id == bot_id,
                    UserAISession.user_telegram_id == user_telegram_id,
                )
                .first()
            )

            if ai_session:
                ai_session.message_count += 1
                ai_session.last_interaction = datetime.utcnow()
                session.commit()

    @staticmethod
    async def reset_session(bot_id: int, user_telegram_id: int):
        """Reseta sessão (volta para fase inicial)"""
        from datetime import datetime

        from .models import UserAISession

        with SessionLocal() as session:
            ai_session = (
                session.query(UserAISession)
                .filter(
                    UserAISession.bot_id == bot_id,
                    UserAISession.user_telegram_id == user_telegram_id,
                )
                .first()
            )

            if ai_session:
                ai_session.current_phase_id = None
                ai_session.message_count = 0
                ai_session.last_interaction = datetime.utcnow()
                session.commit()
                return True
            return False


class OfferRepository:
    """Repository para ofertas"""

    @staticmethod
    async def create_offer(bot_id: int, name: str, value: str = None) -> "Offer":
        """Cria nova oferta"""
        from .models import Offer

        with SessionLocal() as session:
            offer = Offer(bot_id=bot_id, name=name, value=value, is_active=True)
            session.add(offer)
            session.commit()
            session.refresh(offer)
            return offer

    @staticmethod
    async def get_offer_by_id(offer_id: int) -> "Offer":
        """Busca oferta por ID"""
        from .models import Offer

        with SessionLocal() as session:
            return session.query(Offer).filter(Offer.id == offer_id).first()

    @staticmethod
    async def get_offer_by_name(bot_id: int, name: str) -> "Offer":
        """Busca oferta por nome (case-insensitive)"""
        from .models import Offer

        with SessionLocal() as session:
            return (
                session.query(Offer)
                .filter(
                    Offer.bot_id == bot_id,
                    func.lower(Offer.name) == name.lower(),
                    Offer.is_active.is_(True),
                )
                .first()
            )

    @staticmethod
    async def get_offers_by_bot(bot_id: int, active_only: bool = True) -> List["Offer"]:
        """Lista ofertas de um bot"""
        from .models import Offer

        with SessionLocal() as session:
            query = session.query(Offer).filter(Offer.bot_id == bot_id)
            if active_only:
                query = query.filter(Offer.is_active.is_(True))
            return query.order_by(Offer.created_at.desc()).all()

    @staticmethod
    async def update_offer(offer_id: int, **kwargs) -> bool:
        """Atualiza oferta"""
        from datetime import datetime

        from .models import Offer

        with SessionLocal() as session:
            offer = session.query(Offer).filter(Offer.id == offer_id).first()
            if offer:
                for key, value in kwargs.items():
                    if hasattr(offer, key):
                        setattr(offer, key, value)
                offer.updated_at = datetime.utcnow()
                session.commit()
                return True
            return False

    @staticmethod
    async def delete_offer(offer_id: int) -> bool:
        """Deleta oferta (soft delete)"""
        return await OfferRepository.update_offer(offer_id, is_active=False)

    @staticmethod
    def get_offer_by_id_sync(offer_id: int) -> "Offer":
        """Versão síncrona para Celery"""
        from .models import Offer

        with SessionLocal() as session:
            return session.query(Offer).filter(Offer.id == offer_id).first()


class OfferPitchRepository:
    """Repository para blocos do pitch de vendas"""

    @staticmethod
    async def create_block(
        offer_id: int,
        order: int,
        text: str = None,
        media_file_id: str = None,
        media_type: str = None,
        delay_seconds: int = 0,
        auto_delete_seconds: int = 0,
    ) -> "OfferPitchBlock":
        """Cria novo bloco do pitch"""
        from .models import OfferPitchBlock

        with SessionLocal() as session:
            block = OfferPitchBlock(
                offer_id=offer_id,
                order=order,
                text=text,
                media_file_id=media_file_id,
                media_type=media_type,
                delay_seconds=delay_seconds,
                auto_delete_seconds=auto_delete_seconds,
            )
            session.add(block)
            session.commit()
            session.refresh(block)
            return block

    @staticmethod
    async def get_blocks_by_offer(offer_id: int) -> List["OfferPitchBlock"]:
        """Lista blocos de uma oferta ordenados"""
        from .models import OfferPitchBlock

        with SessionLocal() as session:
            return (
                session.query(OfferPitchBlock)
                .filter(OfferPitchBlock.offer_id == offer_id)
                .order_by(OfferPitchBlock.order)
                .all()
            )

    @staticmethod
    async def get_block_by_id(block_id: int) -> "OfferPitchBlock":
        """Busca bloco por ID"""
        from .models import OfferPitchBlock

        with SessionLocal() as session:
            return (
                session.query(OfferPitchBlock)
                .filter(OfferPitchBlock.id == block_id)
                .first()
            )

    @staticmethod
    async def update_block(block_id: int, **kwargs) -> bool:
        """Atualiza bloco"""
        from datetime import datetime

        from .models import OfferPitchBlock

        with SessionLocal() as session:
            block = (
                session.query(OfferPitchBlock)
                .filter(OfferPitchBlock.id == block_id)
                .first()
            )
            if block:
                for key, value in kwargs.items():
                    if hasattr(block, key):
                        setattr(block, key, value)
                block.updated_at = datetime.utcnow()
                session.commit()
                return True
            return False

    @staticmethod
    async def delete_block(block_id: int) -> bool:
        """Deleta bloco e reordena os restantes"""
        from .models import OfferPitchBlock

        with SessionLocal() as session:
            block = (
                session.query(OfferPitchBlock)
                .filter(OfferPitchBlock.id == block_id)
                .first()
            )
            if block:
                offer_id = block.offer_id
                deleted_order = block.order
                session.delete(block)

                # Reordenar blocos restantes
                remaining_blocks = (
                    session.query(OfferPitchBlock)
                    .filter(
                        OfferPitchBlock.offer_id == offer_id,
                        OfferPitchBlock.order > deleted_order,
                    )
                    .order_by(OfferPitchBlock.order)
                    .all()
                )

                for remaining_block in remaining_blocks:
                    remaining_block.order -= 1

                session.commit()
                return True
            return False

    @staticmethod
    def get_blocks_by_offer_sync(offer_id: int) -> List["OfferPitchBlock"]:
        """Versão síncrona para Celery"""
        from .models import OfferPitchBlock

        with SessionLocal() as session:
            return (
                session.query(OfferPitchBlock)
                .filter(OfferPitchBlock.offer_id == offer_id)
                .order_by(OfferPitchBlock.order)
                .all()
            )


class OfferDeliverableRepository:
    """Repository para entregáveis de ofertas"""

    @staticmethod
    async def create_deliverable(
        offer_id: int, content: str, deliverable_type: str = None
    ) -> "OfferDeliverable":
        """Cria novo entregável"""
        from .models import OfferDeliverable

        with SessionLocal() as session:
            deliverable = OfferDeliverable(
                offer_id=offer_id, content=content, type=deliverable_type
            )
            session.add(deliverable)
            session.commit()
            session.refresh(deliverable)
            return deliverable

    @staticmethod
    async def get_deliverables_by_offer(offer_id: int) -> List["OfferDeliverable"]:
        """Lista entregáveis de uma oferta"""
        from .models import OfferDeliverable

        with SessionLocal() as session:
            return (
                session.query(OfferDeliverable)
                .filter(OfferDeliverable.offer_id == offer_id)
                .all()
            )

    @staticmethod
    async def get_deliverable_by_id(deliverable_id: int) -> "OfferDeliverable":
        """Busca entregável por ID"""
        from .models import OfferDeliverable

        with SessionLocal() as session:
            return (
                session.query(OfferDeliverable)
                .filter(OfferDeliverable.id == deliverable_id)
                .first()
            )

    @staticmethod
    async def update_deliverable(deliverable_id: int, **kwargs) -> bool:
        """Atualiza entregável"""
        from datetime import datetime

        from .models import OfferDeliverable

        with SessionLocal() as session:
            deliverable = (
                session.query(OfferDeliverable)
                .filter(OfferDeliverable.id == deliverable_id)
                .first()
            )
            if deliverable:
                for key, value in kwargs.items():
                    if hasattr(deliverable, key):
                        setattr(deliverable, key, value)
                deliverable.updated_at = datetime.utcnow()
                session.commit()
                return True
            return False

    @staticmethod
    async def delete_deliverable(deliverable_id: int) -> bool:
        """Deleta entregável"""
        from .models import OfferDeliverable

        with SessionLocal() as session:
            deliverable = (
                session.query(OfferDeliverable)
                .filter(OfferDeliverable.id == deliverable_id)
                .first()
            )
            if deliverable:
                session.delete(deliverable)
                session.commit()
                return True
            return False


class GatewayConfigRepository:
    """Repository para configurações de gateway"""

    @staticmethod
    async def get_by_admin_id(admin_id: int, gateway_type: str = "pushinpay"):
        """Busca configuração de gateway por admin_id"""
        from .models import GatewayConfig

        with SessionLocal() as session:
            return (
                session.query(GatewayConfig)
                .filter(
                    GatewayConfig.admin_id == admin_id,
                    GatewayConfig.gateway_type == gateway_type,
                    GatewayConfig.is_active == True,  # noqa: E712
                )
                .first()
            )

    @staticmethod
    def get_by_admin_id_sync(admin_id: int, gateway_type: str = "pushinpay"):
        """Busca config de gateway (sync para workers)"""
        from .models import GatewayConfig

        with SessionLocal() as session:
            return (
                session.query(GatewayConfig)
                .filter(
                    GatewayConfig.admin_id == admin_id,
                    GatewayConfig.gateway_type == gateway_type,
                    GatewayConfig.is_active == True,  # noqa: E712
                )
                .first()
            )

    @staticmethod
    async def create_config(admin_id: int, gateway_type: str, encrypted_token: bytes):
        """Cria nova configuração de gateway"""
        from .models import GatewayConfig

        with SessionLocal() as session:
            config = GatewayConfig(
                admin_id=admin_id,
                gateway_type=gateway_type,
                encrypted_token=encrypted_token,
                is_active=True,
            )
            session.add(config)
            session.commit()
            session.refresh(config)
            return config

    @staticmethod
    async def update_token(admin_id: int, gateway_type: str, encrypted_token: bytes):
        """Atualiza token do gateway"""
        from datetime import datetime

        from .models import GatewayConfig

        with SessionLocal() as session:
            config = (
                session.query(GatewayConfig)
                .filter(
                    GatewayConfig.admin_id == admin_id,
                    GatewayConfig.gateway_type == gateway_type,
                )
                .first()
            )
            if config:
                config.encrypted_token = encrypted_token
                config.updated_at = datetime.utcnow()
                session.commit()
                return True
            return False

    @staticmethod
    async def delete_config(admin_id: int, gateway_type: str) -> bool:
        """Deleta configuração de gateway"""
        from .models import GatewayConfig

        with SessionLocal() as session:
            config = (
                session.query(GatewayConfig)
                .filter(
                    GatewayConfig.admin_id == admin_id,
                    GatewayConfig.gateway_type == gateway_type,
                )
                .first()
            )
            if config:
                session.delete(config)
                session.commit()
                return True
            return False


class BotGatewayConfigRepository:
    """Repository para configurações de gateway por bot"""

    @staticmethod
    async def get_by_bot_id(bot_id: int, gateway_type: str = "pushinpay"):
        """Busca configuração de gateway por bot_id"""
        from .models import BotGatewayConfig

        with SessionLocal() as session:
            return (
                session.query(BotGatewayConfig)
                .filter(
                    BotGatewayConfig.bot_id == bot_id,
                    BotGatewayConfig.gateway_type == gateway_type,
                    BotGatewayConfig.is_active == True,  # noqa: E712
                )
                .first()
            )

    @staticmethod
    def get_by_bot_id_sync(bot_id: int, gateway_type: str = "pushinpay"):
        """Busca config de gateway por bot (sync para workers)"""
        from .models import BotGatewayConfig

        with SessionLocal() as session:
            return (
                session.query(BotGatewayConfig)
                .filter(
                    BotGatewayConfig.bot_id == bot_id,
                    BotGatewayConfig.gateway_type == gateway_type,
                    BotGatewayConfig.is_active == True,  # noqa: E712
                )
                .first()
            )

    @staticmethod
    async def create_config(bot_id: int, gateway_type: str, encrypted_token: bytes):
        """Cria nova configuração de gateway para bot"""
        from .models import BotGatewayConfig

        with SessionLocal() as session:
            config = BotGatewayConfig(
                bot_id=bot_id,
                gateway_type=gateway_type,
                encrypted_token=encrypted_token,
                is_active=True,
            )
            session.add(config)
            session.commit()
            session.refresh(config)
            return config

    @staticmethod
    async def update_token(bot_id: int, gateway_type: str, encrypted_token: bytes):
        """Atualiza token do gateway para bot"""
        from datetime import datetime

        from .models import BotGatewayConfig

        with SessionLocal() as session:
            config = (
                session.query(BotGatewayConfig)
                .filter(
                    BotGatewayConfig.bot_id == bot_id,
                    BotGatewayConfig.gateway_type == gateway_type,
                )
                .first()
            )
            if config:
                config.encrypted_token = encrypted_token
                config.updated_at = datetime.utcnow()
                session.commit()
                return True
            return False

    @staticmethod
    async def delete_config(bot_id: int, gateway_type: str) -> bool:
        """Deleta configuração de gateway do bot"""
        from .models import BotGatewayConfig

        with SessionLocal() as session:
            config = (
                session.query(BotGatewayConfig)
                .filter(
                    BotGatewayConfig.bot_id == bot_id,
                    BotGatewayConfig.gateway_type == gateway_type,
                )
                .first()
            )
            if config:
                session.delete(config)
                session.commit()
                return True
            return False


class PixTransactionRepository:
    """Repository para transações PIX"""

    @staticmethod
    async def create_transaction(
        bot_id: int,
        user_telegram_id: int,
        chat_id: int,
        offer_id: int = None,
        upsell_id: int = None,
        transaction_id: str = None,
        qr_code: str = None,
        value_cents: int = None,
        qr_code_base64: str = None,
    ):
        """Cria nova transação PIX (para oferta OU upsell)"""
        from .models import PixTransaction

        with SessionLocal() as session:
            transaction = PixTransaction(
                bot_id=bot_id,
                user_telegram_id=user_telegram_id,
                chat_id=chat_id,
                offer_id=offer_id,
                upsell_id=upsell_id,
                transaction_id=transaction_id,
                qr_code=qr_code,
                qr_code_base64=qr_code_base64,
                value_cents=value_cents,
                status="created",
            )
            session.add(transaction)
            session.commit()
            session.refresh(transaction)
            return transaction

    @staticmethod
    async def get_by_id(pix_id: int):
        """Busca transação por ID"""
        from .models import PixTransaction

        with SessionLocal() as session:
            return (
                session.query(PixTransaction)
                .filter(PixTransaction.id == pix_id)
                .first()
            )

    @staticmethod
    def get_by_id_sync(pix_id: int):
        """Busca transação por ID (sync para workers)"""
        from .models import PixTransaction

        with SessionLocal() as session:
            return (
                session.query(PixTransaction)
                .filter(PixTransaction.id == pix_id)
                .first()
            )

    @staticmethod
    async def get_by_transaction_id(transaction_id: str):
        """Busca transação por transaction_id do PushinPay"""
        from .models import PixTransaction

        with SessionLocal() as session:
            return (
                session.query(PixTransaction)
                .filter(PixTransaction.transaction_id == transaction_id)
                .first()
            )

    @staticmethod
    def get_by_transaction_id_sync(transaction_id: str):
        """Busca transação por transaction_id (sync para workers)."""
        from .models import PixTransaction

        with SessionLocal() as session:
            return (
                session.query(PixTransaction)
                .filter(PixTransaction.transaction_id == transaction_id)
                .first()
            )

    @staticmethod
    async def get_latest_unpaid_by_chat(chat_id: int):
        """Busca última transação não paga de um chat"""
        from .models import PixTransaction

        with SessionLocal() as session:
            return (
                session.query(PixTransaction)
                .filter(
                    PixTransaction.chat_id == chat_id,
                    PixTransaction.status == "created",
                    PixTransaction.delivered_at == None,  # noqa: E711
                )
                .order_by(PixTransaction.created_at.desc())
                .first()
            )

    @staticmethod
    def get_pending_for_verification_sync(limit_minutes: int = 10):
        """Busca transações pendentes para verificação (sync para workers)"""
        from datetime import datetime, timedelta

        from .models import PixTransaction

        cutoff_time = datetime.utcnow() - timedelta(minutes=limit_minutes)

        with SessionLocal() as session:
            return (
                session.query(PixTransaction)
                .filter(
                    PixTransaction.status == "created",
                    PixTransaction.created_at >= cutoff_time,
                )
                .all()
            )

    @staticmethod
    async def update_status(pix_id: int, status: str) -> bool:
        """Atualiza status da transação"""
        from datetime import datetime

        from .models import PixTransaction

        with SessionLocal() as session:
            transaction = (
                session.query(PixTransaction)
                .filter(PixTransaction.id == pix_id)
                .first()
            )
            if transaction:
                transaction.status = status
                transaction.updated_at = datetime.utcnow()
                session.commit()
                return True
            return False

    @staticmethod
    def update_status_sync(pix_id: int, status: str) -> bool:
        """Atualiza status (sync para workers)"""
        from datetime import datetime

        from .models import PixTransaction

        with SessionLocal() as session:
            transaction = (
                session.query(PixTransaction)
                .filter(PixTransaction.id == pix_id)
                .first()
            )
            if transaction:
                transaction.status = status
                transaction.updated_at = datetime.utcnow()
                session.commit()
                return True
            return False

    @staticmethod
    async def mark_delivered(pix_id: int) -> bool:
        """Marca transação como entregue"""
        from datetime import datetime

        from .models import PixTransaction

        with SessionLocal() as session:
            transaction = (
                session.query(PixTransaction)
                .filter(PixTransaction.id == pix_id)
                .first()
            )
            if transaction:
                transaction.delivered_at = datetime.utcnow()
                transaction.updated_at = datetime.utcnow()
                session.commit()
                return True
            return False

    @staticmethod
    def mark_delivered_sync(pix_id: int) -> bool:
        """Marca como entregue (sync para workers)"""
        from datetime import datetime

        from .models import PixTransaction

        with SessionLocal() as session:
            transaction = (
                session.query(PixTransaction)
                .filter(PixTransaction.id == pix_id)
                .first()
            )
            if transaction:
                transaction.delivered_at = datetime.utcnow()
                transaction.updated_at = datetime.utcnow()
                session.commit()
                return True
            return False

    @staticmethod
    def set_tracker_sync(transaction_id: int, tracker_id: int) -> None:
        """Associa um tracker à transação (idempotente)."""
        from datetime import datetime

        from .models import PixTransaction

        with SessionLocal() as session:
            transaction = (
                session.query(PixTransaction)
                .filter(PixTransaction.id == transaction_id)
                .first()
            )
            if not transaction:
                return
            if getattr(transaction, "tracker_id", None) == tracker_id:
                return
            transaction.tracker_id = tracker_id
            transaction.updated_at = datetime.utcnow()
            session.add(transaction)
            session.commit()

    @staticmethod
    async def user_has_paid(bot_id: int, user_telegram_id: int) -> bool:
        from .models import PixTransaction

        with SessionLocal() as session:
            return (
                session.query(PixTransaction.id)
                .filter(
                    PixTransaction.bot_id == bot_id,
                    PixTransaction.user_telegram_id == user_telegram_id,
                    PixTransaction.status == "paid",
                )
                .first()
                is not None
            )

    @staticmethod
    def user_has_paid_sync(bot_id: int, user_telegram_id: int) -> bool:
        from .models import PixTransaction

        with SessionLocal() as session:
            return (
                session.query(PixTransaction.id)
                .filter(
                    PixTransaction.bot_id == bot_id,
                    PixTransaction.user_telegram_id == user_telegram_id,
                    PixTransaction.status == "paid",
                )
                .first()
                is not None
            )

    @staticmethod
    def get_pending_by_user_and_offer_sync(
        bot_id: int, user_telegram_id: int, offer_id: int, minutes_ago: int = 15
    ) -> List:
        """Busca transações PIX pendentes de um usuário em uma oferta"""
        from datetime import datetime, timedelta

        from .models import PixTransaction

        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes_ago)

        with SessionLocal() as session:
            return (
                session.query(PixTransaction)
                .filter(
                    PixTransaction.bot_id == bot_id,
                    PixTransaction.user_telegram_id == user_telegram_id,
                    PixTransaction.offer_id == offer_id,
                    PixTransaction.created_at >= cutoff_time,
                    PixTransaction.status.in_(["created", "pending"]),
                )
                .order_by(PixTransaction.created_at.desc())
                .all()
            )

    @staticmethod
    def get_pending_by_user_and_upsell_sync(
        bot_id: int, user_telegram_id: int, upsell_id: int, minutes_ago: int = 15
    ) -> List:
        """Busca transações PIX pendentes de um usuário em um upsell"""
        from datetime import datetime, timedelta

        from .models import PixTransaction

        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes_ago)

        with SessionLocal() as session:
            return (
                session.query(PixTransaction)
                .filter(
                    PixTransaction.bot_id == bot_id,
                    PixTransaction.user_telegram_id == user_telegram_id,
                    PixTransaction.upsell_id == upsell_id,
                    PixTransaction.created_at >= cutoff_time,
                    PixTransaction.status.in_(["created", "pending"]),
                )
                .order_by(PixTransaction.created_at.desc())
                .all()
            )

    @staticmethod
    def get_pending_upsell_transactions_sync(limit_minutes: int = 10):
        """Busca transações de upsell pendentes para verificação (sync)"""
        from datetime import datetime, timedelta

        from .models import PixTransaction

        cutoff_time = datetime.utcnow() - timedelta(minutes=limit_minutes)

        with SessionLocal() as session:
            return (
                session.query(PixTransaction)
                .filter(
                    PixTransaction.upsell_id.isnot(None),
                    PixTransaction.status == "created",
                    PixTransaction.created_at >= cutoff_time,
                )
                .all()
            )


class OfferDeliverableBlockRepository:
    """Repository para blocos de entregável"""

    @staticmethod
    async def create_block(offer_id: int, order: int, **kwargs):
        """Cria novo bloco de entregável"""
        from .models import OfferDeliverableBlock

        with SessionLocal() as session:
            block = OfferDeliverableBlock(offer_id=offer_id, order=order, **kwargs)
            session.add(block)
            session.commit()
            session.refresh(block)
            return block

    @staticmethod
    async def get_blocks_by_offer(offer_id: int) -> List:
        """Lista blocos de um entregável"""
        from .models import OfferDeliverableBlock

        with SessionLocal() as session:
            return (
                session.query(OfferDeliverableBlock)
                .filter(OfferDeliverableBlock.offer_id == offer_id)
                .order_by(OfferDeliverableBlock.order)
                .all()
            )

    @staticmethod
    def get_blocks_by_offer_sync(offer_id: int) -> List:
        """Lista blocos (sync para workers)"""
        from .models import OfferDeliverableBlock

        with SessionLocal() as session:
            return (
                session.query(OfferDeliverableBlock)
                .filter(OfferDeliverableBlock.offer_id == offer_id)
                .order_by(OfferDeliverableBlock.order)
                .all()
            )

    @staticmethod
    async def get_block_by_id(block_id: int):
        """Busca bloco por ID"""
        from .models import OfferDeliverableBlock

        with SessionLocal() as session:
            return (
                session.query(OfferDeliverableBlock)
                .filter(OfferDeliverableBlock.id == block_id)
                .first()
            )

    @staticmethod
    async def update_block(block_id: int, **kwargs) -> bool:
        """Atualiza bloco"""
        from datetime import datetime

        from .models import OfferDeliverableBlock

        with SessionLocal() as session:
            block = (
                session.query(OfferDeliverableBlock)
                .filter(OfferDeliverableBlock.id == block_id)
                .first()
            )
            if block:
                for key, value in kwargs.items():
                    if hasattr(block, key):
                        setattr(block, key, value)
                block.updated_at = datetime.utcnow()
                session.commit()
                return True
            return False

    @staticmethod
    async def delete_block(block_id: int) -> bool:
        """Deleta bloco"""
        from .models import OfferDeliverableBlock

        with SessionLocal() as session:
            block = (
                session.query(OfferDeliverableBlock)
                .filter(OfferDeliverableBlock.id == block_id)
                .first()
            )
            if block:
                session.delete(block)
                session.commit()
                return True
            return False


class OfferManualVerificationBlockRepository:
    """Repository para blocos de verificação manual"""

    @staticmethod
    async def create_block(offer_id: int, order: int, **kwargs):
        """Cria novo bloco de verificação manual"""
        from .models import OfferManualVerificationBlock

        with SessionLocal() as session:
            block = OfferManualVerificationBlock(
                offer_id=offer_id, order=order, **kwargs
            )
            session.add(block)
            session.commit()
            session.refresh(block)
            return block

    @staticmethod
    async def get_blocks_by_offer(offer_id: int) -> List:
        """Lista blocos de verificação manual"""
        from .models import OfferManualVerificationBlock

        with SessionLocal() as session:
            return (
                session.query(OfferManualVerificationBlock)
                .filter(OfferManualVerificationBlock.offer_id == offer_id)
                .order_by(OfferManualVerificationBlock.order)
                .all()
            )

    @staticmethod
    def get_blocks_by_offer_sync(offer_id: int) -> List:
        """Lista blocos (sync para workers)"""
        from .models import OfferManualVerificationBlock

        with SessionLocal() as session:
            return (
                session.query(OfferManualVerificationBlock)
                .filter(OfferManualVerificationBlock.offer_id == offer_id)
                .order_by(OfferManualVerificationBlock.order)
                .all()
            )

    @staticmethod
    async def get_block_by_id(block_id: int):
        """Busca bloco por ID"""
        from .models import OfferManualVerificationBlock

        with SessionLocal() as session:
            return (
                session.query(OfferManualVerificationBlock)
                .filter(OfferManualVerificationBlock.id == block_id)
                .first()
            )

    @staticmethod
    async def update_block(block_id: int, **kwargs) -> bool:
        """Atualiza bloco"""
        from datetime import datetime

        from .models import OfferManualVerificationBlock

        with SessionLocal() as session:
            block = (
                session.query(OfferManualVerificationBlock)
                .filter(OfferManualVerificationBlock.id == block_id)
                .first()
            )
            if block:
                for key, value in kwargs.items():
                    if hasattr(block, key):
                        setattr(block, key, value)
                block.updated_at = datetime.utcnow()
                session.commit()
                return True
            return False

    @staticmethod
    async def delete_block(block_id: int) -> bool:
        """Deleta bloco"""
        from .models import OfferManualVerificationBlock

        with SessionLocal() as session:
            block = (
                session.query(OfferManualVerificationBlock)
                .filter(OfferManualVerificationBlock.id == block_id)
                .first()
            )
            if block:
                session.delete(block)
                session.commit()
                return True
            return False


class OfferDiscountBlockRepository:
    """Repository para blocos de desconto"""

    @staticmethod
    async def create_block(offer_id: int, order: int, **kwargs):
        """Cria novo bloco de desconto"""
        from .models import OfferDiscountBlock

        with SessionLocal() as session:
            block = OfferDiscountBlock(offer_id=offer_id, order=order, **kwargs)
            session.add(block)
            session.commit()
            session.refresh(block)
            return block

    @staticmethod
    async def get_blocks_by_offer(offer_id: int) -> List:
        """Lista blocos de desconto"""
        from .models import OfferDiscountBlock

        with SessionLocal() as session:
            return (
                session.query(OfferDiscountBlock)
                .filter(OfferDiscountBlock.offer_id == offer_id)
                .order_by(OfferDiscountBlock.order)
                .all()
            )

    @staticmethod
    def get_blocks_by_offer_sync(offer_id: int) -> List:
        """Lista blocos (versão síncrona)"""
        from .models import OfferDiscountBlock

        with SessionLocal() as session:
            return (
                session.query(OfferDiscountBlock)
                .filter(OfferDiscountBlock.offer_id == offer_id)
                .order_by(OfferDiscountBlock.order)
                .all()
            )

    @staticmethod
    async def get_block_by_id(block_id: int):
        """Busca bloco por ID"""
        from .models import OfferDiscountBlock

        with SessionLocal() as session:
            return (
                session.query(OfferDiscountBlock)
                .filter(OfferDiscountBlock.id == block_id)
                .first()
            )

    @staticmethod
    async def update_block(block_id: int, **kwargs) -> bool:
        """Atualiza bloco"""
        from datetime import datetime

        from .models import OfferDiscountBlock

        with SessionLocal() as session:
            block = (
                session.query(OfferDiscountBlock)
                .filter(OfferDiscountBlock.id == block_id)
                .first()
            )
            if block:
                for key, value in kwargs.items():
                    if hasattr(block, key):
                        setattr(block, key, value)
                block.updated_at = datetime.utcnow()
                session.commit()
                return True
            return False

    @staticmethod
    async def delete_block(block_id: int) -> bool:
        """Deleta bloco"""
        from .models import OfferDiscountBlock

        with SessionLocal() as session:
            block = (
                session.query(OfferDiscountBlock)
                .filter(OfferDiscountBlock.id == block_id)
                .first()
            )
            if not block:
                return False

            offer_id = block.offer_id
            deleted_order = block.order
            session.delete(block)

            remaining = (
                session.query(OfferDiscountBlock)
                .filter(
                    OfferDiscountBlock.offer_id == offer_id,
                    OfferDiscountBlock.order > deleted_order,
                )
                .order_by(OfferDiscountBlock.order)
                .all()
            )

            for item in remaining:
                item.order -= 1

            session.commit()
            return True


class MediaFileCacheRepository:
    """Repository para cache de file_ids entre bots"""

    @staticmethod
    async def get_cached_file_id(
        original_file_id: str,
        bot_id: int,
        expected_media_type: Optional[str] = None,
    ) -> Optional[str]:
        """Busca file_id em cache para o bot específico.

        Se um tipo esperado for informado e divergir do armazenado, o registro é
        descartado para forçar novo streaming/conversão."""
        from .models import MediaFileCache

        with SessionLocal() as session:
            cache = (
                session.query(MediaFileCache)
                .filter(
                    MediaFileCache.original_file_id == original_file_id,
                    MediaFileCache.bot_id == bot_id,
                )
                .first()
            )

            if not cache:
                return None

            if expected_media_type and cache.media_type != expected_media_type:
                logger.info(
                    "Cached media type mismatch; forcing re-stream",
                    extra={
                        "original_file_id": original_file_id,
                        "bot_id": bot_id,
                        "cached_media_type": cache.media_type,
                        "expected_media_type": expected_media_type,
                    },
                )
                session.delete(cache)
                session.commit()
                return None

            return cache.cached_file_id

    @staticmethod
    async def save_cached_file_id(
        original_file_id: str,
        bot_id: int,
        cached_file_id: str,
        media_type: str,
    ):
        """Salva file_id em cache"""
        from .models import MediaFileCache

        with SessionLocal() as session:
            # Verificar se já existe
            existing = (
                session.query(MediaFileCache)
                .filter(
                    MediaFileCache.original_file_id == original_file_id,
                    MediaFileCache.bot_id == bot_id,
                )
                .first()
            )

            if existing:
                # Atualizar
                existing.cached_file_id = cached_file_id
                existing.media_type = media_type
            else:
                # Criar novo
                cache = MediaFileCache(
                    original_file_id=original_file_id,
                    bot_id=bot_id,
                    cached_file_id=cached_file_id,
                    media_type=media_type,
                )
                session.add(cache)

            session.commit()

    @staticmethod
    async def clear_cached_file_id(original_file_id: str, bot_id: int) -> None:
        """Remove cache de file_id inválido."""
        from .models import MediaFileCache

        with SessionLocal() as session:
            (
                session.query(MediaFileCache)
                .filter(
                    MediaFileCache.original_file_id == original_file_id,
                    MediaFileCache.bot_id == bot_id,
                )
                .delete(synchronize_session=False)
            )
            session.commit()


class AIActionRepository:
    """Repository para ações da IA"""

    @staticmethod
    async def create_action(
        bot_id: int,
        action_name: str,
        track_usage: bool = False,
        is_active: bool = True,
    ) -> "AIAction":
        """Cria nova ação"""
        from .models import AIAction

        with SessionLocal() as session:
            action = AIAction(
                bot_id=bot_id,
                action_name=action_name,
                track_usage=track_usage,
                is_active=is_active,
            )
            session.add(action)
            session.commit()
            session.refresh(action)
            return action

    @staticmethod
    async def get_action_by_id(action_id: int) -> Optional["AIAction"]:
        """Busca ação por ID"""
        from .models import AIAction

        with SessionLocal() as session:
            return session.query(AIAction).filter(AIAction.id == action_id).first()

    @staticmethod
    async def get_action_by_name(bot_id: int, action_name: str) -> Optional["AIAction"]:
        """Busca ação por nome (trigger)"""
        from .models import AIAction

        with SessionLocal() as session:
            return (
                session.query(AIAction)
                .filter(AIAction.bot_id == bot_id, AIAction.action_name == action_name)
                .first()
            )

    @staticmethod
    async def get_actions_by_bot(
        bot_id: int, active_only: bool = True
    ) -> List["AIAction"]:
        """Lista ações de um bot"""
        from .models import AIAction

        with SessionLocal() as session:
            query = session.query(AIAction).filter(AIAction.bot_id == bot_id)
            if active_only:
                query = query.filter(AIAction.is_active.is_(True))
            return query.order_by(AIAction.created_at.desc()).all()

    @staticmethod
    async def get_tracked_actions(bot_id: int) -> List["AIAction"]:
        """Lista apenas ações com rastreamento ativo"""
        from .models import AIAction

        with SessionLocal() as session:
            return (
                session.query(AIAction)
                .filter(
                    AIAction.bot_id == bot_id,
                    AIAction.is_active.is_(True),
                    AIAction.track_usage.is_(True),
                )
                .all()
            )

    @staticmethod
    async def update_action(action_id: int, **kwargs) -> bool:
        """Atualiza ação"""
        from datetime import datetime

        from .models import AIAction

        with SessionLocal() as session:
            action = session.query(AIAction).filter(AIAction.id == action_id).first()
            if action:
                for key, value in kwargs.items():
                    if hasattr(action, key):
                        setattr(action, key, value)
                action.updated_at = datetime.utcnow()
                session.commit()
                return True
            return False

    @staticmethod
    async def delete_action(action_id: int) -> bool:
        """Deleta ação e seus blocos"""
        from .models import AIAction

        with SessionLocal() as session:
            action = session.query(AIAction).filter(AIAction.id == action_id).first()
            if action:
                session.delete(action)
                session.commit()
                return True
            return False

    @staticmethod
    def get_tracked_actions_sync(bot_id: int) -> List["AIAction"]:
        """Versão síncrona para workers"""
        from .models import AIAction

        with SessionLocal() as session:
            return (
                session.query(AIAction)
                .filter(
                    AIAction.bot_id == bot_id,
                    AIAction.is_active.is_(True),
                    AIAction.track_usage.is_(True),
                )
                .all()
            )


class AIActionBlockRepository:
    """Repository para blocos de ação"""

    @staticmethod
    async def create_block(
        action_id: int,
        order: int,
        text: str = None,
        media_file_id: str = None,
        media_type: str = None,
        delay_seconds: int = 0,
        auto_delete_seconds: int = 0,
    ) -> "AIActionBlock":
        """Cria novo bloco de ação"""
        from .models import AIActionBlock

        with SessionLocal() as session:
            block = AIActionBlock(
                action_id=action_id,
                order=order,
                text=text,
                media_file_id=media_file_id,
                media_type=media_type,
                delay_seconds=delay_seconds,
                auto_delete_seconds=auto_delete_seconds,
            )
            session.add(block)
            session.commit()
            session.refresh(block)
            return block

    @staticmethod
    async def get_blocks_by_action(action_id: int) -> List["AIActionBlock"]:
        """Lista blocos de uma ação ordenados"""
        from .models import AIActionBlock

        with SessionLocal() as session:
            return (
                session.query(AIActionBlock)
                .filter(AIActionBlock.action_id == action_id)
                .order_by(AIActionBlock.order)
                .all()
            )

    @staticmethod
    async def get_block_by_id(block_id: int) -> Optional["AIActionBlock"]:
        """Busca bloco por ID"""
        from .models import AIActionBlock

        with SessionLocal() as session:
            return (
                session.query(AIActionBlock)
                .filter(AIActionBlock.id == block_id)
                .first()
            )

    @staticmethod
    async def update_block(block_id: int, **kwargs) -> bool:
        """Atualiza bloco"""
        from datetime import datetime

        from .models import AIActionBlock

        with SessionLocal() as session:
            block = (
                session.query(AIActionBlock)
                .filter(AIActionBlock.id == block_id)
                .first()
            )
            if block:
                for key, value in kwargs.items():
                    if hasattr(block, key):
                        setattr(block, key, value)
                block.updated_at = datetime.utcnow()
                session.commit()
                return True
            return False

    @staticmethod
    async def delete_block(block_id: int) -> bool:
        """Deleta bloco e reordena os restantes"""
        from .models import AIActionBlock

        with SessionLocal() as session:
            block = (
                session.query(AIActionBlock)
                .filter(AIActionBlock.id == block_id)
                .first()
            )
            if block:
                action_id = block.action_id
                deleted_order = block.order
                session.delete(block)

                # Reordenar blocos restantes
                remaining_blocks = (
                    session.query(AIActionBlock)
                    .filter(
                        AIActionBlock.action_id == action_id,
                        AIActionBlock.order > deleted_order,
                    )
                    .order_by(AIActionBlock.order)
                    .all()
                )

                for remaining_block in remaining_blocks:
                    remaining_block.order -= 1

                session.commit()
                return True
            return False

    @staticmethod
    def get_blocks_by_action_sync(action_id: int) -> List["AIActionBlock"]:
        """Versão síncrona para workers"""
        from .models import AIActionBlock

        with SessionLocal() as session:
            return (
                session.query(AIActionBlock)
                .filter(AIActionBlock.action_id == action_id)
                .order_by(AIActionBlock.order)
                .all()
            )


class StartTemplateRepository:
    """Repository para template de mensagem inicial"""

    @staticmethod
    async def get_or_create(bot_id: int) -> "StartTemplate":
        from .models import StartTemplate

        with SessionLocal() as session:
            template = (
                session.query(StartTemplate)
                .filter(StartTemplate.bot_id == bot_id)
                .first()
            )

            if not template:
                template = StartTemplate(bot_id=bot_id, is_active=True, version=1)
                session.add(template)
                session.commit()
                session.refresh(template)

            return template

    @staticmethod
    async def get_by_id(template_id: int) -> Optional["StartTemplate"]:
        from .models import StartTemplate

        with SessionLocal() as session:
            return (
                session.query(StartTemplate)
                .filter(StartTemplate.id == template_id)
                .first()
            )

    @staticmethod
    async def update_template(template_id: int, **kwargs) -> Optional["StartTemplate"]:
        from datetime import datetime

        from .models import StartTemplate

        with SessionLocal() as session:
            template = (
                session.query(StartTemplate)
                .filter(StartTemplate.id == template_id)
                .first()
            )
            if not template:
                return None

            for key, value in kwargs.items():
                if hasattr(template, key):
                    setattr(template, key, value)

            template.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(template)
            return template

    @staticmethod
    async def increment_version(template_id: int) -> Optional[int]:
        from datetime import datetime

        from sqlalchemy import select, update

        from .models import StartTemplate

        with SessionLocal() as session:
            with session.begin():
                stmt = (
                    select(StartTemplate)
                    .where(StartTemplate.id == template_id)
                    .with_for_update()
                )
                template = session.execute(stmt).scalars().first()
                if not template:
                    return None

                new_version = template.version + 1
                session.execute(
                    update(StartTemplate)
                    .where(StartTemplate.id == template_id)
                    .values(version=new_version, updated_at=datetime.utcnow())
                )

            session.commit()
            return new_version

    @staticmethod
    def get_active_template_sync(bot_id: int) -> Optional["StartTemplate"]:
        from .models import StartTemplate

        with SessionLocal() as session:
            return (
                session.query(StartTemplate)
                .filter(
                    StartTemplate.bot_id == bot_id,
                    StartTemplate.is_active.is_(True),
                )
                .first()
            )


class StartTemplateBlockRepository:
    """Repository para blocos do template de /start"""

    @staticmethod
    async def list_blocks(template_id: int) -> List["StartTemplateBlock"]:
        from .models import StartTemplateBlock

        with SessionLocal() as session:
            return (
                session.query(StartTemplateBlock)
                .filter(StartTemplateBlock.template_id == template_id)
                .order_by(StartTemplateBlock.order)
                .all()
            )

    @staticmethod
    async def count_blocks(template_id: int) -> int:
        from sqlalchemy import func

        from .models import StartTemplateBlock

        with SessionLocal() as session:
            return (
                session.query(func.count(StartTemplateBlock.id))
                .filter(StartTemplateBlock.template_id == template_id)
                .scalar()
            )

    @staticmethod
    async def get_block(block_id: int) -> Optional["StartTemplateBlock"]:
        from .models import StartTemplateBlock

        with SessionLocal() as session:
            return (
                session.query(StartTemplateBlock)
                .filter(StartTemplateBlock.id == block_id)
                .first()
            )

    @staticmethod
    async def create_block(
        template_id: int,
        order: int,
        text: str = None,
        media_file_id: str = None,
        media_type: str = None,
        delay_seconds: int = 0,
        auto_delete_seconds: int = 0,
    ) -> "StartTemplateBlock":
        from .models import StartTemplateBlock

        with SessionLocal() as session:
            block = StartTemplateBlock(
                template_id=template_id,
                order=order,
                text=text,
                media_file_id=media_file_id,
                media_type=media_type,
                delay_seconds=delay_seconds,
                auto_delete_seconds=auto_delete_seconds,
            )
            session.add(block)
            session.commit()
            session.refresh(block)
            return block

    @staticmethod
    async def update_block(block_id: int, **kwargs) -> bool:
        from datetime import datetime

        from .models import StartTemplateBlock

        with SessionLocal() as session:
            block = (
                session.query(StartTemplateBlock)
                .filter(StartTemplateBlock.id == block_id)
                .first()
            )
            if not block:
                return False

            for key, value in kwargs.items():
                if hasattr(block, key):
                    setattr(block, key, value)

            block.updated_at = datetime.utcnow()
            session.commit()
            return True

    @staticmethod
    async def delete_block(block_id: int) -> Optional[int]:
        from .models import StartTemplateBlock

        with SessionLocal() as session:
            block = (
                session.query(StartTemplateBlock)
                .filter(StartTemplateBlock.id == block_id)
                .first()
            )
            if not block:
                return None

            template_id = block.template_id
            deleted_order = block.order
            session.delete(block)

            remaining_blocks = (
                session.query(StartTemplateBlock)
                .filter(
                    StartTemplateBlock.template_id == template_id,
                    StartTemplateBlock.order > deleted_order,
                )
                .order_by(StartTemplateBlock.order)
                .all()
            )

            for remaining_block in remaining_blocks:
                remaining_block.order -= 1

            session.commit()
            return template_id

    @staticmethod
    def list_blocks_sync(template_id: int) -> List["StartTemplateBlock"]:
        from .models import StartTemplateBlock

        with SessionLocal() as session:
            return (
                session.query(StartTemplateBlock)
                .filter(StartTemplateBlock.template_id == template_id)
                .order_by(StartTemplateBlock.order)
                .all()
            )


class StartMessageStatusRepository:
    """Repository para controle de envio de /start"""

    @staticmethod
    async def mark_sent(
        bot_id: int, user_telegram_id: int, template_version: int
    ) -> None:
        from datetime import datetime

        from .models import StartMessageStatus

        with SessionLocal() as session:
            status = (
                session.query(StartMessageStatus)
                .filter(
                    StartMessageStatus.bot_id == bot_id,
                    StartMessageStatus.user_telegram_id == user_telegram_id,
                )
                .first()
            )

            if status:
                status.template_version = template_version
                status.sent_at = datetime.utcnow()
            else:
                status = StartMessageStatus(
                    bot_id=bot_id,
                    user_telegram_id=user_telegram_id,
                    template_version=template_version,
                )
                session.add(status)

            session.commit()

    @staticmethod
    def has_received_sync(bot_id: int, user_telegram_id: int) -> bool:
        from sqlalchemy import exists, select

        from .models import StartMessageStatus

        with SessionLocal() as session:
            stmt = select(
                exists().where(
                    (StartMessageStatus.bot_id == bot_id)
                    & (StartMessageStatus.user_telegram_id == user_telegram_id)
                )
            )
            return session.execute(stmt).scalar()

    @staticmethod
    def get_version_sync(bot_id: int, user_telegram_id: int) -> Optional[int]:
        from .models import StartMessageStatus

        with SessionLocal() as session:
            status = (
                session.query(StartMessageStatus)
                .filter(
                    StartMessageStatus.bot_id == bot_id,
                    StartMessageStatus.user_telegram_id == user_telegram_id,
                )
                .first()
            )
            return status.template_version if status else None


class UserActionStatusRepository:
    """Repository para status de ações por usuário"""

    @staticmethod
    async def get_or_create_status(
        bot_id: int,
        user_telegram_id: int,
        action_id: int,
    ) -> "UserActionStatus":
        """Busca ou cria status de ação para usuário"""
        from .models import UserActionStatus

        with SessionLocal() as session:
            status = (
                session.query(UserActionStatus)
                .filter(
                    UserActionStatus.bot_id == bot_id,
                    UserActionStatus.user_telegram_id == user_telegram_id,
                    UserActionStatus.action_id == action_id,
                )
                .first()
            )

            if not status:
                status = UserActionStatus(
                    bot_id=bot_id,
                    user_telegram_id=user_telegram_id,
                    action_id=action_id,
                    status="INACTIVE",
                )
                session.add(status)
                session.commit()
                session.refresh(status)

            return status

    @staticmethod
    async def get_user_action_statuses(
        bot_id: int,
        user_telegram_id: int,
        action_ids: List[int],
    ) -> dict:
        """Retorna status de múltiplas ações para um usuário"""
        from .models import UserActionStatus

        with SessionLocal() as session:
            statuses = (
                session.query(UserActionStatus)
                .filter(
                    UserActionStatus.bot_id == bot_id,
                    UserActionStatus.user_telegram_id == user_telegram_id,
                    UserActionStatus.action_id.in_(action_ids),
                )
                .all()
            )

            # Criar dict com status por action_id
            status_dict = {s.action_id: s.status for s in statuses}

            # Adicionar INACTIVE para ações sem registro
            for action_id in action_ids:
                if action_id not in status_dict:
                    status_dict[action_id] = "INACTIVE"

            return status_dict

    @staticmethod
    async def update_status_to_activated(
        bot_id: int,
        user_telegram_id: int,
        action_id: int,
    ) -> bool:
        """Atualiza status para ACTIVATED"""
        from datetime import datetime

        from .models import UserActionStatus

        with SessionLocal() as session:
            status = (
                session.query(UserActionStatus)
                .filter(
                    UserActionStatus.bot_id == bot_id,
                    UserActionStatus.user_telegram_id == user_telegram_id,
                    UserActionStatus.action_id == action_id,
                )
                .first()
            )

            if not status:
                # Criar novo com status ACTIVATED
                status = UserActionStatus(
                    bot_id=bot_id,
                    user_telegram_id=user_telegram_id,
                    action_id=action_id,
                    status="ACTIVATED",
                    last_triggered_at=datetime.utcnow(),
                )
                session.add(status)
            else:
                # Atualizar existente
                status.status = "ACTIVATED"
                status.last_triggered_at = datetime.utcnow()
                status.updated_at = datetime.utcnow()

            session.commit()
            return True

    @staticmethod
    async def reset_user_statuses(bot_id: int, user_telegram_id: int) -> bool:
        """Reseta todos os status de ações para INACTIVE"""
        from datetime import datetime

        from .models import UserActionStatus

        with SessionLocal() as session:
            statuses = (
                session.query(UserActionStatus)
                .filter(
                    UserActionStatus.bot_id == bot_id,
                    UserActionStatus.user_telegram_id == user_telegram_id,
                )
                .all()
            )

            for status in statuses:
                status.status = "INACTIVE"
                status.updated_at = datetime.utcnow()

            session.commit()
            return True

    @staticmethod
    def get_user_action_statuses_sync(
        bot_id: int,
        user_telegram_id: int,
        action_ids: List[int],
    ) -> dict:
        """Versão síncrona para workers"""
        from .models import UserActionStatus

        with SessionLocal() as session:
            statuses = (
                session.query(UserActionStatus)
                .filter(
                    UserActionStatus.bot_id == bot_id,
                    UserActionStatus.user_telegram_id == user_telegram_id,
                    UserActionStatus.action_id.in_(action_ids),
                )
                .all()
            )

            status_dict = {s.action_id: s.status for s in statuses}

            for action_id in action_ids:
                if action_id not in status_dict:
                    status_dict[action_id] = "INACTIVE"

            return status_dict


class UpsellRepository:
    """Repository para gerenciar Upsells"""

    @staticmethod
    async def get_upsells_by_bot(bot_id: int):
        """Retorna todos os upsells de um bot ordenados"""
        from .models import Upsell

        with SessionLocal() as session:
            upsells = (
                session.query(Upsell)
                .filter(Upsell.bot_id == bot_id, Upsell.is_active == True)  # noqa: E712
                .order_by(Upsell.order)
                .all()
            )
            return upsells

    @staticmethod
    async def get_upsell_by_id(upsell_id: int):
        """Retorna upsell por ID"""
        from .models import Upsell

        with SessionLocal() as session:
            return session.query(Upsell).filter(Upsell.id == upsell_id).first()

    @staticmethod
    def get_upsell_by_id_sync(upsell_id: int):
        """Versão síncrona"""
        from .models import Upsell

        with SessionLocal() as session:
            return session.query(Upsell).filter(Upsell.id == upsell_id).first()

    @staticmethod
    async def get_first_upsell(bot_id: int):
        """Retorna upsell #1 pré-salvo"""
        from .models import Upsell

        with SessionLocal() as session:
            return (
                session.query(Upsell)
                .filter(Upsell.bot_id == bot_id, Upsell.is_pre_saved.is_(True))
                .first()
            )

    @staticmethod
    def get_first_upsell_sync(bot_id: int):
        """Versão síncrona"""
        from .models import Upsell

        with SessionLocal() as session:
            return (
                session.query(Upsell)
                .filter(Upsell.bot_id == bot_id, Upsell.is_pre_saved.is_(True))
                .first()
            )

    @staticmethod
    async def create_upsell(
        bot_id: int, name: str, order: int, is_pre_saved: bool = False
    ):
        """Cria novo upsell"""
        from .models import Upsell

        with SessionLocal() as session:
            upsell = Upsell(
                bot_id=bot_id,
                name=name,
                order=order,
                is_pre_saved=is_pre_saved,
                is_active=True,
            )
            session.add(upsell)
            session.commit()
            session.refresh(upsell)
            return upsell

    @staticmethod
    async def create_default_upsell(bot_id: int):
        """Cria upsell #1 pré-salvo ao criar bot"""
        from .models import Upsell, UpsellSchedule

        with SessionLocal() as session:
            upsell = Upsell(
                bot_id=bot_id,
                name="Upsell Imediato",
                order=1,
                is_pre_saved=True,
                is_active=True,
            )
            session.add(upsell)
            session.flush()

            schedule = UpsellSchedule(upsell_id=upsell.id, is_immediate=True)
            session.add(schedule)
            session.commit()
            session.refresh(upsell)
            return upsell

    @staticmethod
    def create_default_upsell_sync(bot_id: int):
        """Versão síncrona"""
        from .models import Upsell, UpsellSchedule

        with SessionLocal() as session:
            upsell = Upsell(
                bot_id=bot_id,
                name="Upsell Imediato",
                order=1,
                is_pre_saved=True,
                is_active=True,
            )
            session.add(upsell)
            session.flush()

            schedule = UpsellSchedule(upsell_id=upsell.id, is_immediate=True)
            session.add(schedule)
            session.commit()
            session.refresh(upsell)
            return upsell

    @staticmethod
    async def update_upsell(upsell_id: int, **kwargs):
        """Atualiza campos do upsell"""
        from .models import Upsell

        with SessionLocal() as session:
            upsell = session.query(Upsell).filter(Upsell.id == upsell_id).first()
            if not upsell:
                return None

            for key, value in kwargs.items():
                if hasattr(upsell, key):
                    setattr(upsell, key, value)

            session.commit()
            session.refresh(upsell)
            return upsell

    @staticmethod
    async def delete_upsell(upsell_id: int):
        """Deleta upsell"""
        from .models import Upsell

        with SessionLocal() as session:
            upsell = session.query(Upsell).filter(Upsell.id == upsell_id).first()
            if upsell and not upsell.is_pre_saved:
                session.delete(upsell)
                session.commit()
                return True
            return False

    @staticmethod
    async def get_next_pending_upsell(bot_id: int, user_telegram_id: int):
        """Retorna próximo upsell não enviado"""
        from .models import Upsell, UserUpsellHistory

        with SessionLocal() as session:
            sent_upsells = (
                session.query(UserUpsellHistory.upsell_id)
                .filter(
                    UserUpsellHistory.bot_id == bot_id,
                    UserUpsellHistory.user_telegram_id == user_telegram_id,
                )
                .all()
            )
            sent_ids = [u[0] for u in sent_upsells]

            return (
                session.query(Upsell)
                .filter(
                    Upsell.bot_id == bot_id,
                    Upsell.is_active == True,  # noqa: E712
                    Upsell.id.notin_(sent_ids) if sent_ids else True,
                )
                .order_by(Upsell.order)
                .first()
            )

    @staticmethod
    def get_next_pending_upsell_sync(bot_id: int, user_telegram_id: int):
        """Versão síncrona - Retorna próximo upsell não enviado"""
        from .models import Upsell, UserUpsellHistory

        with SessionLocal() as session:
            sent_upsells = (
                session.query(UserUpsellHistory.upsell_id)
                .filter(
                    UserUpsellHistory.bot_id == bot_id,
                    UserUpsellHistory.user_telegram_id == user_telegram_id,
                )
                .all()
            )
            sent_ids = [u[0] for u in sent_upsells]

            return (
                session.query(Upsell)
                .filter(
                    Upsell.bot_id == bot_id,
                    Upsell.is_active == True,  # noqa: E712
                    Upsell.id.notin_(sent_ids) if sent_ids else True,
                )
                .order_by(Upsell.order)
                .first()
            )


class UpsellAnnouncementBlockRepository:
    """Repository para blocos de anúncio de upsell"""

    @staticmethod
    async def get_blocks_by_upsell(upsell_id: int):
        """Retorna blocos ordenados"""
        from .models import UpsellAnnouncementBlock

        with SessionLocal() as session:
            return (
                session.query(UpsellAnnouncementBlock)
                .filter(UpsellAnnouncementBlock.upsell_id == upsell_id)
                .order_by(UpsellAnnouncementBlock.order)
                .all()
            )

    @staticmethod
    def get_blocks_by_upsell_sync(upsell_id: int):
        """Versão síncrona"""
        from .models import UpsellAnnouncementBlock

        with SessionLocal() as session:
            return (
                session.query(UpsellAnnouncementBlock)
                .filter(UpsellAnnouncementBlock.upsell_id == upsell_id)
                .order_by(UpsellAnnouncementBlock.order)
                .all()
            )

    @staticmethod
    async def get_block_by_id(block_id: int):
        """Retorna bloco por ID"""
        from .models import UpsellAnnouncementBlock

        with SessionLocal() as session:
            return (
                session.query(UpsellAnnouncementBlock)
                .filter(UpsellAnnouncementBlock.id == block_id)
                .first()
            )

    @staticmethod
    def get_block_by_id_sync(block_id: int):
        """Versão síncrona - Retorna bloco por ID"""
        from .models import UpsellAnnouncementBlock

        with SessionLocal() as session:
            return (
                session.query(UpsellAnnouncementBlock)
                .filter(UpsellAnnouncementBlock.id == block_id)
                .first()
            )

    @staticmethod
    async def create_block(upsell_id: int, order: int, **kwargs):
        """Cria novo bloco"""
        from .models import UpsellAnnouncementBlock

        with SessionLocal() as session:
            block = UpsellAnnouncementBlock(
                upsell_id=upsell_id,
                order=order,
                text=kwargs.get("text"),
                media_file_id=kwargs.get("media_file_id"),
                media_type=kwargs.get("media_type"),
                delay_seconds=kwargs.get("delay_seconds", 0),
                auto_delete_seconds=kwargs.get("auto_delete_seconds", 0),
            )
            session.add(block)
            session.commit()
            session.refresh(block)
            return block

    @staticmethod
    async def update_block(block_id: int, **kwargs):
        """Atualiza bloco"""
        from .models import UpsellAnnouncementBlock

        with SessionLocal() as session:
            block = (
                session.query(UpsellAnnouncementBlock)
                .filter(UpsellAnnouncementBlock.id == block_id)
                .first()
            )
            if not block:
                return None

            for key, value in kwargs.items():
                if hasattr(block, key):
                    setattr(block, key, value)

            session.commit()
            session.refresh(block)
            return block

    @staticmethod
    async def delete_block(block_id: int):
        """Deleta bloco"""
        from .models import UpsellAnnouncementBlock

        with SessionLocal() as session:
            block = (
                session.query(UpsellAnnouncementBlock)
                .filter(UpsellAnnouncementBlock.id == block_id)
                .first()
            )
            if block:
                session.delete(block)
                session.commit()
                return True
            return False

    @staticmethod
    async def count_blocks(upsell_id: int) -> int:
        """Conta blocos de um upsell"""
        from .models import UpsellAnnouncementBlock

        with SessionLocal() as session:
            return (
                session.query(UpsellAnnouncementBlock)
                .filter(UpsellAnnouncementBlock.upsell_id == upsell_id)
                .count()
            )


class UpsellDeliverableBlockRepository:
    """Repository para blocos de entrega de upsell"""

    @staticmethod
    async def get_blocks_by_upsell(upsell_id: int):
        """Retorna blocos ordenados"""
        from .models import UpsellDeliverableBlock

        with SessionLocal() as session:
            return (
                session.query(UpsellDeliverableBlock)
                .filter(UpsellDeliverableBlock.upsell_id == upsell_id)
                .order_by(UpsellDeliverableBlock.order)
                .all()
            )

    @staticmethod
    def get_blocks_by_upsell_sync(upsell_id: int):
        """Versão síncrona"""
        from .models import UpsellDeliverableBlock

        with SessionLocal() as session:
            return (
                session.query(UpsellDeliverableBlock)
                .filter(UpsellDeliverableBlock.upsell_id == upsell_id)
                .order_by(UpsellDeliverableBlock.order)
                .all()
            )

    @staticmethod
    async def get_block_by_id(block_id: int):
        """Retorna bloco por ID"""
        from .models import UpsellDeliverableBlock

        with SessionLocal() as session:
            return (
                session.query(UpsellDeliverableBlock)
                .filter(UpsellDeliverableBlock.id == block_id)
                .first()
            )

    @staticmethod
    def get_block_by_id_sync(block_id: int):
        """Versão síncrona - Retorna bloco por ID"""
        from .models import UpsellDeliverableBlock

        with SessionLocal() as session:
            return (
                session.query(UpsellDeliverableBlock)
                .filter(UpsellDeliverableBlock.id == block_id)
                .first()
            )

    @staticmethod
    async def create_block(upsell_id: int, order: int, **kwargs):
        """Cria novo bloco"""
        from .models import UpsellDeliverableBlock

        with SessionLocal() as session:
            block = UpsellDeliverableBlock(
                upsell_id=upsell_id,
                order=order,
                text=kwargs.get("text"),
                media_file_id=kwargs.get("media_file_id"),
                media_type=kwargs.get("media_type"),
                delay_seconds=kwargs.get("delay_seconds", 0),
                auto_delete_seconds=kwargs.get("auto_delete_seconds", 0),
            )
            session.add(block)
            session.commit()
            session.refresh(block)
            return block

    @staticmethod
    async def update_block(block_id: int, **kwargs):
        """Atualiza bloco"""
        from .models import UpsellDeliverableBlock

        with SessionLocal() as session:
            block = (
                session.query(UpsellDeliverableBlock)
                .filter(UpsellDeliverableBlock.id == block_id)
                .first()
            )
            if not block:
                return None

            for key, value in kwargs.items():
                if hasattr(block, key):
                    setattr(block, key, value)

            session.commit()
            session.refresh(block)
            return block

    @staticmethod
    async def delete_block(block_id: int):
        """Deleta bloco"""
        from .models import UpsellDeliverableBlock

        with SessionLocal() as session:
            block = (
                session.query(UpsellDeliverableBlock)
                .filter(UpsellDeliverableBlock.id == block_id)
                .first()
            )
            if block:
                session.delete(block)
                session.commit()
                return True
            return False

    @staticmethod
    async def count_blocks(upsell_id: int) -> int:
        """Conta blocos de um upsell"""
        from .models import UpsellDeliverableBlock

        with SessionLocal() as session:
            return (
                session.query(UpsellDeliverableBlock)
                .filter(UpsellDeliverableBlock.upsell_id == upsell_id)
                .count()
            )


class UpsellPhaseConfigRepository:
    """Repository para configuração de fase de upsell"""

    @staticmethod
    async def get_phase_config(upsell_id: int):
        """Retorna configuração de fase"""
        from .models import UpsellPhaseConfig

        with SessionLocal() as session:
            return (
                session.query(UpsellPhaseConfig)
                .filter(UpsellPhaseConfig.upsell_id == upsell_id)
                .first()
            )

    @staticmethod
    def get_phase_config_sync(upsell_id: int):
        """Versão síncrona"""
        from .models import UpsellPhaseConfig

        with SessionLocal() as session:
            return (
                session.query(UpsellPhaseConfig)
                .filter(UpsellPhaseConfig.upsell_id == upsell_id)
                .first()
            )

    @staticmethod
    async def create_or_update_phase(upsell_id: int, phase_prompt: str):
        """Cria ou atualiza configuração de fase"""
        from .models import UpsellPhaseConfig

        with SessionLocal() as session:
            config = (
                session.query(UpsellPhaseConfig)
                .filter(UpsellPhaseConfig.upsell_id == upsell_id)
                .first()
            )

            if config:
                config.phase_prompt = phase_prompt
            else:
                config = UpsellPhaseConfig(
                    upsell_id=upsell_id, phase_prompt=phase_prompt
                )
                session.add(config)

            session.commit()
            session.refresh(config)
            return config

    @staticmethod
    async def delete_phase_config(upsell_id: int):
        """Deleta configuração de fase"""
        from .models import UpsellPhaseConfig

        with SessionLocal() as session:
            config = (
                session.query(UpsellPhaseConfig)
                .filter(UpsellPhaseConfig.upsell_id == upsell_id)
                .first()
            )
            if config:
                session.delete(config)
                session.commit()
                return True
            return False


class UpsellScheduleRepository:
    """Repository para agendamento de upsell"""

    @staticmethod
    async def get_schedule(upsell_id: int):
        """Retorna agendamento"""
        from .models import UpsellSchedule

        with SessionLocal() as session:
            return (
                session.query(UpsellSchedule)
                .filter(UpsellSchedule.upsell_id == upsell_id)
                .first()
            )

    @staticmethod
    def get_schedule_sync(upsell_id: int):
        """Versão síncrona"""
        from .models import UpsellSchedule

        with SessionLocal() as session:
            return (
                session.query(UpsellSchedule)
                .filter(UpsellSchedule.upsell_id == upsell_id)
                .first()
            )

    @staticmethod
    async def create_schedule(upsell_id: int, **kwargs):
        """Cria agendamento"""
        from .models import UpsellSchedule

        with SessionLocal() as session:
            schedule = UpsellSchedule(
                upsell_id=upsell_id,
                is_immediate=kwargs.get("is_immediate", False),
                days_after=kwargs.get("days_after", 0),
                hours=kwargs.get("hours", 0),
                minutes=kwargs.get("minutes", 0),
            )
            session.add(schedule)
            session.commit()
            session.refresh(schedule)
            return schedule

    @staticmethod
    async def update_schedule(upsell_id: int, **kwargs):
        """Atualiza agendamento"""
        from .models import UpsellSchedule

        with SessionLocal() as session:
            schedule = (
                session.query(UpsellSchedule)
                .filter(UpsellSchedule.upsell_id == upsell_id)
                .first()
            )
            if not schedule:
                return None

            for key, value in kwargs.items():
                if hasattr(schedule, key):
                    setattr(schedule, key, value)

            session.commit()
            session.refresh(schedule)
            return schedule


class UserUpsellHistoryRepository:
    """Repository para histórico de upsells por usuário"""

    @staticmethod
    async def get_user_history(bot_id: int, user_telegram_id: int):
        """Retorna histórico do usuário"""
        from .models import UserUpsellHistory

        with SessionLocal() as session:
            return (
                session.query(UserUpsellHistory)
                .filter(
                    UserUpsellHistory.bot_id == bot_id,
                    UserUpsellHistory.user_telegram_id == user_telegram_id,
                )
                .all()
            )

    @staticmethod
    def get_user_history_sync(bot_id: int, user_telegram_id: int):
        """Versão síncrona"""
        from .models import UserUpsellHistory

        with SessionLocal() as session:
            return (
                session.query(UserUpsellHistory)
                .filter(
                    UserUpsellHistory.bot_id == bot_id,
                    UserUpsellHistory.user_telegram_id == user_telegram_id,
                )
                .all()
            )

    @staticmethod
    async def mark_sent(bot_id: int, user_telegram_id: int, upsell_id: int):
        """Marca upsell como enviado"""
        from datetime import datetime

        from .models import UserUpsellHistory

        with SessionLocal() as session:
            history = UserUpsellHistory(
                bot_id=bot_id,
                user_telegram_id=user_telegram_id,
                upsell_id=upsell_id,
                sent_at=datetime.utcnow(),
            )
            session.add(history)
            session.commit()
            return history

    @staticmethod
    def mark_sent_sync(bot_id: int, user_telegram_id: int, upsell_id: int):
        """Versão síncrona"""
        from datetime import datetime

        from .models import UserUpsellHistory

        with SessionLocal() as session:
            # Verificar se já existe
            existing = (
                session.query(UserUpsellHistory)
                .filter(
                    UserUpsellHistory.bot_id == bot_id,
                    UserUpsellHistory.user_telegram_id == user_telegram_id,
                    UserUpsellHistory.upsell_id == upsell_id,
                )
                .first()
            )

            if existing:
                existing.sent_at = datetime.utcnow()
                session.commit()
                return existing

            history = UserUpsellHistory(
                bot_id=bot_id,
                user_telegram_id=user_telegram_id,
                upsell_id=upsell_id,
                sent_at=datetime.utcnow(),
            )
            session.add(history)
            session.commit()
            return history

    @staticmethod
    async def mark_paid(
        bot_id: int, user_telegram_id: int, upsell_id: int, transaction_id: str
    ):
        """Marca upsell como pago"""
        from datetime import datetime

        from .models import UserUpsellHistory

        with SessionLocal() as session:
            history = (
                session.query(UserUpsellHistory)
                .filter(
                    UserUpsellHistory.bot_id == bot_id,
                    UserUpsellHistory.user_telegram_id == user_telegram_id,
                    UserUpsellHistory.upsell_id == upsell_id,
                )
                .first()
            )

            if history:
                history.paid_at = datetime.utcnow()
                history.transaction_id = transaction_id
                session.commit()
                return history

            return None

    @staticmethod
    def mark_paid_sync(
        bot_id: int, user_telegram_id: int, upsell_id: int, transaction_id: str
    ):
        """Versão síncrona"""
        from datetime import datetime

        from .models import UserUpsellHistory

        with SessionLocal() as session:
            history = (
                session.query(UserUpsellHistory)
                .filter(
                    UserUpsellHistory.bot_id == bot_id,
                    UserUpsellHistory.user_telegram_id == user_telegram_id,
                    UserUpsellHistory.upsell_id == upsell_id,
                )
                .first()
            )

            if history:
                history.paid_at = datetime.utcnow()
                history.transaction_id = transaction_id
                session.commit()
                return history

            return None

    @staticmethod
    async def get_last_payment_time(bot_id: int, user_telegram_id: int):
        """Retorna timestamp do último pagamento"""
        from .models import UserUpsellHistory

        with SessionLocal() as session:
            history = (
                session.query(UserUpsellHistory)
                .filter(
                    UserUpsellHistory.bot_id == bot_id,
                    UserUpsellHistory.user_telegram_id == user_telegram_id,
                    UserUpsellHistory.paid_at.isnot(None),
                )
                .order_by(UserUpsellHistory.paid_at.desc())
                .first()
            )
            return history.paid_at if history else None

    @staticmethod
    async def has_received_upsell(
        bot_id: int, user_telegram_id: int, upsell_id: int
    ) -> bool:
        """Verifica se usuário já recebeu upsell"""
        from .models import UserUpsellHistory

        with SessionLocal() as session:
            return (
                session.query(UserUpsellHistory)
                .filter(
                    UserUpsellHistory.bot_id == bot_id,
                    UserUpsellHistory.user_telegram_id == user_telegram_id,
                    UserUpsellHistory.upsell_id == upsell_id,
                )
                .count()
                > 0
            )


class AntiSpamConfigRepository:
    """Repository para configurações de anti-spam"""

    @staticmethod
    async def get_or_create(bot_id: int):
        """Busca ou cria configuração de anti-spam"""
        from .models import BotAntiSpamConfig

        with SessionLocal() as session:
            config = (
                session.query(BotAntiSpamConfig)
                .filter(BotAntiSpamConfig.bot_id == bot_id)
                .first()
            )

            if not config:
                # Cria com valores padrão
                config = BotAntiSpamConfig(bot_id=bot_id)
                session.add(config)
                session.commit()
                session.refresh(config)

            return config

    @staticmethod
    def get_by_bot_id_sync(bot_id: int):
        """Busca configuração (sync para workers)"""
        from .models import BotAntiSpamConfig

        with SessionLocal() as session:
            return (
                session.query(BotAntiSpamConfig)
                .filter(BotAntiSpamConfig.bot_id == bot_id)
                .first()
            )

    @staticmethod
    async def update_config(bot_id: int, **kwargs) -> bool:
        """Atualiza configuração"""
        from datetime import datetime

        from .models import BotAntiSpamConfig

        with SessionLocal() as session:
            config = (
                session.query(BotAntiSpamConfig)
                .filter(BotAntiSpamConfig.bot_id == bot_id)
                .first()
            )

            if config:
                for key, value in kwargs.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
                config.updated_at = datetime.utcnow()
                session.commit()
                return True
            return False

    @staticmethod
    async def toggle_protection(bot_id: int, protection: str) -> bool:
        """Alterna status de uma proteção"""
        from .models import BotAntiSpamConfig

        with SessionLocal() as session:
            config = (
                session.query(BotAntiSpamConfig)
                .filter(BotAntiSpamConfig.bot_id == bot_id)
                .first()
            )

            if config and hasattr(config, protection):
                current_value = getattr(config, protection)
                setattr(config, protection, not current_value)
                session.commit()
                return not current_value  # Retorna o novo valor
            return False

    @staticmethod
    def to_dict(config) -> dict:
        """Converte config para dicionário"""
        if not config:
            return {}

        return {
            "dot_after_start": config.dot_after_start,
            "repetition": config.repetition,
            "flood": config.flood,
            "links_mentions": config.links_mentions,
            "short_messages": config.short_messages,
            "loop_start": config.loop_start,
            "total_limit": config.total_limit,
            "total_limit_value": config.total_limit_value,
            "forward_spam": config.forward_spam,
            "emoji_flood": config.emoji_flood,
            "char_repetition": config.char_repetition,
            "bot_speed": config.bot_speed,
            "media_spam": config.media_spam,
            "sticker_spam": config.sticker_spam,
            "contact_spam": config.contact_spam,
            "location_spam": config.location_spam,
        }
