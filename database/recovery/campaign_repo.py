"""Repos para campanhas, passos e blocos de recuperação."""

from __future__ import annotations

from typing import List, Optional, Sequence

from sqlalchemy import asc, func

from core.telemetry import logger
from database.models import RecoveryBlock, RecoveryCampaign, RecoveryStep
from database.repos import SessionLocal


class RecoveryCampaignRepository:
    """CRUD básico da campanha (1 por bot)."""

    @staticmethod
    async def get_or_create(
        bot_id: int, *, created_by: Optional[int] = None
    ) -> RecoveryCampaign:
        with SessionLocal() as session:
            campaign = (
                session.query(RecoveryCampaign)
                .filter(RecoveryCampaign.bot_id == bot_id)
                .first()
            )
            if campaign:
                return campaign

            campaign = RecoveryCampaign(
                bot_id=bot_id,
                title="Recuperação",
                timezone="UTC",
                inactivity_threshold_seconds=600,
                is_active=True,
                version=1,
                skip_paid_users=True,
                created_by=created_by,
            )
            session.add(campaign)
            session.commit()
            session.refresh(campaign)
            logger.info(
                "Recovery campaign created",
                extra={"bot_id": bot_id, "campaign_id": campaign.id},
            )
            return campaign

    @staticmethod
    async def update_campaign(campaign_id: int, **fields) -> Optional[RecoveryCampaign]:
        if not fields:
            return await RecoveryCampaignRepository.get_by_id(campaign_id)
        with SessionLocal() as session:
            campaign = (
                session.query(RecoveryCampaign)
                .filter(RecoveryCampaign.id == campaign_id)
                .with_for_update()
                .first()
            )
            if not campaign:
                return None
            for key, value in fields.items():
                if hasattr(campaign, key):
                    setattr(campaign, key, value)
            session.commit()
            session.refresh(campaign)
            return campaign

    @staticmethod
    async def increment_version(campaign_id: int) -> None:
        with SessionLocal() as session:
            session.query(RecoveryCampaign).filter(
                RecoveryCampaign.id == campaign_id
            ).update({RecoveryCampaign.version: RecoveryCampaign.version + 1})
            session.commit()

    @staticmethod
    async def get_by_id(campaign_id: int) -> Optional[RecoveryCampaign]:
        with SessionLocal() as session:
            return (
                session.query(RecoveryCampaign)
                .filter(RecoveryCampaign.id == campaign_id)
                .first()
            )

    @staticmethod
    async def get_by_bot(bot_id: int) -> Optional[RecoveryCampaign]:
        with SessionLocal() as session:
            return (
                session.query(RecoveryCampaign)
                .filter(RecoveryCampaign.bot_id == bot_id)
                .first()
            )


class RecoveryStepRepository:
    """Manutenção dos passos sequenciais."""

    @staticmethod
    async def list_steps(campaign_id: int) -> List[RecoveryStep]:
        with SessionLocal() as session:
            return (
                session.query(RecoveryStep)
                .filter(RecoveryStep.campaign_id == campaign_id)
                .order_by(asc(RecoveryStep.order_index))
                .all()
            )

    @staticmethod
    async def get_step(step_id: int) -> Optional[RecoveryStep]:
        with SessionLocal() as session:
            return (
                session.query(RecoveryStep).filter(RecoveryStep.id == step_id).first()
            )

    @staticmethod
    async def create_step(
        campaign_id: int,
        schedule_type: str,
        schedule_value: str,
        *,
        is_active: bool = True,
    ) -> RecoveryStep:
        with SessionLocal() as session:
            next_order = (
                session.query(func.coalesce(func.max(RecoveryStep.order_index), 0))
                .filter(RecoveryStep.campaign_id == campaign_id)
                .scalar()
            )
            step = RecoveryStep(
                campaign_id=campaign_id,
                order_index=int(next_order) + 1,
                schedule_type=schedule_type,
                schedule_value=schedule_value,
                is_active=is_active,
            )
            session.add(step)
            session.commit()
            session.refresh(step)
            return step

    @staticmethod
    async def update_schedule(
        step_id: int, schedule_type: str, schedule_value: str
    ) -> Optional[RecoveryStep]:
        with SessionLocal() as session:
            step = (
                session.query(RecoveryStep)
                .filter(RecoveryStep.id == step_id)
                .with_for_update()
                .first()
            )
            if not step:
                return None
            step.schedule_type = schedule_type
            step.schedule_value = schedule_value
            session.commit()
            session.refresh(step)
            return step

    @staticmethod
    async def update_activation(step_id: int, is_active: bool) -> None:
        with SessionLocal() as session:
            session.query(RecoveryStep).filter(RecoveryStep.id == step_id).update(
                {RecoveryStep.is_active: is_active}
            )
            session.commit()

    @staticmethod
    async def delete_step(step_id: int) -> Optional[int]:
        with SessionLocal() as session:
            step = (
                session.query(RecoveryStep).filter(RecoveryStep.id == step_id).first()
            )
            if not step:
                return None
            campaign_id = step.campaign_id
            session.delete(step)
            session.flush()
            RecoveryStepRepository._reorder_steps(session, campaign_id)
            session.commit()
            return campaign_id

    @staticmethod
    def _reorder_steps(session, campaign_id: int) -> None:
        steps: Sequence[RecoveryStep] = (
            session.query(RecoveryStep)
            .filter(RecoveryStep.campaign_id == campaign_id)
            .order_by(asc(RecoveryStep.order_index))
            .all()
        )
        for idx, step in enumerate(steps, start=1):
            if step.order_index != idx:
                step.order_index = idx


class RecoveryBlockRepository:
    """Operações com blocos de mensagem."""

    @staticmethod
    async def list_blocks(step_id: int) -> List[RecoveryBlock]:
        with SessionLocal() as session:
            return (
                session.query(RecoveryBlock)
                .filter(RecoveryBlock.step_id == step_id)
                .order_by(asc(RecoveryBlock.order_index))
                .all()
            )

    @staticmethod
    async def get_block(block_id: int) -> Optional[RecoveryBlock]:
        with SessionLocal() as session:
            return (
                session.query(RecoveryBlock)
                .filter(RecoveryBlock.id == block_id)
                .first()
            )

    @staticmethod
    async def create_block(step_id: int) -> RecoveryBlock:
        with SessionLocal() as session:
            next_order = (
                session.query(func.coalesce(func.max(RecoveryBlock.order_index), 0))
                .filter(RecoveryBlock.step_id == step_id)
                .scalar()
            )
            block = RecoveryBlock(
                step_id=step_id,
                order_index=int(next_order) + 1,
                text="",
                parse_mode="Markdown",
                delay_seconds=0,
                auto_delete_seconds=0,
            )
            session.add(block)
            session.commit()
            session.refresh(block)
            return block

    @staticmethod
    async def update_block(block_id: int, **fields) -> Optional[RecoveryBlock]:
        if not fields:
            return await RecoveryBlockRepository.get_block(block_id)
        with SessionLocal() as session:
            block = (
                session.query(RecoveryBlock)
                .filter(RecoveryBlock.id == block_id)
                .with_for_update()
                .first()
            )
            if not block:
                return None
            for key, value in fields.items():
                if hasattr(block, key):
                    setattr(block, key, value)
            session.commit()
            session.refresh(block)
            return block

    @staticmethod
    async def delete_block(block_id: int) -> Optional[int]:
        with SessionLocal() as session:
            block = (
                session.query(RecoveryBlock)
                .filter(RecoveryBlock.id == block_id)
                .first()
            )
            if not block:
                return None
            step_id = block.step_id
            session.delete(block)
            session.flush()
            RecoveryBlockRepository._reorder_blocks(session, step_id)
            session.commit()
            return step_id

    @staticmethod
    def _reorder_blocks(session, step_id: int) -> None:
        blocks: Sequence[RecoveryBlock] = (
            session.query(RecoveryBlock)
            .filter(RecoveryBlock.step_id == step_id)
            .order_by(asc(RecoveryBlock.order_index))
            .all()
        )
        for idx, block in enumerate(blocks, start=1):
            if block.order_index != idx:
                block.order_index = idx
