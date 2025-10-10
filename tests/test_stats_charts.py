"""Tests for sales chart generation with caching."""

from datetime import date, timedelta

import pytest

pytest.importorskip("matplotlib")

from services.stats import charts
from services.stats.schemas import StatsWindow, StatsWindowMode


class DummyStatsService:
    """Minimal stub implementing the interface expected by charts."""

    def __init__(self, owner_id: int) -> None:
        self.owner_id = owner_id

    def daily_sales_series(self, days: int, end_date: date):
        base = end_date - timedelta(days=days - 1)
        return [(base + timedelta(days=idx), idx) for idx in range(days)]


def test_generate_sales_chart_cached(monkeypatch, fake_redis):
    monkeypatch.setattr(charts, "redis_client", fake_redis)

    service = DummyStatsService(owner_id=42)
    window = StatsWindow(mode=StatsWindowMode.DAY, day=date(2025, 10, 6))

    first = charts.generate_sales_chart(service, window)
    assert first is not None
    assert first.fresh is True
    assert first.path.is_file()

    second = charts.generate_sales_chart(service, window)
    assert second is not None
    assert second.fresh is False
    assert second.path == first.path

    forced = charts.generate_sales_chart(service, window, force=True)
    assert forced is not None
    assert forced.fresh is True
    assert forced.path != first.path
    assert not first.path.exists()

    # cleanup temp files generated during the test
    for candidate in (second.path, forced.path):
        try:
            candidate.unlink()
        except FileNotFoundError:
            continue
