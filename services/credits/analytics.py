"""Helper functions for credit summaries and metrics."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional, Tuple

from sqlalchemy import func

from database.credits_models import CreditLedger
from database.models import Bot, ConversationHistory
from database.repos import SessionLocal


def sum_ledger_amount(
    admin_id: int,
    entry_type: str,
    start_dt: datetime,
    end_dt: datetime,
    categories: Optional[Iterable[str]] = None,
) -> int:
    """Soma centavos de entradas do ledger para um período."""
    with SessionLocal() as session:
        query = (
            session.query(func.coalesce(func.sum(CreditLedger.amount_cents), 0))
            .filter(CreditLedger.admin_id == admin_id)
            .filter(CreditLedger.entry_type == entry_type)
            .filter(CreditLedger.created_at >= start_dt)
            .filter(CreditLedger.created_at < end_dt)
        )
        if categories:
            query = query.filter(CreditLedger.category.in_(tuple(categories)))
        return int(query.scalar() or 0)


def message_token_stats(
    admin_id: int, start_dt: datetime, end_dt: datetime
) -> Tuple[int, int]:
    """Retorna (mensagens, tokens) de respostas da IA em um período."""
    with SessionLocal() as session:
        messages_expr = func.count(ConversationHistory.id)
        prompt_sum = func.coalesce(func.sum(ConversationHistory.prompt_tokens), 0)
        cached_sum = func.coalesce(func.sum(ConversationHistory.cached_tokens), 0)
        completion_sum = func.coalesce(
            func.sum(ConversationHistory.completion_tokens), 0
        )
        reasoning_sum = func.coalesce(func.sum(ConversationHistory.reasoning_tokens), 0)

        result = (
            session.query(
                messages_expr, prompt_sum, cached_sum, completion_sum, reasoning_sum
            )
            .join(Bot, ConversationHistory.bot_id == Bot.id)
            .filter(Bot.admin_id == admin_id)
            .filter(ConversationHistory.role == "assistant")
            .filter(ConversationHistory.created_at >= start_dt)
            .filter(ConversationHistory.created_at < end_dt)
            .one()
        )

        messages = int(result[0] or 0)
        tokens = int(result[1] + result[2] + result[3] + result[4])
        return messages, tokens


__all__ = ["sum_ledger_amount", "message_token_stats"]
