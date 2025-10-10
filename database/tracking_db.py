"""Shared helpers for tracking persistence layers."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime

from database import repos as base_repos


@contextmanager
def session_scope():
    with base_repos.SessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


@dataclass
class TrackerDTO:
    id: int
    bot_id: int
    admin_id: int
    name: str
    code: str
    is_active: bool
    created_at: datetime


@dataclass
class DailyStatDTO:
    day: date
    starts: int
    sales: int
    revenue_cents: int


__all__ = ["session_scope", "TrackerDTO", "DailyStatDTO"]
