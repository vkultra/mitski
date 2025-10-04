"""
SQLAlchemy Models
"""
from sqlalchemy import (
    Column, Integer, String, BigInteger, Boolean,
    DateTime, ForeignKey, Index, LargeBinary, func
)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Bot(Base):
    """Modelo de Bot Secundário"""
    __tablename__ = 'bots'

    id = Column(Integer, primary_key=True)
    admin_id = Column(BigInteger, nullable=False, index=True)
    token = Column(LargeBinary, nullable=False)  # criptografado
    username = Column(String(64), unique=True)
    webhook_secret = Column(String(128))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        Index('idx_admin_active', 'admin_id', 'is_active'),
    )


class User(Base):
    """Modelo de Usuário"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    bot_id = Column(Integer, ForeignKey('bots.id'), nullable=False)
    username = Column(String(64))
    first_name = Column(String(128))
    last_name = Column(String(128))
    first_interaction = Column(DateTime, server_default=func.now())
    last_interaction = Column(DateTime, onupdate=func.now())
    is_blocked = Column(Boolean, default=False)

    __table_args__ = (
        Index('idx_bot_user', 'bot_id', 'telegram_id'),
    )


class Event(Base):
    """Modelo de Evento/Log"""
    __tablename__ = 'events'

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey('bots.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'))
    event_type = Column(String(64), nullable=False)
    payload = Column(String(2048))
    created_at = Column(DateTime, server_default=func.now(), index=True)

    __table_args__ = (
        Index('idx_bot_event_ts', 'bot_id', 'event_type', 'created_at'),
    )
