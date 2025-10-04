"""
Repository Pattern para acesso ao banco
"""

import os
from typing import List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.telemetry import logger

from .models import Bot, User

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
        """Desativa bot"""
        with SessionLocal() as session:
            bot = session.query(Bot).filter(Bot.id == bot_id).first()
            if bot:
                bot.is_active = False
                session.commit()
                return True
            return False


class UserRepository:
    """Repository para operações com User"""

    @staticmethod
    async def get_or_create_user(telegram_id: int, bot_id: int, **kwargs) -> User:
        """Busca ou cria usuário"""
        with SessionLocal() as session:
            user = (
                session.query(User)
                .filter(User.telegram_id == telegram_id, User.bot_id == bot_id)
                .first()
            )

            if not user:
                user = User(telegram_id=telegram_id, bot_id=bot_id, **kwargs)
                session.add(user)
                session.commit()
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
