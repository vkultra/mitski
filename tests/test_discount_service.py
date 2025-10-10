import types
from unittest.mock import AsyncMock, patch

import pytest

from database.repos import OfferDiscountBlockRepository, OfferRepository
from services.offers.discount_service import DiscountService


@pytest.mark.asyncio
async def test_match_discount_case_insensitive_and_embedded():
    trigger = "fechoupack"
    message = "Olha, TESTEFechouPack15 reais"

    result = DiscountService._match_discount(trigger, message)

    assert result == 1500


@pytest.mark.asyncio
async def test_process_ai_message_for_discounts_triggers_pix(
    db_session, sample_bot, sample_offer
):
    await OfferRepository.update_offer(sample_offer.id, discount_trigger="fechoupack")
    await OfferDiscountBlockRepository.create_block(
        offer_id=sample_offer.id,
        order=1,
        text="Obrigado! Pague usando {pix}.",
        delay_seconds=0,
        auto_delete_seconds=0,
    )

    fake_transaction = types.SimpleNamespace(
        id=42,
        qr_code="00020126360014BR.GOV.BCB.PIX0114+55119999999990203PIX520400005303986540510.005802BR5925DESCONTO TESTE6009SAO PAULO61080540900062070503999",
    )

    with (
        patch(
            "services.offers.discount_service.PixProcessor.generate_pix_for_offer",
            new=AsyncMock(return_value=fake_transaction),
        ) as pix_mock,
        patch(
            "services.offers.discount_service.DiscountSender.send_discount_blocks",
            new=AsyncMock(),
        ) as sender_mock,
        patch(
            "services.offers.discount_service.start_payment_verification.delay"
        ) as delay_mock,
    ):
        result = await DiscountService.process_ai_message_for_discounts(
            bot_id=sample_bot.id,
            chat_id=987654321,
            ai_message="FechouPack 50,00?",
            bot_token="fake-token",
            user_telegram_id=987654321,
        )

    pix_mock.assert_awaited_once()
    sender_mock.assert_awaited_once()
    delay_mock.assert_called_once_with(fake_transaction.id)

    assert result is not None
    assert result["replaced_message"] is True
    assert result["value_cents"] == 5000
