"""
SQLAlchemy Models
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    func,
)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Bot(Base):
    """Modelo de Bot Secundário"""

    __tablename__ = "bots"

    id = Column(Integer, primary_key=True)
    admin_id = Column(BigInteger, nullable=False, index=True)
    token = Column(LargeBinary, nullable=False)  # criptografado
    username = Column(String(64), unique=True)
    display_name = Column(String(128))  # nome customizado pelo admin
    webhook_secret = Column(String(128))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (Index("idx_admin_active", "admin_id", "is_active"),)


class User(Base):
    """Modelo de Usuário"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False)
    username = Column(String(64))
    first_name = Column(String(128))
    last_name = Column(String(128))
    first_interaction = Column(DateTime, server_default=func.now())
    last_interaction = Column(DateTime, onupdate=func.now())
    is_blocked = Column(Boolean, default=False)

    __table_args__ = (Index("idx_bot_user", "bot_id", "telegram_id"),)


class Event(Base):
    """Modelo de Evento/Log"""

    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    event_type = Column(String(64), nullable=False)
    payload = Column(String(2048))
    created_at = Column(DateTime, server_default=func.now(), index=True)

    __table_args__ = (Index("idx_bot_event_ts", "bot_id", "event_type", "created_at"),)


class BotAIConfig(Base):
    """Configuração de IA por bot"""

    __tablename__ = "bot_ai_configs"

    id = Column(Integer, primary_key=True)
    bot_id = Column(
        Integer, ForeignKey("bots.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    model_type = Column(
        String(32), default="reasoning"
    )  # 'reasoning' ou 'non-reasoning'
    general_prompt = Column(String(4096))  # Comportamento geral da IA
    temperature = Column(String(8), default="0.7")
    max_tokens = Column(Integer, default=2000)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class AIPhase(Base):
    """Fases da IA com triggers"""

    __tablename__ = "ai_phases"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    phase_trigger = Column(
        String(32), nullable=False
    )  # Termo único (ex: "fcf4", "eko3")
    phase_prompt = Column(String(4096), nullable=False)  # Prompt da fase
    order = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (Index("idx_bot_trigger", "bot_id", "phase_trigger", unique=True),)


class ConversationHistory(Base):
    """Histórico de conversa com IA"""

    __tablename__ = "conversation_history"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    user_telegram_id = Column(BigInteger, nullable=False)
    role = Column(String(16), nullable=False)  # 'system', 'user', 'assistant'
    content = Column(String(8192), nullable=False)
    has_image = Column(Boolean, default=False)
    image_url = Column(String(512))

    # Métricas de tokens (economia com cache!)
    prompt_tokens = Column(Integer, default=0)
    cached_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    reasoning_tokens = Column(Integer, default=0)

    created_at = Column(DateTime, server_default=func.now(), index=True)

    __table_args__ = (
        Index("idx_bot_user_created", "bot_id", "user_telegram_id", "created_at"),
    )


class UserAISession(Base):
    """Sessão de IA do usuário"""

    __tablename__ = "user_ai_sessions"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    user_telegram_id = Column(BigInteger, nullable=False)
    current_phase_id = Column(Integer, ForeignKey("ai_phases.id", ondelete="SET NULL"))
    message_count = Column(Integer, default=0)
    last_interaction = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_bot_user_session", "bot_id", "user_telegram_id", unique=True),
    )
