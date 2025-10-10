"""Tests for phase trigger handling in AIConversationService."""

from unittest.mock import AsyncMock, patch

import pytest

from database.models import ConversationHistory, UserAISession
from database.repos import AIConfigRepository, AIPhaseRepository
from services.ai.conversation import AIConversationService


@pytest.mark.asyncio
async def test_phase_trigger_runs_second_completion(db_session, sample_bot):
    """Ensure trigger terms are internal and a second completion uses the new phase."""

    await AIConfigRepository.create_config(
        bot_id=sample_bot.id,
        model_type="reasoning",
        general_prompt="Prompt base",
    )

    await AIPhaseRepository.create_phase(
        bot_id=sample_bot.id,
        name="Inicial",
        prompt="Prompt inicial",
        trigger=None,
        is_initial=True,
        order=0,
    )

    new_phase = await AIPhaseRepository.create_phase(
        bot_id=sample_bot.id,
        name="Oferta",
        prompt="Prompt oferta",
        trigger="etap3",
        is_initial=False,
        order=1,
    )

    user_telegram_id = 111222333

    with (
        patch("services.ai.conversation.GrokAPIClient") as mock_grok_client,
        patch(
            "services.offers.discount_service.DiscountService.process_ai_message_for_discounts",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "services.offers.offer_service.OfferService.process_ai_message_for_offers",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "services.upsell.TriggerDetector.detect_upsell_trigger",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "services.ai.actions.action_service.ActionService.get_tracked_actions_status",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "services.ai.actions.action_service.ActionService.process_ai_message_for_actions",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "services.ai.conversation.AIConversationService._check_manual_verification_trigger",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "services.upsell.UpsellPhaseManager.get_active_upsell",
            new=AsyncMock(return_value=None),
        ),
    ):
        grok_instance = mock_grok_client.return_value
        grok_instance.chat_completion = AsyncMock(
            side_effect=[
                {"content": "etap3", "usage": {"total_tokens": 10}},
                {
                    "content": "Resposta final após troca de fase",
                    "usage": {"total_tokens": 20},
                },
            ]
        )
        grok_instance.extract_response = AsyncMock(
            side_effect=[
                {"content": "etap3", "usage": {"total_tokens": 10}},
                {
                    "content": "Resposta final após troca de fase",
                    "usage": {"total_tokens": 20},
                },
            ]
        )
        grok_instance.close = AsyncMock(return_value=None)

        response = await AIConversationService.process_user_message(
            bot_id=sample_bot.id,
            user_telegram_id=user_telegram_id,
            text="oi",
            photo_file_ids=None,
            bot_token="fake-token",
            xai_api_key="fake-key",
        )

    assert response == "Resposta final após troca de fase"
    assert grok_instance.chat_completion.await_count == 2

    history_rows = (
        db_session.query(ConversationHistory).order_by(ConversationHistory.id).all()
    )
    assert len(history_rows) == 2
    assert history_rows[0].role == "user"
    assert history_rows[1].role == "assistant"
    assert "etap3" not in history_rows[1].content.lower()

    session = (
        db_session.query(UserAISession)
        .filter(
            UserAISession.bot_id == sample_bot.id,
            UserAISession.user_telegram_id == user_telegram_id,
        )
        .first()
    )
    assert session is not None
    assert session.current_phase_id == new_phase.id
