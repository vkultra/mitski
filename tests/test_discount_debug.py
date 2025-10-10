from unittest.mock import AsyncMock, patch

import pytest

from database.repos import OfferRepository
from services.offers.discount_debug import (
    DiscountDebugCommandResult,
    try_handle_discount_debug_command,
)


@pytest.mark.asyncio
async def test_discount_debug_invokes_service_with_synthetic_message(
    db_session, sample_bot, sample_offer
):
    await OfferRepository.update_offer(sample_offer.id, discount_trigger="fechoupack")

    with patch(
        "services.offers.discount_debug.DiscountService.process_ai_message_for_discounts",
        new=AsyncMock(return_value={"replaced_message": True}),
    ) as mock_service:
        result = await try_handle_discount_debug_command(
            bot_id=sample_bot.id,
            chat_id=987,
            user_id=sample_bot.admin_id,
            text="/FechouPack15",
            bot_token="fake",
        )

    assert result == DiscountDebugCommandResult(handled=True, reply=None)
    mock_service.assert_awaited_once_with(
        bot_id=sample_bot.id,
        chat_id=987,
        ai_message="fechoupack 15",
        bot_token="fake",
        user_telegram_id=sample_bot.admin_id,
    )


@pytest.mark.asyncio
async def test_discount_debug_needs_value(db_session, sample_bot, sample_offer):
    await OfferRepository.update_offer(sample_offer.id, discount_trigger="fechoupack")

    result = await try_handle_discount_debug_command(
        bot_id=sample_bot.id,
        chat_id=987,
        user_id=sample_bot.admin_id,
        text="/fechoupack",
        bot_token="fake",
    )

    assert result.handled is True
    assert result.reply and "Informe um valor" in result.reply


@pytest.mark.asyncio
async def test_discount_debug_ignores_non_matching_command(
    db_session, sample_bot, sample_offer
):
    await OfferRepository.update_offer(sample_offer.id, discount_trigger="fechoupack")

    result = await try_handle_discount_debug_command(
        bot_id=sample_bot.id,
        chat_id=987,
        user_id=sample_bot.admin_id,
        text="/outrocomando",
        bot_token="fake",
    )

    assert result.handled is False
    assert result.reply is None


@pytest.mark.asyncio
async def test_discount_debug_returns_error_when_service_fails(
    db_session, sample_bot, sample_offer
):
    await OfferRepository.update_offer(sample_offer.id, discount_trigger="fechoupack")

    with patch(
        "services.offers.discount_debug.DiscountService.process_ai_message_for_discounts",
        new=AsyncMock(return_value=None),
    ):
        result = await try_handle_discount_debug_command(
            bot_id=sample_bot.id,
            chat_id=987,
            user_id=sample_bot.admin_id,
            text="/fechoupack20",
            bot_token="fake",
        )

    assert result.handled is True
    assert (
        result.reply
        == "⚠️ Não foi possível gerar o PIX para este teste. Verifique os logs."
    )
