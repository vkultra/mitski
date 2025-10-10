"""Pydantic schemas shared across statistics handlers."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class StatsWindowMode(str, Enum):
    DAY = "day"
    RANGE = "range"


class StatsWindow(BaseModel):
    mode: StatsWindowMode
    day: Optional[date] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @model_validator(mode="after")
    def validate_dates(cls, values: "StatsWindow") -> "StatsWindow":  # noqa: D401
        if values.mode == StatsWindowMode.DAY:
            if values.day is None:
                raise ValueError("day must be provided for day mode")
            values.start_date = values.day
            values.end_date = values.day
        else:
            if values.start_date is None or values.end_date is None:
                raise ValueError("start_date and end_date are required for range mode")
            if values.start_date > values.end_date:
                values.start_date, values.end_date = values.end_date, values.start_date
        return values

    @property
    def label(self) -> str:
        if self.mode == StatsWindowMode.DAY:
            return self.day.strftime("%d/%m/%Y")  # type: ignore[union-attr]
        return f"{self.start_date.strftime('%d/%m/%Y')} → {self.end_date.strftime('%d/%m/%Y')}"  # noqa: E501


class Totals(BaseModel):
    sales_count: int = 0
    gross_cents: int = 0
    upsell_count: int = 0
    upsell_gross_cents: int = 0
    starts_count: int = 0
    conversion: float = 0.0
    total_cost_cents: int = 0
    roi: Optional[float] = None


class BotBreakdown(BaseModel):
    bot_id: int
    name: str
    sales_count: int
    gross_cents: int
    upsell_count: int
    upsell_gross_cents: int
    starts_count: int
    conversion: float
    allocated_cost_cents: int
    roi: Optional[float]


class HourlyBucket(BaseModel):
    hour: int = Field(ge=0, le=23)
    sales_count: int
    gross_cents: int


class PhaseBreakdown(BaseModel):
    bot_id: int
    phase_id: int
    phase_name: str
    entered: int
    advanced: int
    drop_rate: float


class CostEntry(BaseModel):
    day: date
    scope: str  # general | bot
    bot_id: Optional[int] = None
    amount_cents: int
    note: Optional[str] = None


class StatsSummary(BaseModel):
    window: StatsWindow
    totals: Totals
    top_bots: List[BotBreakdown] = Field(default_factory=list)
    hourly: List[HourlyBucket] = Field(default_factory=list)
    phases: List[PhaseBreakdown] = Field(default_factory=list)
    costs: List[CostEntry] = Field(default_factory=list)


__all__ = [
    "StatsWindowMode",
    "StatsWindow",
    "Totals",
    "BotBreakdown",
    "HourlyBucket",
    "PhaseBreakdown",
    "CostEntry",
    "StatsSummary",
]
