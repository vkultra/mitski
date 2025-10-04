"""
Repository Pattern para acesso ao banco
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from .models import Bot, User
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# Configuração do engine
engine = create_engine(
    os.environ.get('DB_URL', 'postgresql+psycopg://admin:senha_segura@localhost:5432/telegram_bots'),
    pool_size=int(os.environ.get('DB_POOL_SIZE', 20)),
    max_overflow=int(os.environ.get('DB_MAX_OVERFLOW', 40)),
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False
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
            user = session.query(User).filter(
                User.telegram_id == telegram_id,
                User.bot_id == bot_id
            ).first()

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
            user = session.query(User).filter(
                User.telegram_id == telegram_id,
                User.bot_id == bot_id
            ).first()

            if user:
                from datetime import datetime
                user.last_interaction = datetime.utcnow()
                session.commit()
