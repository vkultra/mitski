"""Envio de mensagens de recuperação."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from core.recovery import (
    allocate_episode,
    clear_episode,
    compute_next_occurrence,
    current_episode,
    decode_schedule,
    get_inactivity_version,
)
from core.security import decrypt
from core.telemetry import logger
from database.recovery import (
    RecoveryBlockRepository,
    RecoveryCampaignRepository,
    RecoveryStepRepository,
)
from database.recovery.delivery_repo import RecoveryDeliveryRepository
from database.repos import BotRepository, PixTransactionRepository
from services.recovery.sender import RecoveryMessageSender
from workers.recovery_utils import (
    ensure_scheduled_delivery,
    fetch_active_steps,
    get_or_create_user,
    step_has_blocks,
)

from .celery_app import celery_app


def _next_step_with_blocks(campaign_id: int, current_order: int) -> Optional[int]:
    for step in fetch_active_steps(campaign_id):
        if step.order_index > current_order and step_has_blocks(step.id):
            return step.id
    return None


@celery_app.task(bind=True, max_retries=3)
def send_recovery_step(
    self,
    bot_id: int,
    user_id: int,
    step_id: int,
    campaign_id: int,
    episode_id: str,
    campaign_version: int,
    inactivity_version: int,
) -> None:
    current_version = get_inactivity_version(bot_id, user_id)
    if current_version != inactivity_version:
        logger.info(
            "Skipping recovery step due to user activity",
            extra={"bot_id": bot_id, "user_id": user_id},
        )
        return

    current_ep = current_episode(bot_id, user_id)
    if current_ep and current_ep != episode_id:
        logger.info(
            "Skipping recovery step due to episode mismatch",
            extra={"bot_id": bot_id, "user_id": user_id},
        )
        return

    campaign = asyncio.run(RecoveryCampaignRepository.get_by_id(campaign_id))
    if not campaign or not campaign.is_active:
        clear_episode(bot_id, user_id)
        return

    if campaign.version != campaign_version:
        logger.info(
            "Skipping recovery step due to campaign version change",
            extra={"bot_id": bot_id, "user_id": user_id},
        )
        clear_episode(bot_id, user_id)
        return

    if campaign.skip_paid_users and PixTransactionRepository.user_has_paid_sync(
        bot_id, user_id
    ):
        logger.info(
            "Skipping recovery step because user already paid",
            extra={"bot_id": bot_id, "user_id": user_id},
        )
        clear_episode(bot_id, user_id)
        return

    step = asyncio.run(RecoveryStepRepository.get_step(step_id))
    if not step or not step.is_active:
        return

    blocks = asyncio.run(RecoveryBlockRepository.list_blocks(step_id))
    if not blocks:
        return

    user_model = get_or_create_user(bot_id, user_id)
    bot = BotRepository.get_bot_by_id_sync(bot_id)
    if not bot or not bot.is_active:
        clear_episode(bot_id, user_id)
        return

    sender = RecoveryMessageSender(decrypt(bot.token), bot_id=bot_id)

    try:
        message_ids = asyncio.run(
            sender.send_blocks(
                blocks,
                chat_id=user_id,
                preview=False,
                bot_id=bot_id,
            )
        )
    except Exception as exc:  # pragma: no cover - reattempt
        raise self.retry(exc=exc, countdown=2**self.request.retries)

    sent_at = datetime.utcnow()
    payload = {
        "status": "sent",
        "sent_at": sent_at,
        "message_ids_json": json.dumps(message_ids or []),
    }

    delivery = asyncio.run(
        RecoveryDeliveryRepository.get_delivery(
            bot_id, user_model.id, step_id, episode_id
        )
    )
    if delivery:
        asyncio.run(
            RecoveryDeliveryRepository.update_status(
                delivery_id=delivery.id,
                **payload,
            )
        )
    else:
        asyncio.run(
            RecoveryDeliveryRepository.create_or_update(
                campaign_id=campaign_id,
                step_id=step_id,
                bot_id=bot_id,
                user_id=user_model.id,
                episode_id=episode_id,
                version_snapshot=campaign.version,
                **payload,
            )
        )

    next_step_id = _next_step_with_blocks(campaign_id, step.order_index)
    if not next_step_id:
        clear_episode(bot_id, user_id)
        return

    allocate_episode(bot_id, user_id, episode_id)

    next_step = asyncio.run(RecoveryStepRepository.get_step(next_step_id))
    definition = decode_schedule(next_step.schedule_type, next_step.schedule_value)
    base_time = datetime.now(timezone.utc)
    schedule_dt = compute_next_occurrence(
        definition,
        base_time=base_time,
        timezone_name=campaign.timezone,
    )
    delay_seconds = max(0, (schedule_dt - datetime.now(timezone.utc)).total_seconds())

    ensure_scheduled_delivery(
        campaign_id=campaign_id,
        bot_id=bot_id,
        user_db_id=user_model.id,
        step_id=next_step_id,
        episode_id=episode_id,
        scheduled_for=schedule_dt,
        campaign_version=campaign.version,
    )

    send_recovery_step.apply_async(
        args=[
            bot_id,
            user_id,
            next_step_id,
            campaign_id,
            episode_id,
            campaign.version,
            inactivity_version,
        ],
        countdown=delay_seconds,
        queue="recovery",
    )

    logger.info(
        "Recovery step sent",
        extra={
            "bot_id": bot_id,
            "user_id": user_id,
            "step_id": step_id,
            "episode_id": episode_id,
            "messages_sent": len(message_ids or []),
        },
    )

    logger.info(
        "Recovery next step scheduled",
        extra={
            "bot_id": bot_id,
            "user_id": user_id,
            "current_step": step_id,
            "next_step": next_step_id,
            "episode_id": episode_id,
            "countdown": int(delay_seconds),
        },
    )
