from datetime import datetime

import pytest

from database.models import PixTransaction, TrackerDailyStat
from services.tracking.runtime import extract_tracker_code, handle_start
from services.tracking.service import TrackerService


def test_extract_tracker_code():
    assert extract_tracker_code("/start abc123") == "abc123"
    assert extract_tracker_code("/start") is None
    assert extract_tracker_code("/help") is None


@pytest.mark.usefixtures("mock_redis_client")
def test_handle_start_tracks_and_ignores(
    db_session, sample_bot, fake_redis, monkeypatch
):
    monkeypatch.setattr("services.tracking.cache.redis_client", fake_redis)
    service = TrackerService(sample_bot.admin_id)
    tracker = service.create(bot_id=sample_bot.id, name="Campanha Stories")

    status, tracker_id = handle_start(
        bot_id=sample_bot.id,
        user_id=998,
        message_text=f"/start {tracker.code}",
        now=datetime.utcnow(),
    )
    assert status == "tracked"
    assert tracker_id == tracker.id

    status, _ = handle_start(
        bot_id=sample_bot.id,
        user_id=998,
        message_text="/start",
        now=datetime.utcnow(),
    )
    assert status == "pass"

    service.set_toggle_state(sample_bot.id, enabled=True)

    status, _ = handle_start(
        bot_id=sample_bot.id,
        user_id=998,
        message_text="/start",
        now=datetime.utcnow(),
    )
    assert status == "pass"

    status, _ = handle_start(
        bot_id=sample_bot.id,
        user_id=998,
        message_text="/start wrongcode",
        now=datetime.utcnow(),
    )
    assert status == "ignored"

    service.delete(tracker_id=tracker.id)

    status, _ = handle_start(
        bot_id=sample_bot.id,
        user_id=998,
        message_text="/start",
        now=datetime.utcnow(),
    )
    assert status == "pass"


@pytest.mark.usefixtures("mock_redis_client")
def test_record_sale_updates_stats(db_session, sample_bot, fake_redis, monkeypatch):
    monkeypatch.setattr("services.tracking.cache.redis_client", fake_redis)
    service = TrackerService(sample_bot.admin_id)
    tracker = service.create(bot_id=sample_bot.id, name="Campanha")
    service.record_start(
        bot_id=sample_bot.id,
        tracker_id=tracker.id,
        user_id=321,
        when=datetime.utcnow(),
    )

    transaction = PixTransaction(
        bot_id=sample_bot.id,
        user_telegram_id=321,
        chat_id=321,
        offer_id=None,
        upsell_id=None,
        transaction_id="txn-123",
        qr_code="code",
        value_cents=7500,
        status="paid",
    )
    db_session.add(transaction)
    db_session.commit()

    service.record_sale(transaction_id=transaction.id)

    stats = (
        db_session.query(TrackerDailyStat)
        .filter(TrackerDailyStat.tracker_id == tracker.id)
        .one()
    )
    assert stats.sales == 1
    assert stats.revenue_cents == 7500

    refreshed = db_session.query(PixTransaction).get(transaction.id)
    assert refreshed.tracker_id == tracker.id
