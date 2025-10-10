"""Cost-related helpers for statistics and ROI."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from database.repos import SessionLocal
from database.stats_models import DailyCostEntry


class CostRepository:
    """CRUD helpers for daily cost entries."""

    @staticmethod
    def add_cost(
        owner_id: int,
        scope: str,
        day: date,
        amount_cents: int,
        bot_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> DailyCostEntry:
        with SessionLocal() as session:
            entry = DailyCostEntry(
                owner_id=owner_id,
                scope=scope,
                bot_id=bot_id,
                day=day,
                amount_cents=amount_cents,
                note=note,
            )
            session.add(entry)
            session.commit()
            session.refresh(entry)
            return entry

    @staticmethod
    def list_costs(
        owner_id: int, start_day: date, end_day: date
    ) -> List[DailyCostEntry]:
        with SessionLocal() as session:
            query = (
                session.query(DailyCostEntry)
                .filter(
                    DailyCostEntry.owner_id == owner_id,
                    DailyCostEntry.day >= start_day,
                    DailyCostEntry.day <= end_day,
                )
                .order_by(DailyCostEntry.day.asc(), DailyCostEntry.created_at.asc())
            )
            return list(query)


__all__ = ["CostRepository"]
