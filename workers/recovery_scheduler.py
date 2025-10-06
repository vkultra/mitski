"""Agendamento de verificações de inatividade para recuperação."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Optional

from core.recovery import (
    clear_episode,
    compute_next_occurrence,
    decode_schedule,
    generate_episode_id,
    get_inactivity_version,
    get_last_activity,
    remember_campaign_version,
    try_allocate_episode,
)
from core.telemetry import logger
from database.recovery import RecoveryCampaignRepository, RecoveryStepRepository
from database.repos import PixTransactionRepository
from workers.recovery_utils import (
    ensure_scheduled_delivery,
    fetch_active_steps,
    get_or_create_user,
    step_has_blocks,
)

from .celery_app import celery_app


def schedule_inactivity_check(
    bot_id: int, user_id: int, inactivity_version: int
) -> None:
    campaign = asyncio.run(RecoveryCampaignRepository.get_by_bot(bot_id))
    if not campaign or not campaign.is_active:
        return

    steps = fetch_active_steps(campaign.id)
    if not steps:
        return

    if campaign.skip_paid_users and PixTransactionRepository.user_has_paid_sync(
        bot_id, user_id
    ):
        logger.info(
            "Skipping recovery scheduling for paying user",
            extra={"bot_id": bot_id, "user_id": user_id},
        )
        return

    countdown = max(1, campaign.inactivity_threshold_seconds or 600)
    check_inactive.apply_async(
        args=[bot_id, user_id, inactivity_version],
        countdown=countdown,
        queue="recovery",
    )


@celery_app.task(bind=True, max_retries=3)
def check_inactive(self, bot_id: int, user_id: int, inactivity_version: int) -> None:
    current_version = get_inactivity_version(bot_id, user_id)
    if current_version != inactivity_version:
        logger.debug(
            "Recovery check skipped due to version mismatch",
            extra={"bot_id": bot_id, "user_id": user_id},
        )
        return

    campaign = asyncio.run(RecoveryCampaignRepository.get_by_bot(bot_id))
    if not campaign or not campaign.is_active:
        return

    steps = fetch_active_steps(campaign.id)
    if not steps:
        return

    if campaign.skip_paid_users and PixTransactionRepository.user_has_paid_sync(
        bot_id, user_id
    ):
        logger.info(
            "Skipping recovery due to paying user",
            extra={"bot_id": bot_id, "user_id": user_id},
        )
        return

    last_active = get_last_activity(bot_id, user_id)
    if last_active is None:
        last_active = int(time.time())

    threshold = campaign.inactivity_threshold_seconds or 600
    inactive_since = last_active + threshold
    now = time.time()

    if now + 1 < inactive_since:
        countdown = max(1, inactive_since - now)
        check_inactive.apply_async(
            args=[bot_id, user_id, inactivity_version],
            countdown=int(countdown),
            queue="recovery",
        )
        return

    first_step_id: Optional[int] = None
    for step in steps:
        if step_has_blocks(step.id):
            first_step_id = step.id
            break

    if not first_step_id:
        logger.debug(
            "Recovery skipped due to empty steps",
            extra={"bot_id": bot_id, "user_id": user_id},
        )
        return

    episode_id = generate_episode_id()
    if not try_allocate_episode(bot_id, user_id, episode_id):
        logger.debug(
            "Recovery episode already running",
            extra={"bot_id": bot_id, "user_id": user_id},
        )
        return

    remember_campaign_version(bot_id, user_id, campaign.version)

    step = asyncio.run(RecoveryStepRepository.get_step(first_step_id))
    if not step:
        clear_episode(bot_id, user_id)
        return

    definition = decode_schedule(step.schedule_type, step.schedule_value)
    base_time = datetime.fromtimestamp(inactive_since, timezone.utc)
    schedule_dt = compute_next_occurrence(
        definition,
        base_time=base_time,
        timezone_name=campaign.timezone,
    )
    delay_seconds = max(0, (schedule_dt - datetime.now(timezone.utc)).total_seconds())

    user_model = get_or_create_user(bot_id, user_id)
    ensure_scheduled_delivery(
        campaign_id=campaign.id,
        bot_id=bot_id,
        user_db_id=user_model.id,
        step_id=first_step_id,
        episode_id=episode_id,
        scheduled_for=schedule_dt,
        campaign_version=campaign.version,
    )

    from workers.recovery_sender import (  # import tardio para evitar ciclo
        send_recovery_step,
    )

    send_recovery_step.apply_async(
        args=[
            bot_id,
            user_id,
            first_step_id,
            campaign.id,
            episode_id,
            campaign.version,
            inactivity_version,
        ],
        countdown=delay_seconds,
        queue="recovery",
    )

    logger.info(
        "Recovery step scheduled",
        extra={
            "bot_id": bot_id,
            "user_id": user_id,
            "step_id": first_step_id,
            "episode_id": episode_id,
            "countdown": int(delay_seconds),
        },
    )
