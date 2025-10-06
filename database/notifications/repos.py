"""Repositórios dedicados à lógica de notificações de vendas."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, Optional, Tuple

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert

from core.telemetry import logger
from database.notifications.models import NotificationSettings, SaleNotification
from database.repos import SessionLocal


class NotificationSettingsRepository:
    """Operações de persistência para configurações de notificação."""

    @staticmethod
    def get_for_owner_sync(
        owner_user_id: int, bot_id: Optional[int]
    ) -> Optional[NotificationSettings]:
        with SessionLocal() as session:
            query = session.query(NotificationSettings).filter(
                NotificationSettings.owner_user_id == owner_user_id
            )
            if bot_id is None:
                query = query.filter(NotificationSettings.bot_id.is_(None))
            else:
                query = query.filter(NotificationSettings.bot_id == bot_id)
            return query.first()

    @staticmethod
    def get_default_sync(owner_user_id: int) -> Optional[NotificationSettings]:
        with SessionLocal() as session:
            return (
                session.query(NotificationSettings)
                .filter(
                    NotificationSettings.owner_user_id == owner_user_id,
                    NotificationSettings.bot_id.is_(None),
                )
                .first()
            )

    @staticmethod
    def list_for_owner_sync(
        owner_user_id: int,
    ) -> Iterable[NotificationSettings]:
        with SessionLocal() as session:
            return (
                session.query(NotificationSettings)
                .filter(NotificationSettings.owner_user_id == owner_user_id)
                .order_by(NotificationSettings.bot_id.nullsfirst())
                .all()
            )

    @staticmethod
    def upsert_channel_sync(
        owner_user_id: int,
        channel_id: int,
        bot_id: Optional[int] = None,
    ) -> NotificationSettings:
        with SessionLocal() as session:
            query = session.query(NotificationSettings).filter(
                NotificationSettings.owner_user_id == owner_user_id
            )
            if bot_id is None:
                query = query.filter(NotificationSettings.bot_id.is_(None))
            else:
                query = query.filter(NotificationSettings.bot_id == bot_id)
            record = query.first()

            if record:
                record.channel_id = channel_id
                record.enabled = True
                record.updated_at = datetime.utcnow()
            else:
                record = NotificationSettings(
                    owner_user_id=owner_user_id,
                    bot_id=bot_id,
                    channel_id=channel_id,
                    enabled=True,
                )
                session.add(record)

            session.commit()
            session.refresh(record)
            return record

    @staticmethod
    def disable_sync(owner_user_id: int, bot_id: Optional[int]) -> bool:
        with SessionLocal() as session:
            query = session.query(NotificationSettings).filter(
                NotificationSettings.owner_user_id == owner_user_id
            )
            if bot_id is None:
                query = query.filter(NotificationSettings.bot_id.is_(None))
            else:
                query = query.filter(NotificationSettings.bot_id == bot_id)
            record = query.first()
            if not record:
                return False

            record.enabled = False
            record.updated_at = datetime.utcnow()
            session.commit()
            return True

    @staticmethod
    def delete_sync(owner_user_id: int, bot_id: Optional[int]) -> bool:
        with SessionLocal() as session:
            query = session.query(NotificationSettings).filter(
                NotificationSettings.owner_user_id == owner_user_id
            )
            if bot_id is None:
                query = query.filter(NotificationSettings.bot_id.is_(None))
            else:
                query = query.filter(NotificationSettings.bot_id == bot_id)
            record = query.first()
            if not record:
                return False

            session.delete(record)
            session.commit()
            return True

    # --- Wrappers assíncronos -------------------------------------------------

    @staticmethod
    async def get_for_owner(
        owner_user_id: int, bot_id: Optional[int]
    ) -> Optional[NotificationSettings]:
        return NotificationSettingsRepository.get_for_owner_sync(owner_user_id, bot_id)

    @staticmethod
    async def get_default(owner_user_id: int) -> Optional[NotificationSettings]:
        return NotificationSettingsRepository.get_default_sync(owner_user_id)

    @staticmethod
    async def list_for_owner(owner_user_id: int) -> Iterable[NotificationSettings]:
        return NotificationSettingsRepository.list_for_owner_sync(owner_user_id)

    @staticmethod
    async def upsert_channel(
        owner_user_id: int,
        channel_id: int,
        bot_id: Optional[int] = None,
    ) -> NotificationSettings:
        return NotificationSettingsRepository.upsert_channel_sync(
            owner_user_id, channel_id, bot_id
        )

    @staticmethod
    async def disable(owner_user_id: int, bot_id: Optional[int]) -> bool:
        return NotificationSettingsRepository.disable_sync(owner_user_id, bot_id)

    @staticmethod
    async def delete(owner_user_id: int, bot_id: Optional[int]) -> bool:
        return NotificationSettingsRepository.delete_sync(owner_user_id, bot_id)


class SaleNotificationsRepository:
    """Controle dos registros de notificações de vendas."""

    @staticmethod
    def create_if_absent_sync(data: Dict) -> Tuple[Optional[SaleNotification], bool]:
        transaction_id = data.get("transaction_id")
        provider = data.get("provider", "") or ""

        stmt = (
            insert(SaleNotification)
            .values({**data, "provider": provider})
            .on_conflict_do_nothing(index_elements=[SaleNotification.transaction_id])
            .returning(SaleNotification.id)
        )

        with SessionLocal() as session:
            result = session.execute(stmt).scalar_one_or_none()
            if result is None:
                session.rollback()
                existing = (
                    session.query(SaleNotification)
                    .filter(
                        SaleNotification.transaction_id == transaction_id,
                    )
                    .first()
                )
                if existing:
                    logger.debug(
                        "Sale notification already registered",
                        extra={
                            "transaction_id": transaction_id,
                            "sale_notification_id": existing.id,
                        },
                    )
                return existing, False

            session.commit()
            record = session.get(SaleNotification, result)
            return record, True

    @staticmethod
    def mark_status_sync(
        transaction_id: str,
        status: str,
        *,
        error: Optional[str] = None,
        notified_at: Optional[datetime] = None,
    ) -> None:
        with SessionLocal() as session:
            session.execute(
                update(SaleNotification)
                .where(
                    SaleNotification.transaction_id == transaction_id,
                )
                .values(
                    status=status,
                    error=error,
                    notified_at=notified_at,
                    updated_at=datetime.utcnow(),
                )
            )
            session.commit()

    @staticmethod
    def get_by_transaction_sync(transaction_id: str) -> Optional[SaleNotification]:
        with SessionLocal() as session:
            return (
                session.query(SaleNotification)
                .filter(
                    SaleNotification.transaction_id == transaction_id,
                )
                .first()
            )

    @staticmethod
    def list_recent_for_owner_sync(owner_user_id: int, limit: int = 20):
        with SessionLocal() as session:
            return (
                session.query(SaleNotification)
                .filter(SaleNotification.owner_user_id == owner_user_id)
                .order_by(SaleNotification.created_at.desc())
                .limit(limit)
                .all()
            )


__all__ = [
    "NotificationSettingsRepository",
    "SaleNotificationsRepository",
]
