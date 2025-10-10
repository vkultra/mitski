"""Repository helpers for tracker link CRUD and configs."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import func

from database.tracking_db import TrackerDTO, session_scope
from database.tracking_models import BotTrackingConfig, TrackerLink


def create_tracker(*, admin_id: int, bot_id: int, name: str, code: str) -> TrackerDTO:
    with session_scope() as session:
        tracker = TrackerLink(
            admin_id=admin_id,
            bot_id=bot_id,
            name=name,
            code=code,
            is_active=True,
        )
        session.add(tracker)
        session.flush()
        session.refresh(tracker)
        return TrackerDTO(
            id=tracker.id,
            bot_id=tracker.bot_id,
            admin_id=tracker.admin_id,
            name=tracker.name,
            code=tracker.code,
            is_active=tracker.is_active,
            created_at=tracker.created_at,
        )


def list_trackers(
    *,
    admin_id: int,
    bot_id: Optional[int] = None,
    include_inactive: bool = False,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> List[TrackerDTO]:
    with session_scope() as session:
        query = session.query(TrackerLink).filter(TrackerLink.admin_id == admin_id)
        if bot_id is not None:
            query = query.filter(TrackerLink.bot_id == bot_id)
        if not include_inactive:
            query = query.filter(TrackerLink.is_active.is_(True))
        query = query.order_by(TrackerLink.created_at.desc())
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        items = query.all()
        return [
            TrackerDTO(
                id=i.id,
                bot_id=i.bot_id,
                admin_id=i.admin_id,
                name=i.name,
                code=i.code,
                is_active=i.is_active,
                created_at=i.created_at,
            )
            for i in items
        ]


def count_trackers(*, admin_id: int, bot_id: Optional[int] = None) -> int:
    with session_scope() as session:
        query = session.query(func.count(TrackerLink.id)).filter(
            TrackerLink.admin_id == admin_id,
            TrackerLink.is_active.is_(True),
        )
        if bot_id is not None:
            query = query.filter(TrackerLink.bot_id == bot_id)
        return int(query.scalar() or 0)


def count_active_by_bot(bot_id: int) -> int:
    with session_scope() as session:
        total = (
            session.query(func.count(TrackerLink.id))
            .filter(TrackerLink.bot_id == bot_id, TrackerLink.is_active.is_(True))
            .scalar()
        )
        return int(total or 0)


def get_tracker_by_id(tracker_id: int) -> Optional[TrackerDTO]:
    with session_scope() as session:
        tracker = (
            session.query(TrackerLink).filter(TrackerLink.id == tracker_id).first()
        )
        if not tracker:
            return None
        return TrackerDTO(
            id=tracker.id,
            bot_id=tracker.bot_id,
            admin_id=tracker.admin_id,
            name=tracker.name,
            code=tracker.code,
            is_active=tracker.is_active,
            created_at=tracker.created_at,
        )


def get_tracker_by_code(bot_id: int, code: str) -> Optional[TrackerDTO]:
    with session_scope() as session:
        tracker = (
            session.query(TrackerLink)
            .filter(
                TrackerLink.bot_id == bot_id,
                TrackerLink.code == code,
                TrackerLink.is_active.is_(True),
            )
            .first()
        )
        if not tracker:
            return None
        return TrackerDTO(
            id=tracker.id,
            bot_id=tracker.bot_id,
            admin_id=tracker.admin_id,
            name=tracker.name,
            code=tracker.code,
            is_active=tracker.is_active,
            created_at=tracker.created_at,
        )


def soft_delete_tracker(tracker_id: int, *, admin_id: int) -> bool:
    with session_scope() as session:
        tracker = (
            session.query(TrackerLink)
            .filter(
                TrackerLink.id == tracker_id,
                TrackerLink.admin_id == admin_id,
                TrackerLink.is_active.is_(True),
            )
            .first()
        )
        if not tracker:
            return False
        tracker.is_active = False
        tracker.deleted_at = datetime.utcnow()
        session.add(tracker)
        return True


def get_bot_config(bot_id: int) -> Optional[bool]:
    with session_scope() as session:
        config = (
            session.query(BotTrackingConfig)
            .filter(BotTrackingConfig.bot_id == bot_id)
            .first()
        )
        if not config:
            return None
        return bool(config.ignore_untracked_starts)


def set_bot_config(bot_id: int, *, ignore_untracked: bool) -> None:
    with session_scope() as session:
        config = (
            session.query(BotTrackingConfig)
            .filter(BotTrackingConfig.bot_id == bot_id)
            .first()
        )
        if not config:
            config = BotTrackingConfig(bot_id=bot_id)
            session.add(config)
            session.flush()
        config.ignore_untracked_starts = ignore_untracked
        config.last_forced_at = datetime.utcnow()
        session.add(config)


def batch_tracker_ids_for_bot(bot_id: int) -> List[int]:
    with session_scope() as session:
        rows = (
            session.query(TrackerLink.id)
            .filter(TrackerLink.bot_id == bot_id, TrackerLink.is_active.is_(True))
            .all()
        )
        return [int(row[0]) for row in rows]


__all__ = [
    "TrackerDTO",
    "create_tracker",
    "list_trackers",
    "count_trackers",
    "count_active_by_bot",
    "get_tracker_by_id",
    "get_tracker_by_code",
    "soft_delete_tracker",
    "get_bot_config",
    "set_bot_config",
    "batch_tracker_ids_for_bot",
]
