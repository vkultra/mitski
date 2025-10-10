"""Credit service: prechecks, debits and topups for IA and audio.

Design goals:
- Keep it compact (<280 lines), dependency‑free.
- Use ALLOWED_ADMIN_IDS for unlimited usage (no debits, no gating).
- Pre‑check (conservative) and post‑debit (accurate from usage).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.config import settings
from core.telemetry import logger
from core.token_costs import (
    TextUsage,
    apply_conservative_pad,
    estimate_completion_tokens,
    estimate_prompt_tokens_with_tokenize,
    text_cost_brl_cents,
    whisper_cost_brl_cents,
)
from database.credits_repos import (
    CreditLedgerRepository,
    CreditTopupRepository,
    CreditWalletRepository,
)
from database.repos import BotRepository, ConversationHistoryRepository
from services.gateway.pushinpay_client import PushinPayClient


def _is_unlimited_admin(admin_id: int) -> bool:
    """Checks unlimited credits strictly against ALLOWED_ADMIN_IDS string.

    Note: Unlike UI authorization (which treats empty as allow-all), unlimited
    credits must be explicit to avoid granting ilimitado por padrão.
    """
    try:
        raw = getattr(settings, "ALLOWED_ADMIN_IDS", "") or ""
        if not raw.strip():
            return False
        ids = {int(x) for x in raw.split(",") if x.strip()}
        return int(admin_id) in ids
    except Exception:
        return False


def is_unlimited_admin(admin_id: int) -> bool:
    """Public helper to check unlimited credits."""
    return _is_unlimited_admin(admin_id)


async def _avg_completion_tokens(
    bot_id: int, user_telegram_id: int, sample: int = 8
) -> int:
    msgs = await ConversationHistoryRepository.get_recent_messages(
        bot_id, user_telegram_id, limit=sample * 2
    )
    vals: List[int] = []
    for m in msgs:
        if getattr(m, "role", "") == "assistant":
            vals.append(
                int(getattr(m, "completion_tokens", 0))
                + int(getattr(m, "reasoning_tokens", 0))
            )
    if not vals:
        return 0
    return max(0, sum(vals) // len(vals))


class CreditService:
    """High‑level entry points for credit operations."""

    @staticmethod
    async def precheck_text(
        bot_id: int,
        user_telegram_id: int,
        messages: List[Dict[str, Any]],
        max_tokens: int,
        tokenizer_call,
    ) -> bool:
        """Returns True if the message should proceed (enough balance or unlimited)."""
        bot = await BotRepository.get_bot_by_id(bot_id)
        if not bot:
            return False
        admin_id = int(getattr(bot, "admin_id", 0) or 0)
        if _is_unlimited_admin(admin_id):
            return True

        # Build a concatenated prompt text for tokenization (system+history+user)
        parts: List[str] = []
        for msg in messages or []:
            content = msg.get("content")
            if isinstance(content, list):
                for item in content:
                    if item.get("type") == "text":
                        parts.append(item.get("text") or "")
            else:
                parts.append(str(content or ""))
        prompt_text = "\n".join(parts)

        prompt_tokens = await estimate_prompt_tokens_with_tokenize(
            prompt_text, tokenizer_call
        )
        avg_out = await _avg_completion_tokens(bot_id, user_telegram_id)
        completion_tokens = estimate_completion_tokens(avg_out, max_tokens)

        est = TextUsage(
            prompt_tokens=apply_conservative_pad(prompt_tokens),
            completion_tokens=apply_conservative_pad(completion_tokens),
            cached_tokens=0,
            reasoning_tokens=0,
        )
        est_cost = text_cost_brl_cents(est)

        balance = CreditWalletRepository.get_balance_cents_sync(admin_id)
        allowed: bool = bool(balance >= est_cost)
        logger.info(
            "Credit precheck",
            extra={
                "bot_id": bot_id,
                "admin_id": admin_id,
                "balance_cents": balance,
                "est_cost_cents": est_cost,
                "prompt_tokens": prompt_tokens,
                "completion_est": completion_tokens,
            },
        )
        return allowed

    @staticmethod
    def debit_text_usage(bot_id: int, usage: Dict[str, Any]) -> Optional[int]:
        """Debits wallet using accurate usage after a successful IA call.

        Returns debited cents or None if unlimited/no debit.
        """
        bot = BotRepository.get_bot_by_id_sync(bot_id)
        if not bot:
            return None
        admin_id = int(getattr(bot, "admin_id", 0) or 0)
        if _is_unlimited_admin(admin_id):
            return None

        u = TextUsage(
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            cached_tokens=int(usage.get("cached_tokens", 0)),
            reasoning_tokens=int(usage.get("reasoning_tokens", 0)),
        )
        cents = text_cost_brl_cents(u)
        ok = CreditLedgerRepository.debit_if_enough_balance_sync(
            admin_id=admin_id,
            amount_cents=cents,
            category="text",
            bot_id=bot_id,
        )
        if not ok:
            logger.warning(
                "Debit failed due to insufficient funds (post-usage)",
                extra={"admin_id": admin_id, "bot_id": bot_id, "cents": cents},
            )
            return 0
        return int(cents)

    @staticmethod
    def precheck_audio(bot_id: int, duration_seconds: Optional[int]) -> bool:
        bot = BotRepository.get_bot_by_id_sync(bot_id)
        if not bot:
            return False
        admin_id = int(getattr(bot, "admin_id", 0) or 0)
        if _is_unlimited_admin(admin_id):
            return True
        minutes = max(0.0, float(duration_seconds or 0) / 60.0)
        cost_cents = whisper_cost_brl_cents(minutes)
        balance = CreditWalletRepository.get_balance_cents_sync(admin_id)
        allowed: bool = bool(balance >= cost_cents)
        logger.info(
            "Credit precheck audio",
            extra={
                "bot_id": bot_id,
                "admin_id": admin_id,
                "balance_cents": balance,
                "est_cost_cents": cost_cents,
                "minutes": minutes,
            },
        )
        return allowed

    @staticmethod
    def debit_audio(bot_id: int, duration_seconds: Optional[int]) -> Optional[int]:
        bot = BotRepository.get_bot_by_id_sync(bot_id)
        if not bot:
            return None
        admin_id = int(getattr(bot, "admin_id", 0) or 0)
        if _is_unlimited_admin(admin_id):
            return None
        minutes = max(0.0, float(duration_seconds or 0) / 60.0)
        cents = whisper_cost_brl_cents(minutes)
        ok = CreditLedgerRepository.debit_if_enough_balance_sync(
            admin_id=admin_id, amount_cents=cents, category="whisper", bot_id=bot_id
        )
        if not ok:
            logger.warning(
                "Debit failed (audio)",
                extra={"admin_id": admin_id, "bot_id": bot_id, "cents": cents},
            )
            return 0
        return int(cents)

    @staticmethod
    def create_topup(admin_id: int, value_cents: int, bot_id: Optional[int] = None):
        """Creates a PIX charge via PushinPay and stores the topup record."""
        # Prefer dedicated token from env for topups; fallback to admin gateway
        token = getattr(settings, "PUSHINRECARGA", None)
        if not token:
            raise ValueError(
                "PUSHINRECARGA não configurado. Configure o token dedicado de recarga no .env"
            )
        # Create PIX (síncrono para evitar conflitos de event loop)
        data = PushinPayClient.create_pix_sync(token, int(value_cents))
        tx_id = str(data.get("id"))
        qr_code = data.get("qr_code") or data.get("pix_code") or ""
        qr_b64 = data.get("qr_code_base64")
        topup = CreditTopupRepository.create_sync(
            admin_id=admin_id,
            value_cents=int(value_cents),
            transaction_id=tx_id,
            qr_code=qr_code,
            qr_code_base64=qr_b64,
            bot_id=bot_id,
        )
        return topup


__all__ = ["CreditService"]
