"""
Repository Pattern para acesso ao banco
"""

import os
from typing import List, Optional

from sqlalchemy import create_engine, func
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
                    Offer.is_active == True,
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
                query = query.filter(Offer.is_active == True)
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
        offer_id: int,
        transaction_id: str,
        qr_code: str,
        value_cents: int,
        qr_code_base64: str = None,
    ):
        """Cria nova transação PIX"""
        from .models import PixTransaction

        with SessionLocal() as session:
            transaction = PixTransaction(
                bot_id=bot_id,
                user_telegram_id=user_telegram_id,
                chat_id=chat_id,
                offer_id=offer_id,
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
