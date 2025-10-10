"""Shared data structures for tracking services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Tuple


@dataclass
class TrackerView:
    id: int
    bot_id: int
    bot_username: str
    name: str
    code: str
    link: str
    starts: int
    sales: int
    revenue_cents: int


@dataclass
class TrackerDetail:
    tracker: TrackerView
    day: date
    timeline: List[Tuple[date, int, int, int]]


class TrackerNotFoundError(Exception):
    """Raised when tracker is missing or not owned by the admin."""


__all__ = ["TrackerView", "TrackerDetail", "TrackerNotFoundError"]
