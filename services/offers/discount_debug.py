"""Utilitários para simular descontos via comandos de debug."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from core.telemetry import logger
from database.repos import OfferRepository

from .discount_service import DiscountService


@dataclass
class DiscountDebugCommandResult:
    """Resultado do processamento do comando de debug de desconto."""

    handled: bool
    reply: Optional[str] = None


async def try_handle_discount_debug_command(
    bot_id: int,
    chat_id: int,
    user_id: int,
    text: str,
    bot_token: str,
) -> DiscountDebugCommandResult:
    """Simula a detecção de desconto quando o admin digita `/{termo}{valor}`.

    Retorna ``handled=True`` quando o comando foi reconhecido como teste de desconto,
    seja ele bem-sucedido ou não. Em caso de falha envia feedback para o usuário.
    """

    if not text or not text.startswith("/") or len(text) <= 1:
        return DiscountDebugCommandResult(handled=False)

    parts = text.strip().split()
    if not parts:
        return DiscountDebugCommandResult(handled=False)

    command_raw = parts[0][1:]
    if not command_raw:
        return DiscountDebugCommandResult(handled=False)

    command_base = command_raw.split("@", 1)[0]
    command_lower = command_base.lower()
    args_suffix = " ".join(parts[1:]).strip()

    offers = await OfferRepository.get_offers_by_bot(bot_id, active_only=True)
    for offer in offers:
        trigger = (offer.discount_trigger or "").strip()
        if not trigger:
            continue

        trigger_lower = trigger.lower()
        if not command_lower.startswith(trigger_lower):
            continue

        inline_suffix = command_base[len(trigger) :]
        combined_tail = inline_suffix.strip()
        if args_suffix:
            combined_tail = (
                f"{combined_tail} {args_suffix}".strip()
                if combined_tail
                else args_suffix
            )

        if not combined_tail:
            guidance = (
                f"⚠️ Informe um valor após `{trigger}`. " f"Exemplo: `/{trigger}15`."
            )
            return DiscountDebugCommandResult(handled=True, reply=guidance)

        tail = _build_tail(inline_suffix, args_suffix)
        synthetic_message = _compose_message(trigger, tail)

        logger.info(
            "Triggering discount via debug command",
            extra={
                "bot_id": bot_id,
                "user_id": user_id,
                "offer_id": offer.id,
                "command": text,
                "synthetic_message": synthetic_message,
            },
        )

        result = await DiscountService.process_ai_message_for_discounts(
            bot_id=bot_id,
            chat_id=chat_id,
            ai_message=synthetic_message,
            bot_token=bot_token,
            user_telegram_id=user_id,
        )

        if not result:
            return DiscountDebugCommandResult(
                handled=True,
                reply="⚠️ Não foi possível gerar o PIX para este teste. Verifique os logs.",
            )

        return DiscountDebugCommandResult(handled=True, reply=None)

    return DiscountDebugCommandResult(handled=False)


def _build_tail(inline_suffix: str, args_suffix: str) -> str:
    inline = inline_suffix or ""
    args = args_suffix.strip()
    parts = []
    if inline:
        parts.append(inline.strip())
    if args:
        parts.append(args)
    return " ".join(parts).strip()


def _compose_message(trigger: str, tail: str) -> str:
    if not tail:
        return trigger

    if tail[0] in (":", "-"):
        message = f"{trigger}{tail}"
    else:
        message = f"{trigger} {tail}"

    return re.sub(r"\s+", " ", message).strip()


__all__ = [
    "DiscountDebugCommandResult",
    "try_handle_discount_debug_command",
]
