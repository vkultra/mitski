"""High level statistics orchestrator used by bot handlers."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

from database.models import AIPhase, Bot
from database.repos import SessionLocal
from database.stats_costs import CostRepository
from database.stats_repos import StatsQueryRepository
from services.stats.roi import allocate_general_costs, compute_roi
from services.stats.schemas import (
    BotBreakdown,
    CostEntry,
    HourlyBucket,
    PhaseBreakdown,
    StatsSummary,
    StatsWindow,
    StatsWindowMode,
    Totals,
)

TZ = ZoneInfo("America/Sao_Paulo")


@dataclass(frozen=True)
class OwnerBot:
    id: int
    name: str


class StatsService:
    """Aggregates data required for the manager statistics UI."""

    def __init__(self, owner_id: int):
        self.owner_id = owner_id

    def build_window(
        self,
        *,
        day: Optional[date] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> StatsWindow:
        mode = StatsWindowMode.DAY if day else StatsWindowMode.RANGE
        return StatsWindow(mode=mode, day=day, start_date=start_date, end_date=end_date)

    def load_summary(self, window: StatsWindow) -> StatsSummary:
        bots = self._load_owner_bots()
        if not bots:
            empty_totals = Totals()
            return StatsSummary(window=window, totals=empty_totals)

        bot_ids = [bot.id for bot in bots]
        start_dt, end_dt = self._bounds(window.start_date, window.end_date)

        sales_data = StatsQueryRepository.sales_by_bot(bot_ids, start_dt, end_dt)
        starts_data = StatsQueryRepository.starts_by_bot(bot_ids, start_dt, end_dt)
        hourly_data = StatsQueryRepository.hourly_sales(
            bot_ids, start_dt, end_dt, TZ.key
        )
        phase_data = StatsQueryRepository.phase_entries(
            self.owner_id, bot_ids, start_dt, end_dt
        )
        cost_entries = CostRepository.list_costs(
            self.owner_id, window.start_date, window.end_date
        )

        per_bot = self._merge_bot_metrics(bots, sales_data, starts_data)
        totals = self._compute_totals(per_bot, cost_entries)

        top_bots = self._build_bot_breakdown(per_bot)
        hourly = [
            HourlyBucket(
                hour=row["hour"],
                sales_count=row["sales_count"],
                gross_cents=row["gross_cents"],
            )
            for row in hourly_data
        ]
        phases = self._build_phase_breakdown(phase_data)
        costs = [
            CostEntry(
                day=entry.day,
                scope=entry.scope,
                bot_id=entry.bot_id,
                amount_cents=entry.amount_cents,
                note=entry.note,
            )
            for entry in cost_entries
        ]

        return StatsSummary(
            window=window,
            totals=totals,
            top_bots=top_bots,
            hourly=hourly,
            phases=phases,
            costs=costs,
        )

    def _load_owner_bots(self) -> List[OwnerBot]:
        with SessionLocal() as session:
            query = session.query(Bot).filter(Bot.admin_id == self.owner_id)
            bots: List[OwnerBot] = []
            for bot in query:
                if bot.is_active is False:
                    continue
                name = bot.display_name or (
                    f"@{bot.username}" if bot.username else f"Bot #{bot.id}"
                )
                bots.append(OwnerBot(id=bot.id, name=name))
            return bots

    def daily_sales_series(
        self, days: int = 7, end_date: Optional[date] = None
    ) -> List[Tuple[date, int]]:
        if end_date is None:
            end_date = date.today()

        bots = self._load_owner_bots()
        if not bots:
            return []

        bot_ids = [bot.id for bot in bots]
        end_local = datetime.combine(end_date, time.min, tzinfo=TZ) + timedelta(days=1)
        start_local = datetime.combine(
            end_date - timedelta(days=days - 1), time.min, tzinfo=TZ
        )

        rows = StatsQueryRepository.sales_by_day(
            bot_ids, start_local, end_local, TZ.key
        )
        counts_by_day: Dict[date, int] = {}
        for row in rows:
            day_value = row.get("day")
            if isinstance(day_value, str):
                current_day = datetime.strptime(day_value, "%Y-%m-%d").date()
            elif isinstance(day_value, datetime):
                current_day = day_value.date()
            else:
                current_day = day_value  # type: ignore[assignment]
            counts_by_day[current_day] = row.get("sales_count", 0)

        series: List[Tuple[date, int]] = []
        for offset in range(days):
            current = end_date - timedelta(days=days - 1 - offset)
            series.append((current, counts_by_day.get(current, 0)))

        return series

    @staticmethod
    def _bounds(start_day: date, end_day: date) -> tuple[datetime, datetime]:
        start_local = datetime.combine(start_day, time.min, tzinfo=TZ)
        end_local = datetime.combine(end_day, time.min, tzinfo=TZ) + timedelta(days=1)
        return start_local.astimezone(timezone.utc).replace(
            tzinfo=None
        ), end_local.astimezone(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _merge_bot_metrics(
        bots: Iterable[OwnerBot],
        sales_rows: Iterable[Dict[str, int]],
        start_rows: Iterable[Dict[str, int]],
    ) -> Dict[int, Dict[str, int]]:
        result = {
            bot.id: {
                "name": bot.name,
                "sales_count": 0,
                "gross_cents": 0,
                "upsell_count": 0,
                "upsell_gross_cents": 0,
                "starts_count": 0,
            }
            for bot in bots
        }

        for row in sales_rows:
            if row["bot_id"] not in result:
                continue
            result[row["bot_id"]]["sales_count"] = row["sales_count"] or 0
            result[row["bot_id"]]["gross_cents"] = row["gross_cents"] or 0
            result[row["bot_id"]]["upsell_count"] = row["upsell_count"] or 0
            result[row["bot_id"]]["upsell_gross_cents"] = row["upsell_gross_cents"] or 0

        for row in start_rows:
            if row["bot_id"] in result:
                result[row["bot_id"]]["starts_count"] = row["start_count"] or 0

        return result

    def _compute_totals(
        self,
        per_bot: Dict[int, Dict[str, int]],
        cost_entries,
    ) -> Totals:
        sales_count = sum(bot["sales_count"] for bot in per_bot.values())
        gross_cents = sum(bot["gross_cents"] for bot in per_bot.values())
        upsell_count = sum(bot["upsell_count"] for bot in per_bot.values())
        upsell_gross = sum(bot["upsell_gross_cents"] for bot in per_bot.values())
        starts_count = sum(bot["starts_count"] for bot in per_bot.values())
        conversion = (sales_count / starts_count) if starts_count else 0.0

        per_bot_cost = defaultdict(int)
        general_cost_cents = 0
        for entry in cost_entries:
            if entry.scope == "bot" and entry.bot_id is not None:
                per_bot_cost[entry.bot_id] += entry.amount_cents
            else:
                general_cost_cents += entry.amount_cents

        general_alloc = allocate_general_costs(
            general_cost_cents,
            {bot_id: data["gross_cents"] for bot_id, data in per_bot.items()},
        )

        allocated_general = sum(general_alloc.values())
        general_leftover = max(general_cost_cents - allocated_general, 0)

        for bot_id, alloc in general_alloc.items():
            per_bot_cost[bot_id] += alloc

        for bot_id, data in per_bot.items():
            cost = per_bot_cost.get(bot_id, 0)
            data["cost_cents"] = cost
            data["conversion"] = (
                data["sales_count"] / data["starts_count"]
                if data["starts_count"]
                else 0.0
            )
            data["roi"] = compute_roi(data["gross_cents"], cost)

        total_cost = sum(per_bot_cost.values()) + general_leftover
        roi_overall = compute_roi(gross_cents, total_cost)

        return Totals(
            sales_count=sales_count,
            gross_cents=gross_cents,
            upsell_count=upsell_count,
            upsell_gross_cents=upsell_gross,
            starts_count=starts_count,
            conversion=conversion,
            total_cost_cents=total_cost,
            roi=roi_overall,
        )

    def _build_bot_breakdown(
        self, per_bot: Dict[int, Dict[str, int]]
    ) -> List[BotBreakdown]:
        breakdown = [
            BotBreakdown(
                bot_id=bot_id,
                name=data["name"],
                sales_count=data["sales_count"],
                gross_cents=data["gross_cents"],
                upsell_count=data["upsell_count"],
                upsell_gross_cents=data["upsell_gross_cents"],
                starts_count=data["starts_count"],
                conversion=data["conversion"],
                allocated_cost_cents=data.get("cost_cents", 0),
                roi=data.get("roi"),
            )
            for bot_id, data in per_bot.items()
        ]
        breakdown.sort(
            key=lambda item: (item.gross_cents, item.sales_count), reverse=True
        )
        return breakdown

    def _build_phase_breakdown(
        self,
        phase_data: Dict[tuple[int, int], Dict[str, int]],
    ) -> List[PhaseBreakdown]:
        if not phase_data:
            return []

        phase_ids = {phase_id for _, phase_id in phase_data.keys()}
        names = self._load_phase_names(phase_ids)

        items: List[PhaseBreakdown] = []
        for (bot_id, phase_id), data in phase_data.items():
            entered = data.get("entered", 0)
            advanced = data.get("advanced", 0)
            drop_rate = 0.0
            if entered > 0:
                drop_rate = max(entered - advanced, 0) / entered
            items.append(
                PhaseBreakdown(
                    bot_id=bot_id,
                    phase_id=phase_id,
                    phase_name=names.get(phase_id, f"Fase {phase_id}"),
                    entered=entered,
                    advanced=advanced,
                    drop_rate=drop_rate,
                )
            )

        items.sort(key=lambda item: (item.drop_rate, item.entered), reverse=True)
        return items

    @staticmethod
    def _load_phase_names(phase_ids: Iterable[int]) -> Dict[int, str]:
        if not phase_ids:
            return {}
        with SessionLocal() as session:
            query = session.query(AIPhase.id, AIPhase.phase_name).filter(
                AIPhase.id.in_(list(phase_ids))
            )
            return {phase_id: name for phase_id, name in query}


__all__ = ["StatsService"]
