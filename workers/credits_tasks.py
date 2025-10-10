"""Celery tasks for credit topups verification via PushinPay (<280 lines)."""

from __future__ import annotations

from datetime import datetime, timedelta

from core.redis_client import redis_client
from core.telemetry import logger
from core.token_costs import TextUsage, text_cost_brl_cents
from database.credits_models import CreditTopup  # type: ignore
from database.credits_repos import CreditLedgerRepository, CreditTopupRepository
from database.models import Bot, ConversationHistory
from database.repos import SessionLocal
from services.credits.metrics import (
    CREDITS_DEBIT_CENTS_TOTAL,
    CREDITS_TOPUP_CREATED_TOTAL,
    CREDITS_TOPUP_CREDITED_TOTAL,
)
from services.gateway.pushinpay_client import PushinPayClient
from workers.celery_app import celery_app

# (already imported above)


@celery_app.task
def start_topup_verification(topup_id: int):
    """Schedules 10 verification attempts (1 per minute)."""
    for i in range(10):
        verify_topup_task.apply_async(args=[topup_id], countdown=60 * (i + 1))
    try:
        CREDITS_TOPUP_CREATED_TOTAL.inc()
    except Exception:
        pass


@celery_app.task
def verify_topup_task(topup_id: int):
    topup = CreditTopupRepository.get_by_id_sync(topup_id)
    if not topup:
        logger.warning("Topup not found", extra={"topup_id": topup_id})
        return

    if topup.status == "paid" and topup.credited_at:
        return

    # Skip after 60 minutes window
    if (datetime.utcnow() - topup.created_at).total_seconds() > 3600:
        return

    from core.config import settings

    token = getattr(settings, "PUSHINRECARGA", None)
    if not token:
        logger.error("PUSHINRECARGA não configurado para verificar topup")
        return
    try:
        status_data = PushinPayClient.check_payment_status_sync(
            token, topup.transaction_id
        )
        current_status = status_data.get("status", "created")

        if current_status != topup.status:
            CreditTopupRepository.update_status_sync(topup.id, current_status)

        if current_status == "paid" and not topup.credited_at:
            # Credit wallet and mark
            CreditLedgerRepository.credit_sync(
                admin_id=topup.admin_id,
                amount_cents=int(topup.value_cents),
                category="topup",
                note=f"topup:{topup.transaction_id}",
            )
            CreditTopupRepository.mark_credited_sync(topup.id)
            logger.info(
                "Topup credited",
                extra={"admin_id": topup.admin_id, "value_cents": topup.value_cents},
            )
            try:
                CREDITS_TOPUP_CREDITED_TOTAL.inc()
            except Exception:
                pass
    except Exception as e:
        logger.error(
            "Topup verification error", extra={"topup_id": topup_id, "error": str(e)}
        )


@celery_app.task
def verify_all_pending_topups():
    """Finds recent created topups and schedules verification (sweeper)."""
    since = datetime.utcnow() - timedelta(minutes=60)
    with SessionLocal() as session:
        rows = (
            session.query(CreditTopup.id)
            .filter(CreditTopup.status == "created", CreditTopup.created_at >= since)
            .all()
        )
        for (tid,) in rows:
            verify_topup_task.delay(tid)


@celery_app.task(name="credits.debit_text_usage")
def debit_text_usage_task(bot_id: int, message_id: int) -> int:
    """Debits credits based on a saved assistant message (idempotent by note).

    Returns debited cents.
    """
    lock_key = f"credits:debit:msg:{message_id}"
    if not redis_client.set(lock_key, "1", nx=True, ex=3600):
        return 0
    try:
        with SessionLocal() as session:
            msg = session.query(ConversationHistory).filter_by(id=message_id).first()
            if not msg or getattr(msg, "role", None) != "assistant":
                return 0
            bot = session.query(Bot).filter_by(id=bot_id).first()
            if not bot:
                return 0
            admin_id = int(getattr(bot, "admin_id", 0) or 0)
            note = f"msg:{message_id}"
            if CreditLedgerRepository.exists_by_note_sync(admin_id, note):
                return 0
            usage = TextUsage(
                prompt_tokens=int(getattr(msg, "prompt_tokens", 0)),
                completion_tokens=int(getattr(msg, "completion_tokens", 0)),
                cached_tokens=int(getattr(msg, "cached_tokens", 0)),
                reasoning_tokens=int(getattr(msg, "reasoning_tokens", 0)),
            )
            cents = text_cost_brl_cents(usage)
            ok = CreditLedgerRepository.debit_if_enough_balance_sync(
                admin_id=admin_id,
                amount_cents=cents,
                category="text",
                bot_id=bot_id,
                user_telegram_id=int(getattr(msg, "user_telegram_id", 0) or 0),
                note=note,
            )
            if ok:
                try:
                    CREDITS_DEBIT_CENTS_TOTAL.labels(type="text").inc(int(cents))
                except Exception:
                    pass
                return int(cents)
            return 0
    finally:
        redis_client.delete(lock_key)
