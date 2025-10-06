"""Testes para o módulo de notificações de vendas."""

from __future__ import annotations

from types import SimpleNamespace
from typing import List
from unittest.mock import MagicMock

import pytest

from core.notifications.renderer import SaleMessageData, render_sale_message
from database.notifications.repos import (
    NotificationSettingsRepository,
    SaleNotificationsRepository,
)
from services.sales import emit_sale_approved


def test_notification_settings_repository(db_session, sample_bot):
    owner_id = sample_bot.admin_id

    default = NotificationSettingsRepository.upsert_channel_sync(owner_id, -1001)
    assert default.channel_id == -1001
    assert default.enabled is True

    fetched_default = NotificationSettingsRepository.get_default_sync(owner_id)
    assert fetched_default.channel_id == -1001

    scoped = NotificationSettingsRepository.upsert_channel_sync(
        owner_id, -2002, bot_id=sample_bot.id
    )
    assert scoped.channel_id == -2002

    fetched_scoped = NotificationSettingsRepository.get_for_owner_sync(
        owner_id, sample_bot.id
    )
    assert fetched_scoped.id == scoped.id

    NotificationSettingsRepository.disable_sync(owner_id, sample_bot.id)
    disabled = NotificationSettingsRepository.get_for_owner_sync(owner_id, sample_bot.id)
    assert disabled.enabled is False


def test_sale_notifications_repository(db_session, sample_bot):
    transaction_id = "tx-123"
    data = {
        "transaction_id": transaction_id,
        "provider": "auto",
        "owner_user_id": sample_bot.admin_id,
        "bot_id": sample_bot.id,
        "channel_id": -555,
        "is_upsell": False,
        "amount_cents": 1299,
        "currency": "BRL",
        "buyer_user_id": 999,
        "buyer_username": "cliente",
        "bot_username": sample_bot.username,
        "origin": "auto",
        "status": "pending",
    }

    record, created = SaleNotificationsRepository.create_if_absent_sync(data)
    assert created is True
    assert record.status == "pending"

    duplicate, created_again = SaleNotificationsRepository.create_if_absent_sync(data)
    assert created_again is False
    assert duplicate.id == record.id

    SaleNotificationsRepository.mark_status_sync(transaction_id, status="sent")
    updated = SaleNotificationsRepository.get_by_transaction_sync(transaction_id)
    assert updated.status == "sent"


def test_render_sale_message_formatting():
    message = render_sale_message(
        SaleMessageData(
            amount_cents=12345,
            buyer_username="cliente",
            buyer_user_id=555,
            bot_username="meubot",
            is_upsell=True,
        )
    )

    assert "🎉" in message
    assert "<b>Valor:</b> R$ 123,45" in message
    assert "Tipo" in message
    assert "ID: 555" in message


def test_emit_sale_approved_enqueues(monkeypatch):
    calls: List[tuple[str, str]] = []

    monkeypatch.setattr("services.sales.events.acquire_sale_lock", lambda *_, **__: True)
    monkeypatch.setattr("services.sales.events.release_sale_lock", lambda *_, **__: None)

    class DummyTask:
        def delay(self, transaction_identifier: str, origin: str = "auto") -> None:
            calls.append((transaction_identifier, origin))

    monkeypatch.setattr(
        "workers.notifications.tasks.enqueue_sale_notification",
        DummyTask(),
    )
    monkeypatch.setattr("services.sales.events.inc_enqueued", lambda *_: None)
    monkeypatch.setattr("services.sales.events.settings", SimpleNamespace(ENABLE_SALE_NOTIFICATIONS=True))

    assert emit_sale_approved("tx-abc", origin="manual") is True
    assert calls == [("tx-abc", "manual")]

    # Lock bloqueado → não enfileira novamente
    monkeypatch.setattr("services.sales.events.acquire_sale_lock", lambda *_, **__: False)
    assert emit_sale_approved("tx-abc", origin="manual") is False
    assert calls == [("tx-abc", "manual")]


@pytest.mark.asyncio
async def test_handle_notifications_menu(monkeypatch, sample_bot):
    async def fake_list_bots(user_id: int):
        return [sample_bot]

    async def fake_list_settings(user_id: int):
        return [
            SimpleNamespace(bot_id=None, channel_id=-1001, enabled=True),
            SimpleNamespace(bot_id=sample_bot.id, channel_id=-2002, enabled=False),
        ]

    monkeypatch.setattr(
        "handlers.notifications.manager_menu.BotRegistrationService.list_bots",
        fake_list_bots,
    )
    monkeypatch.setattr(
        "handlers.notifications.manager_menu.NotificationSettingsRepository.list_for_owner",
        fake_list_settings,
    )

    from handlers.notifications.manager_menu import handle_notifications_menu

    result = await handle_notifications_menu(sample_bot.admin_id)

    assert "Notificações de Vendas" in result["text"]
    assert "padrão" in result["text"].lower()
    assert result["keyboard"]["inline_keyboard"]


@pytest.mark.asyncio
async def test_validate_and_save_channel(monkeypatch, db_session, sample_bot):
    from handlers.notifications.validation import validate_and_save_channel

    monkeypatch.setattr("handlers.notifications.validation.settings.MANAGER_BOT_TOKEN", "123:token")

    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            self.sent = []

        def get_chat(self, identifier):
            assert identifier == -1001
            return {"id": -1001, "type": "channel"}

        def send_message(self, chat_id, text, parse_mode: str = "HTML", disable_web_page_preview: bool = True):
            self.sent.append((chat_id, text))
            return {"ok": True}

    clients: List[FakeClient] = []

    def fake_client_factory(token: str):
        client = FakeClient(token)
        clients.append(client)
        return client

    monkeypatch.setattr(
        "handlers.notifications.validation.TelegramNotificationClient",
        fake_client_factory,
    )

    response = await validate_and_save_channel(sample_bot.admin_id, None, "-1001")
    assert "Canal salvo" in response["text"]
    assert clients[0].sent[0][0] == -1001

    saved = await NotificationSettingsRepository.get_default(sample_bot.admin_id)
    assert saved.channel_id == -1001


__all__ = ["test_notification_settings_repository"]
