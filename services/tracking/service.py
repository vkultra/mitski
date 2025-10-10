"""High level service for tracker management and reporting."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from core.telemetry import logger
from database.repos import PixTransactionRepository
from database.tracking_repos import (
    count_active_by_bot,
    count_trackers,
    create_tracker,
    get_tracker_by_id,
    list_trackers,
    set_bot_config,
    soft_delete_tracker,
)
from database.tracking_stats_repo import (
    get_attribution,
    load_daily_stats_bulk,
    load_daily_summary_for_admin,
    load_stats,
    upsert_attribution,
    upsert_daily_stats,
)
from services.tracking import cache, helpers
from services.tracking.types import TrackerDetail, TrackerNotFoundError, TrackerView


class TrackerService:
    def __init__(self, admin_id: int):
        self.admin_id = admin_id

    def create(self, *, bot_id: int, name: str) -> TrackerView:
        bot = helpers.ensure_bot(self.admin_id, bot_id)
        clean_name = helpers.sanitize_name(name)
        code = helpers.generate_unique_code(bot_id)
        dto = create_tracker(
            admin_id=self.admin_id, bot_id=bot_id, name=clean_name, code=code
        )
        cache.cache_tracker_code(bot_id, code, dto.id)
        active_count = count_active_by_bot(bot_id)
        cache.cache_bot_config(
            bot_id,
            ignore=helpers.load_ignore_flag(self.admin_id, bot_id),
            active_count=active_count,
        )
        link = helpers.build_deeplink(bot.username, code)
        logger.info(
            "Tracker created",
            extra={"admin_id": self.admin_id, "bot_id": bot_id, "tracker_id": dto.id},
        )
        return TrackerView(
            id=dto.id,
            bot_id=dto.bot_id,
            bot_username=bot.username,
            name=dto.name,
            code=dto.code,
            link=link,
            starts=0,
            sales=0,
            revenue_cents=0,
        )

    def delete(self, *, tracker_id: int) -> bool:
        tracker = get_tracker_by_id(tracker_id)
        if not tracker or tracker.admin_id != self.admin_id:
            return False
        deleted = soft_delete_tracker(tracker_id, admin_id=self.admin_id)
        if deleted:
            cache.drop_tracker_code(tracker.bot_id, tracker.code)
            active_count = count_active_by_bot(tracker.bot_id)
            cache.cache_bot_config(
                tracker.bot_id,
                ignore=helpers.load_ignore_flag(self.admin_id, tracker.bot_id),
                active_count=active_count,
            )
            logger.info(
                "Tracker deleted",
                extra={
                    "tracker_id": tracker_id,
                    "bot_id": tracker.bot_id,
                    "admin_id": self.admin_id,
                },
            )
        return deleted

    def list(
        self,
        *,
        bot_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 5,
        day: Optional[date] = None,
    ) -> Tuple[List[TrackerView], int]:
        day = day or date.today()
        offset = max(page - 1, 0) * per_page
        items = list_trackers(
            admin_id=self.admin_id,
            bot_id=bot_id,
            limit=per_page,
            offset=offset,
        )
        ids = [item.id for item in items]
        stats = {
            row[0]: row[1:] for row in load_daily_stats_bulk(tracker_ids=ids, day=day)
        }
        bot_usernames = helpers.load_bot_usernames(
            self.admin_id, {item.bot_id for item in items}
        )
        views = [
            TrackerView(
                id=item.id,
                bot_id=item.bot_id,
                bot_username=bot_usernames.get(item.bot_id, ""),
                name=item.name,
                code=item.code,
                link=helpers.build_deeplink(
                    bot_usernames.get(item.bot_id, ""), item.code
                ),
                starts=stats.get(item.id, (0, 0, 0))[0],
                sales=stats.get(item.id, (0, 0, 0))[1],
                revenue_cents=stats.get(item.id, (0, 0, 0))[2],
            )
            for item in items
        ]
        total = count_trackers(admin_id=self.admin_id, bot_id=bot_id)
        return views, total

    def detail(
        self, tracker_id: int, *, day: date, days_back: int = 6
    ) -> TrackerDetail:
        tracker = get_tracker_by_id(tracker_id)
        if not tracker or tracker.admin_id != self.admin_id:
            raise TrackerNotFoundError
        bot = helpers.ensure_bot(self.admin_id, tracker.bot_id)
        start_day = day - timedelta(days=days_back)
        stats = load_stats(tracker_id=tracker_id, start_day=start_day, end_day=day)
        timeline = []
        summary_map: Dict[date, Tuple[int, int, int]] = {
            entry.day: (entry.starts, entry.sales, entry.revenue_cents)
            for entry in stats
        }
        for i in range(days_back, -1, -1):
            target_day = day - timedelta(days=i)
            timeline.append(
                (
                    target_day,
                    summary_map.get(target_day, (0, 0, 0))[0],
                    summary_map.get(target_day, (0, 0, 0))[1],
                    summary_map.get(target_day, (0, 0, 0))[2],
                )
            )
        today_stats = summary_map.get(day, (0, 0, 0))
        view = TrackerView(
            id=tracker.id,
            bot_id=tracker.bot_id,
            bot_username=bot.username,
            name=tracker.name,
            code=tracker.code,
            link=helpers.build_deeplink(bot.username, tracker.code),
            starts=today_stats[0],
            sales=today_stats[1],
            revenue_cents=today_stats[2],
        )
        return TrackerDetail(tracker=view, day=day, timeline=timeline)

    def top_daily(self, *, day: date, limit: int = 3) -> List[TrackerView]:
        rows = load_daily_summary_for_admin(
            admin_id=self.admin_id, day=day, limit=limit
        )
        if not rows:
            return []
        tracker_map = {
            dto.id: dto
            for dto in list_trackers(admin_id=self.admin_id, include_inactive=False)
        }
        bot_usernames = helpers.load_bot_usernames(
            self.admin_id, {dto.bot_id for dto in tracker_map.values()}
        )
        views: List[TrackerView] = []
        for tracker_id, starts, sales, revenue in rows:
            dto = tracker_map.get(tracker_id)
            if not dto:
                continue
            views.append(
                TrackerView(
                    id=tracker_id,
                    bot_id=dto.bot_id,
                    bot_username=bot_usernames.get(dto.bot_id, ""),
                    name=dto.name,
                    code=dto.code,
                    link=helpers.build_deeplink(
                        bot_usernames.get(dto.bot_id, ""), dto.code
                    ),
                    starts=starts,
                    sales=sales,
                    revenue_cents=revenue,
                )
            )
        return views

    def get_toggle_state(self, bot_id: int) -> Tuple[bool, int]:
        flag = helpers.load_ignore_flag(self.admin_id, bot_id)
        active = count_active_by_bot(bot_id)
        cache.cache_bot_config(bot_id, ignore=flag, active_count=active)
        return flag, active

    def set_toggle_state(self, bot_id: int, *, enabled: bool) -> Tuple[bool, int]:
        helpers.ensure_bot(self.admin_id, bot_id)
        set_bot_config(bot_id, ignore_untracked=enabled)
        active = count_active_by_bot(bot_id)
        cache.cache_bot_config(bot_id, ignore=enabled, active_count=active)
        return enabled, active

    def record_start(
        self, *, bot_id: int, tracker_id: int, user_id: int, when: datetime
    ) -> None:
        day = when.date()
        cache.cache_attribution(bot_id, user_id, tracker_id)
        upsert_attribution(
            bot_id=bot_id, user_telegram_id=user_id, tracker_id=tracker_id
        )
        upsert_daily_stats(tracker_id=tracker_id, day=day, starts_delta=1)

    def record_sale(self, *, transaction_id: int) -> Optional[int]:
        transaction = PixTransactionRepository.get_by_id_sync(transaction_id)
        if not transaction:
            return None
        if getattr(transaction, "tracker_id", None):
            return transaction.tracker_id
        tracker_id = get_attribution(
            bot_id=transaction.bot_id,
            user_telegram_id=transaction.user_telegram_id,
        )
        if not tracker_id:
            return None
        event_day = (transaction.updated_at or datetime.utcnow()).date()
        upsert_daily_stats(
            tracker_id=tracker_id,
            day=event_day,
            sales_delta=1,
            revenue_delta=transaction.value_cents or 0,
        )
        PixTransactionRepository.set_tracker_sync(transaction_id, tracker_id)
        return tracker_id


__all__ = [
    "TrackerService",
    "TrackerView",
    "TrackerDetail",
    "TrackerNotFoundError",
]
