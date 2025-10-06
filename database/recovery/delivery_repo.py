"""Repo para entregas/agendamentos de recuperação."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import asc
from sqlalchemy.orm import joinedload

from database.models import RecoveryDelivery
from database.repos import SessionLocal


class RecoveryDeliveryRepository:
    """Helpers para criar, listar e atualizar entregas."""

    @staticmethod
    async def create_or_update(**values) -> RecoveryDelivery:
        with SessionLocal() as session:
            query = session.query(RecoveryDelivery).filter_by(
                bot_id=values.get("bot_id"),
                user_id=values.get("user_id"),
                step_id=values.get("step_id"),
                episode_id=values.get("episode_id"),
            )
            delivery = query.first()
            if delivery:
                for key, value in values.items():
                    if hasattr(delivery, key):
                        setattr(delivery, key, value)
            else:
                delivery = RecoveryDelivery(**values)
                session.add(delivery)
            session.commit()
            session.refresh(delivery)
            return delivery

    @staticmethod
    async def list_pending(bot_id: int, user_id: int) -> List[RecoveryDelivery]:
        with SessionLocal() as session:
            return (
                session.query(RecoveryDelivery)
                .options(joinedload(RecoveryDelivery.step))
                .filter(
                    RecoveryDelivery.bot_id == bot_id,
                    RecoveryDelivery.user_id == user_id,
                    RecoveryDelivery.status == "scheduled",
                )
                .order_by(asc(RecoveryDelivery.scheduled_for))
                .all()
            )

    @staticmethod
    async def get_delivery(
        bot_id: int, user_id: int, step_id: int, episode_id: str
    ) -> Optional[RecoveryDelivery]:
        with SessionLocal() as session:
            return (
                session.query(RecoveryDelivery)
                .filter(
                    RecoveryDelivery.bot_id == bot_id,
                    RecoveryDelivery.user_id == user_id,
                    RecoveryDelivery.step_id == step_id,
                    RecoveryDelivery.episode_id == episode_id,
                )
                .first()
            )

    @staticmethod
    async def update_status(delivery_id: int, status: str, **fields) -> None:
        with SessionLocal() as session:
            update_fields = {RecoveryDelivery.status: status}
            for key, value in fields.items():
                column = getattr(RecoveryDelivery, key, None)
                if column is not None:
                    update_fields[column] = value
            session.query(RecoveryDelivery).filter(
                RecoveryDelivery.id == delivery_id
            ).update(update_fields)
            session.commit()

    @staticmethod
    async def delete_episode(bot_id: int, user_id: int, episode_id: str) -> None:
        with SessionLocal() as session:
            session.query(RecoveryDelivery).filter(
                RecoveryDelivery.bot_id == bot_id,
                RecoveryDelivery.user_id == user_id,
                RecoveryDelivery.episode_id == episode_id,
            ).delete(synchronize_session=False)
            session.commit()
