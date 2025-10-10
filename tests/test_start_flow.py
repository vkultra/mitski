import asyncio
from unittest.mock import AsyncMock

import pytest

from database.repos import (
    StartMessageStatusRepository,
    StartTemplateBlockRepository,
    StartTemplateRepository,
)
from services.start import StartFlowService, StartTemplateService
from workers.start_tasks import send_start_message


@pytest.mark.asyncio
async def test_handle_start_command_schedules_once(
    db_session, sample_bot, fake_redis, monkeypatch
):
    monkeypatch.setattr("core.redis_client.redis_client", fake_redis)
    monkeypatch.setattr("services.start.template_service.redis_client", fake_redis)
    monkeypatch.setattr("services.start.start_flow.redis_client", fake_redis)

    template = await StartTemplateRepository.get_or_create(sample_bot.id)
    await StartTemplateBlockRepository.create_block(
        template_id=template.id,
        order=1,
        text="Olá!",
    )

    scheduled_calls = []

    def fake_delay(**kwargs):
        scheduled_calls.append(kwargs)

    monkeypatch.setattr("workers.start_tasks.send_start_message.delay", fake_delay)

    handled = await StartFlowService.handle_start_command(
        bot=sample_bot,
        user_id=111,
        chat_id=111,
    )
    assert handled is True
    assert len(scheduled_calls) == 1

    # Segunda tentativa deve falhar pelo pending lock
    handled_again = await StartFlowService.handle_start_command(
        bot=sample_bot,
        user_id=111,
        chat_id=111,
    )
    assert handled_again is False

    # Libera pending e simula envio concluído
    StartFlowService.release_pending(sample_bot.id, 111)
    await StartMessageStatusRepository.mark_sent(
        bot_id=sample_bot.id,
        user_telegram_id=111,
        template_version=template.version,
    )

    handled_after_sent = await StartFlowService.handle_start_command(
        bot=sample_bot,
        user_id=111,
        chat_id=111,
    )
    assert handled_after_sent is False


@pytest.mark.usefixtures("mock_telegram_api")
def test_send_start_message_marks_sent(db_session, sample_bot, fake_redis, monkeypatch):
    monkeypatch.setattr("core.redis_client.redis_client", fake_redis)
    monkeypatch.setattr("services.start.template_service.redis_client", fake_redis)
    monkeypatch.setattr("services.start.start_flow.redis_client", fake_redis)

    async def _prepare() -> int:
        template = await StartTemplateRepository.get_or_create(sample_bot.id)
        await StartTemplateBlockRepository.create_block(
            template_id=template.id,
            order=1,
            text="Bem-vindo!",
        )
        return template.id

    template_id = asyncio.run(_prepare())

    pending_key = f"start_template:pending:{sample_bot.id}:{222}"
    fake_redis.set(pending_key, "1")

    async def fake_send_template(*_args, **_kwargs):
        return [123]

    monkeypatch.setattr(
        "services.start.start_sender.StartTemplateSenderService.send_template",
        AsyncMock(side_effect=fake_send_template),
    )
    monkeypatch.setattr("core.security.decrypt", lambda _token: "TEST_TOKEN")
    monkeypatch.setattr("workers.start_tasks.decrypt", lambda _token: "TEST_TOKEN")

    template_version = asyncio.run(
        StartTemplateService.get_metadata(sample_bot.id)
    ).version

    result = send_start_message.apply(
        args=(sample_bot.id, template_id, template_version, 222, 222)
    )
    assert result.successful()

    status = StartMessageStatusRepository.get_version_sync(sample_bot.id, 222)
    assert status == template_version

    # Pending precisa ser liberado
    assert not fake_redis.exists(pending_key)
