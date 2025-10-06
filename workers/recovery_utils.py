"""Funções utilitárias para tasks de recuperação."""

from __future__ import annotations

import asyncio
from datetime import datetime

from database.recovery import RecoveryBlockRepository, RecoveryStepRepository
from database.recovery.delivery_repo import RecoveryDeliveryRepository
from database.repos import UserRepository


def fetch_active_steps(campaign_id: int):
    return [
        step
        for step in asyncio.run(RecoveryStepRepository.list_steps(campaign_id))
        if step.is_active
    ]


def step_has_blocks(step_id: int) -> bool:
    blocks = asyncio.run(RecoveryBlockRepository.list_blocks(step_id))
    return bool(blocks)


def get_or_create_user(bot_id: int, telegram_id: int):
    return asyncio.run(UserRepository.get_or_create_user(telegram_id, bot_id))


def ensure_scheduled_delivery(
    *,
    campaign_id: int,
    bot_id: int,
    user_db_id: int,
    step_id: int,
    episode_id: str,
    scheduled_for: datetime,
    campaign_version: int,
) -> None:
    asyncio.run(
        RecoveryDeliveryRepository.create_or_update(
            campaign_id=campaign_id,
            step_id=step_id,
            bot_id=bot_id,
            user_id=user_db_id,
            episode_id=episode_id,
            status="scheduled",
            scheduled_for=scheduled_for.replace(tzinfo=None),
            version_snapshot=campaign_version,
        )
    )
