"""Persistence helpers for tracker statistics and attributions."""

from __future__ import annotations

from datetime import date
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from database.tracking_db import DailyStatDTO, session_scope
from database.tracking_models import TrackerAttribution, TrackerDailyStat, TrackerLink


def upsert_daily_stats(
    *,
    tracker_id: int,
    day: date,
    starts_delta: int = 0,
    sales_delta: int = 0,
    revenue_delta: int = 0,
) -> None:
    if not any((starts_delta, sales_delta, revenue_delta)):
        return
    with session_scope() as session:
        stmt = insert(TrackerDailyStat).values(
            tracker_id=tracker_id,
            day=day,
            starts=starts_delta,
            sales=sales_delta,
            revenue_cents=revenue_delta,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[TrackerDailyStat.tracker_id, TrackerDailyStat.day],
            set_={
                "starts": TrackerDailyStat.starts + starts_delta,
                "sales": TrackerDailyStat.sales + sales_delta,
                "revenue_cents": TrackerDailyStat.revenue_cents + revenue_delta,
                "updated_at": func.now(),
            },
        )
        session.execute(stmt)


def load_stats(
    *,
    tracker_id: int,
    start_day: date,
    end_day: date,
) -> List[DailyStatDTO]:
    with session_scope() as session:
        rows = (
            session.query(TrackerDailyStat)
            .filter(
                TrackerDailyStat.tracker_id == tracker_id,
                TrackerDailyStat.day >= start_day,
                TrackerDailyStat.day <= end_day,
            )
            .order_by(TrackerDailyStat.day.asc())
            .all()
        )
        return [
            DailyStatDTO(
                day=row.day,
                starts=row.starts,
                sales=row.sales,
                revenue_cents=row.revenue_cents,
            )
            for row in rows
        ]


def upsert_attribution(
    *,
    bot_id: int,
    user_telegram_id: int,
    tracker_id: int,
) -> None:
    with session_scope() as session:
        stmt = insert(TrackerAttribution).values(
            bot_id=bot_id,
            user_telegram_id=user_telegram_id,
            tracker_id=tracker_id,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                TrackerAttribution.bot_id,
                TrackerAttribution.user_telegram_id,
            ],
            set_={
                "tracker_id": tracker_id,
                "last_seen_at": func.now(),
            },
        )
        session.execute(stmt)


def get_attribution(
    *,
    bot_id: int,
    user_telegram_id: int,
) -> Optional[int]:
    with session_scope() as session:
        tracker_id = (
            session.query(TrackerAttribution.tracker_id)
            .filter(
                TrackerAttribution.bot_id == bot_id,
                TrackerAttribution.user_telegram_id == user_telegram_id,
            )
            .scalar()
        )
        return int(tracker_id) if tracker_id else None


def load_daily_summary_for_admin(
    *,
    admin_id: int,
    day: date,
    limit: int = 10,
) -> List[Tuple[int, int, int, int]]:
    with session_scope() as session:
        rows = (
            session.query(
                TrackerDailyStat.tracker_id,
                TrackerDailyStat.starts,
                TrackerDailyStat.sales,
                TrackerDailyStat.revenue_cents,
            )
            .join(TrackerLink, TrackerLink.id == TrackerDailyStat.tracker_id)
            .filter(
                TrackerLink.admin_id == admin_id,
                TrackerLink.is_active.is_(True),
                TrackerDailyStat.day == day,
            )
            .order_by(TrackerDailyStat.sales.desc(), TrackerDailyStat.starts.desc())
            .limit(limit)
            .all()
        )
        return [
            (
                int(row[0]),
                int(row[1]),
                int(row[2]),
                int(row[3]),
            )
            for row in rows
        ]


def load_daily_stats_bulk(
    *,
    tracker_ids: Sequence[int],
    day: date,
) -> List[Tuple[int, int, int, int]]:
    if not tracker_ids:
        return []
    with session_scope() as session:
        rows = (
            session.query(
                TrackerDailyStat.tracker_id,
                TrackerDailyStat.starts,
                TrackerDailyStat.sales,
                TrackerDailyStat.revenue_cents,
            )
            .filter(
                TrackerDailyStat.tracker_id.in_(tracker_ids),
                TrackerDailyStat.day == day,
            )
            .all()
        )
        return [
            (
                int(row[0]),
                int(row[1]),
                int(row[2]),
                int(row[3]),
            )
            for row in rows
        ]


__all__ = [
    "upsert_daily_stats",
    "load_stats",
    "upsert_attribution",
    "get_attribution",
    "load_daily_summary_for_admin",
    "load_daily_stats_bulk",
]
