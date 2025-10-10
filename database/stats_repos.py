"""Low-level helpers for statistics related persistence and aggregation."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

from sqlalchemy import INT, case, cast, func

from core.telemetry import logger

from .models import PixTransaction
from .repos import SessionLocal
from .stats_models import PhaseTransitionEvent, StartEvent


def _ensure_naive(dt: datetime) -> datetime:
    """Force datetime to be naive UTC for Postgres comparisons."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


class StatsEventRepository:
    """Persists telemetry events without blocking main flows."""

    @staticmethod
    def record_start(
        owner_id: int, bot_id: int, user_telegram_id: int, occurred_at: datetime
    ) -> None:
        try:
            with SessionLocal() as session:
                event = StartEvent(
                    owner_id=owner_id,
                    bot_id=bot_id,
                    user_telegram_id=user_telegram_id,
                    occurred_at=_ensure_naive(occurred_at or datetime.utcnow()),
                )
                session.add(event)
                session.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to save start event",
                extra={
                    "owner_id": owner_id,
                    "bot_id": bot_id,
                    "user_id": user_telegram_id,
                    "error": str(exc),
                },
            )

    @staticmethod
    def record_phase_transition(
        owner_id: int,
        bot_id: int,
        user_telegram_id: int,
        from_phase_id: Optional[int],
        to_phase_id: int,
        occurred_at: datetime,
    ) -> None:
        try:
            with SessionLocal() as session:
                event = PhaseTransitionEvent(
                    owner_id=owner_id,
                    bot_id=bot_id,
                    user_telegram_id=user_telegram_id,
                    from_phase_id=from_phase_id,
                    to_phase_id=to_phase_id,
                    occurred_at=_ensure_naive(occurred_at or datetime.utcnow()),
                )
                session.add(event)
                session.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to save phase transition",
                extra={
                    "owner_id": owner_id,
                    "bot_id": bot_id,
                    "from_phase_id": from_phase_id,
                    "to_phase_id": to_phase_id,
                    "error": str(exc),
                },
            )


class StatsQueryRepository:
    """Aggregated SQL helpers used by the statistics service."""

    @staticmethod
    def sales_by_bot(
        bot_ids: Iterable[int],
        start: datetime,
        end: datetime,
    ) -> List[Dict[str, int]]:
        ids = list(bot_ids)
        if not ids:
            return []

        with SessionLocal() as session:
            query = (
                session.query(
                    PixTransaction.bot_id.label("bot_id"),
                    func.count(PixTransaction.id).label("sales_count"),
                    func.sum(PixTransaction.value_cents).label("gross_cents"),
                    func.sum(
                        case((PixTransaction.upsell_id.isnot(None), 1), else_=0)
                    ).label("upsell_count"),
                    func.sum(
                        case(
                            (
                                PixTransaction.upsell_id.isnot(None),
                                PixTransaction.value_cents,
                            ),
                            else_=0,
                        )
                    ).label("upsell_gross_cents"),
                )
                .filter(
                    PixTransaction.status == "paid",
                    PixTransaction.bot_id.in_(ids),
                    PixTransaction.updated_at >= _ensure_naive(start),
                    PixTransaction.updated_at < _ensure_naive(end),
                )
                .group_by(PixTransaction.bot_id)
            )
            return [dict(row._mapping) for row in query]  # noqa: SLF001

    @staticmethod
    def starts_by_bot(
        bot_ids: Iterable[int],
        start: datetime,
        end: datetime,
    ) -> List[Dict[str, int]]:
        ids = list(bot_ids)
        if not ids:
            return []
        with SessionLocal() as session:
            query = (
                session.query(
                    StartEvent.bot_id.label("bot_id"),
                    func.count(StartEvent.id).label("start_count"),
                )
                .filter(
                    StartEvent.bot_id.in_(ids),
                    StartEvent.occurred_at >= _ensure_naive(start),
                    StartEvent.occurred_at < _ensure_naive(end),
                )
                .group_by(StartEvent.bot_id)
            )
            return [dict(row._mapping) for row in query]  # noqa: SLF001

    @staticmethod
    def hourly_sales(
        bot_ids: Iterable[int],
        start: datetime,
        end: datetime,
        timezone_name: str,
    ) -> List[Dict[str, int]]:
        ids = list(bot_ids)
        if not ids:
            return []

        with SessionLocal() as session:
            if session.bind and session.bind.dialect.name == "sqlite":
                hour_expr = cast(func.strftime("%H", PixTransaction.updated_at), INT)
            else:
                tz_expr = func.timezone(timezone_name, PixTransaction.updated_at)
                hour_expr = cast(func.extract("hour", tz_expr), INT)
            query = (
                session.query(
                    hour_expr.label("hour"),
                    func.count(PixTransaction.id).label("sales_count"),
                    func.sum(PixTransaction.value_cents).label("gross_cents"),
                )
                .filter(
                    PixTransaction.status == "paid",
                    PixTransaction.bot_id.in_(ids),
                    PixTransaction.updated_at >= _ensure_naive(start),
                    PixTransaction.updated_at < _ensure_naive(end),
                )
                .group_by(hour_expr)
                .order_by(hour_expr)
            )
            return [dict(row._mapping) for row in query]  # noqa: SLF001

    @staticmethod
    def sales_by_day(
        bot_ids: Iterable[int],
        start: datetime,
        end: datetime,
        timezone_name: str,
    ) -> List[Dict[str, object]]:
        ids = list(bot_ids)
        if not ids:
            return []

        with SessionLocal() as session:
            if session.bind and session.bind.dialect.name == "sqlite":
                day_expr = func.strftime("%Y-%m-%d", PixTransaction.updated_at)
            else:
                tz_expr = func.timezone(timezone_name, PixTransaction.updated_at)
                day_expr = func.to_char(tz_expr, "YYYY-MM-DD")

            query = (
                session.query(
                    day_expr.label("day"),
                    func.count(PixTransaction.id).label("sales_count"),
                    func.sum(PixTransaction.value_cents).label("gross_cents"),
                )
                .filter(
                    PixTransaction.status == "paid",
                    PixTransaction.bot_id.in_(ids),
                    PixTransaction.updated_at >= _ensure_naive(start),
                    PixTransaction.updated_at < _ensure_naive(end),
                )
                .group_by(day_expr)
                .order_by(day_expr)
            )
            return [dict(row._mapping) for row in query]  # noqa: SLF001

    @staticmethod
    def phase_entries(
        owner_id: int,
        bot_ids: Iterable[int],
        start: datetime,
        end: datetime,
    ) -> Dict[tuple[int, int], Dict[str, int]]:
        ids = list(bot_ids)
        if not ids:
            return {}

        with SessionLocal() as session:
            entered_query = (
                session.query(
                    PhaseTransitionEvent.bot_id.label("bot_id"),
                    PhaseTransitionEvent.to_phase_id.label("phase_id"),
                    func.count(PhaseTransitionEvent.id).label("entered"),
                )
                .filter(
                    PhaseTransitionEvent.owner_id == owner_id,
                    PhaseTransitionEvent.bot_id.in_(ids),
                    PhaseTransitionEvent.occurred_at >= _ensure_naive(start),
                    PhaseTransitionEvent.occurred_at < _ensure_naive(end),
                )
                .group_by(PhaseTransitionEvent.bot_id, PhaseTransitionEvent.to_phase_id)
            )
            advanced_query = (
                session.query(
                    PhaseTransitionEvent.bot_id.label("bot_id"),
                    PhaseTransitionEvent.from_phase_id.label("phase_id"),
                    func.count(PhaseTransitionEvent.id).label("advanced"),
                )
                .filter(
                    PhaseTransitionEvent.owner_id == owner_id,
                    PhaseTransitionEvent.bot_id.in_(ids),
                    PhaseTransitionEvent.from_phase_id.isnot(None),
                    PhaseTransitionEvent.occurred_at >= _ensure_naive(start),
                    PhaseTransitionEvent.occurred_at < _ensure_naive(end),
                )
                .group_by(
                    PhaseTransitionEvent.bot_id, PhaseTransitionEvent.from_phase_id
                )
            )

            result = defaultdict(lambda: {"entered": 0, "advanced": 0})
            for row in entered_query:
                result[(row.bot_id, row.phase_id)]["entered"] = row.entered
            for row in advanced_query:
                result[(row.bot_id, row.phase_id)]["advanced"] = row.advanced
            return dict(result)


__all__ = ["StatsEventRepository", "StatsQueryRepository"]
