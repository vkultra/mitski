"""Integration tests for statistics service."""

from datetime import datetime

from database.models import AIPhase, Bot, PixTransaction
from database.stats_models import DailyCostEntry, PhaseTransitionEvent, StartEvent
from database.stats_repos import StatsQueryRepository
from services.stats.schemas import StatsWindowMode
from services.stats.service import StatsService


def _paid_transaction(
    bot_id: int, value_cents: int, updated_at: datetime, **extra
) -> PixTransaction:
    txn = PixTransaction(
        bot_id=bot_id,
        user_telegram_id=111,
        chat_id=111,
        transaction_id=f"txn-{bot_id}-{value_cents}-{updated_at.timestamp()}",
        qr_code="code",
        value_cents=value_cents,
        status="paid",
        created_at=updated_at,
        updated_at=updated_at,
        **extra,
    )
    return txn


def test_stats_summary(db_session, sample_bot) -> None:
    owner_id = sample_bot.admin_id

    # Segundo bot
    bot2 = sample_bot.__class__(
        admin_id=owner_id,
        username="bot_2",
        display_name="Bot 2",
        token=b"token",
        is_active=True,
    )
    db_session.add(bot2)
    db_session.commit()

    reference = datetime(2025, 10, 7, 15, 0, 0)

    db_session.add_all(
        [
            _paid_transaction(sample_bot.id, 10000, reference),
            _paid_transaction(sample_bot.id, 5000, reference, upsell_id=1),
            _paid_transaction(bot2.id, 8000, reference),
        ]
    )

    db_session.add_all(
        [
            StartEvent(
                owner_id=owner_id,
                bot_id=sample_bot.id,
                user_telegram_id=1,
                occurred_at=reference,
            ),
            StartEvent(
                owner_id=owner_id,
                bot_id=sample_bot.id,
                user_telegram_id=2,
                occurred_at=reference,
            ),
            StartEvent(
                owner_id=owner_id,
                bot_id=sample_bot.id,
                user_telegram_id=3,
                occurred_at=reference,
            ),
            StartEvent(
                owner_id=owner_id,
                bot_id=sample_bot.id,
                user_telegram_id=4,
                occurred_at=reference,
            ),
            StartEvent(
                owner_id=owner_id,
                bot_id=sample_bot.id,
                user_telegram_id=5,
                occurred_at=reference,
            ),
            StartEvent(
                owner_id=owner_id,
                bot_id=bot2.id,
                user_telegram_id=6,
                occurred_at=reference,
            ),
            StartEvent(
                owner_id=owner_id,
                bot_id=bot2.id,
                user_telegram_id=7,
                occurred_at=reference,
            ),
        ]
    )

    phase1 = AIPhase(
        bot_id=sample_bot.id, phase_name="Boas-vindas", phase_prompt="hi", order=1
    )
    phase2 = AIPhase(
        bot_id=sample_bot.id, phase_name="Oferta", phase_prompt="offer", order=2
    )
    db_session.add_all([phase1, phase2])
    db_session.commit()

    db_session.add_all(
        [
            PhaseTransitionEvent(
                owner_id=owner_id,
                bot_id=sample_bot.id,
                user_telegram_id=9,
                to_phase_id=phase1.id,
                occurred_at=reference,
            ),
            PhaseTransitionEvent(
                owner_id=owner_id,
                bot_id=sample_bot.id,
                user_telegram_id=9,
                from_phase_id=phase1.id,
                to_phase_id=phase2.id,
                occurred_at=reference,
            ),
        ]
    )

    db_session.add_all(
        [
            DailyCostEntry(
                owner_id=owner_id,
                scope="general",
                day=reference.date(),
                amount_cents=3000,
            ),
            DailyCostEntry(
                owner_id=owner_id,
                scope="bot",
                bot_id=sample_bot.id,
                day=reference.date(),
                amount_cents=2000,
            ),
            DailyCostEntry(
                owner_id=owner_id,
                scope="bot",
                bot_id=bot2.id,
                day=reference.date(),
                amount_cents=1000,
            ),
        ]
    )

    db_session.commit()

    assert db_session.query(PixTransaction).count() == 3
    assert db_session.query(StartEvent).count() == 7
    bots_in_db = db_session.query(Bot).filter(Bot.admin_id == owner_id).all()
    assert len(bots_in_db) == 2
    assert all(bot.is_active for bot in bots_in_db)

    service = StatsService(owner_id)
    bots_loaded = service._load_owner_bots()
    assert len(bots_loaded) == 2
    window = service.build_window(day=reference.date())
    start_dt, end_dt = service._bounds(window.start_date, window.end_date)  # type: ignore[arg-type]
    sales_rows = StatsQueryRepository.sales_by_bot(
        [sample_bot.id, bot2.id], start_dt, end_dt
    )
    assert sales_rows
    summary = service.load_summary(window)

    assert summary.window.mode == StatsWindowMode.DAY
    assert summary.totals.sales_count == 3
    assert summary.totals.gross_cents == 23000
    assert summary.totals.upsell_count == 1
    assert summary.totals.starts_count == 7
    assert summary.totals.total_cost_cents == 6000
    assert summary.totals.roi and summary.totals.roi > 2.0

    assert summary.top_bots[0].bot_id == sample_bot.id
    assert summary.top_bots[0].roi is not None
    assert summary.hourly
    assert summary.phases
