"""Serviço responsável por detectar termos de desconto e responder com blocos customizados."""

from __future__ import annotations

import re
from typing import Dict, Optional

from core.telemetry import logger
from database.repos import OfferDiscountBlockRepository, OfferRepository
from services.gateway import PixProcessor
from workers.payment_tasks import start_payment_verification

from .discount_sender import DiscountSender

_MIN_VALUE_CENTS = 50  # R$ 0,50
_MAX_VALUE_CENTS = 1_000_000  # R$ 10.000,00


class DiscountService:
    """Processa mensagens da IA buscando termos configurados de desconto."""

    @classmethod
    async def process_ai_message_for_discounts(
        cls,
        bot_id: int,
        chat_id: int,
        ai_message: str,
        bot_token: str,
        user_telegram_id: Optional[int],
    ) -> Optional[Dict[str, object]]:
        if not ai_message or not user_telegram_id:
            return None

        offers = await OfferRepository.get_offers_by_bot(bot_id, active_only=True)
        if not offers:
            return None

        matched = None
        for offer in offers:
            if not offer.discount_trigger:
                continue
            result = cls._match_discount(offer.discount_trigger, ai_message)
            if result:
                matched = (offer, result)
                break

        if not matched:
            return None

        offer, value_cents = matched

        blocks = await OfferDiscountBlockRepository.get_blocks_by_offer(offer.id)
        if not blocks:
            logger.warning(
                "Discount trigger matched but no blocks configured",
                extra={"offer_id": offer.id},
            )
            return None

        transaction = await PixProcessor.generate_pix_for_offer(
            offer_id=offer.id,
            bot_id=bot_id,
            user_telegram_id=user_telegram_id,
            chat_id=chat_id,
            value_cents=value_cents,
        )

        if not transaction:
            logger.error(
                "Failed to generate PIX for discount",
                extra={
                    "offer_id": offer.id,
                    "bot_id": bot_id,
                    "chat_id": chat_id,
                    "value_cents": value_cents,
                },
            )
            return None

        pix_code = PixProcessor.format_pix_code(transaction.qr_code)

        sender = DiscountSender(bot_token)
        await sender.send_discount_blocks(
            offer_id=offer.id,
            chat_id=chat_id,
            pix_code=pix_code,
            preview_mode=False,
            bot_id=bot_id,
        )

        start_payment_verification.delay(transaction.id)

        logger.info(
            "Discount flow triggered",
            extra={
                "offer_id": offer.id,
                "chat_id": chat_id,
                "value_cents": value_cents,
                "transaction_id": transaction.id,
            },
        )

        return {
            "replaced_message": True,
            "offer_id": offer.id,
            "value_cents": value_cents,
            "transaction_id": transaction.id,
        }

    @staticmethod
    def _match_discount(trigger: str, message: str) -> Optional[int]:
        pattern = re.compile(
            rf"{re.escape(trigger)}\s*[:\-]?\s*([0-9]+(?:[.,][0-9]{{1,2}})?)",
            re.IGNORECASE,
        )

        matches = list(pattern.finditer(message))
        if not matches:
            return None

        value_str = matches[-1].group(1)
        value_cents = DiscountService._parse_value_to_cents(value_str)
        if value_cents is None:
            logger.debug(
                "Failed to parse discount value",
                extra={"trigger": trigger, "value_str": value_str},
            )
            return None

        if value_cents < _MIN_VALUE_CENTS or value_cents > _MAX_VALUE_CENTS:
            logger.warning(
                "Discount value outside allowed range",
                extra={"trigger": trigger, "value_cents": value_cents},
            )
            return None

        return value_cents

    @staticmethod
    def _parse_value_to_cents(raw_value: str) -> Optional[int]:
        value = raw_value.strip()
        if not value:
            return None

        normalized = value.replace(" ", "")
        # Se existir vírgula, assume padrão brasileiro
        if "," in normalized and normalized.count(",") == 1:
            normalized = normalized.replace(".", "")
            normalized = normalized.replace(",", ".")

        try:
            value_float = float(normalized)
        except ValueError:
            return None

        value_cents = int(round(value_float * 100))
        return value_cents if value_cents >= 0 else None
