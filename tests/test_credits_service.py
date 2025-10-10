import asyncio
import types

import pytest

from core.token_costs import TextUsage, text_cost_brl_cents
from handlers.credits_handlers import handle_credits_menu
from services.credits.credit_service import CreditService


class DummyBot:
    def __init__(self, admin_id: int) -> None:
        self.admin_id = admin_id


@pytest.mark.asyncio
async def test_precheck_text_blocks_when_insufficient(monkeypatch):
    # Bot with admin_id=1
    monkeypatch.setattr(
        "database.repos.BotRepository.get_bot_by_id",
        lambda bot_id: DummyAwait(DummyBot(1)),
    )
    # No balance
    monkeypatch.setattr(
        "database.credits_repos.CreditWalletRepository.get_balance_cents_sync",
        lambda admin_id: 0,
    )
    # No history
    monkeypatch.setattr(
        "database.repos.ConversationHistoryRepository.get_recent_messages",
        lambda bot_id, user_telegram_id, limit=16: DummyAwait([]),
    )

    async def tokenizer_call(text: str) -> int:
        return 200_000  # enough tokens to yield cost >= 1 cent

    ok = await CreditService.precheck_text(
        bot_id=123,
        user_telegram_id=555,
        messages=[{"role": "user", "content": "hello"}],
        max_tokens=1000,
        tokenizer_call=tokenizer_call,
    )
    assert ok is False


def test_debit_text_usage_calls_ledger(monkeypatch):
    # Bot sync
    monkeypatch.setattr(
        "database.repos.BotRepository.get_bot_by_id_sync",
        lambda bot_id: DummyBot(1),
    )
    captured = {}

    def debit_if_enough_balance_sync(
        admin_id, amount_cents, category, bot_id, user_telegram_id=None, note=None
    ):
        captured["amount"] = int(amount_cents)
        return True

    monkeypatch.setattr(
        "database.credits_repos.CreditLedgerRepository.debit_if_enough_balance_sync",
        debit_if_enough_balance_sync,
    )
    usage = {"prompt_tokens": 1000, "completion_tokens": 2000, "cached_tokens": 100}
    cents = CreditService.debit_text_usage(123, usage)
    assert isinstance(cents, int)
    assert (
        cents
        == captured["amount"]
        == text_cost_brl_cents(TextUsage(1000, 2000, 100, 0))
    )


def test_create_topup_uses_pushinrecarga(monkeypatch):
    # Enforce env token
    from core.config import settings

    prev = settings.PUSHINRECARGA
    settings.PUSHINRECARGA = ""
    with pytest.raises(ValueError):
        CreditService.create_topup(admin_id=1, value_cents=1000)

    settings.PUSHINRECARGA = "token"

    def fake_create_pix_sync(token: str, value_cents: int):
        assert token == "token"
        return {"id": "tx1", "qr_code": "PIXCODE", "qr_code_base64": "B64"}

    class T:
        def __init__(self):
            self.id = 1
            self.qr_code = "PIXCODE"
            self.qr_code_base64 = "B64"
            self.value_cents = 1000

    monkeypatch.setattr(
        "services.gateway.pushinpay_client.PushinPayClient.create_pix_sync",
        fake_create_pix_sync,
    )
    monkeypatch.setattr(
        "database.credits_repos.CreditTopupRepository.create_sync", lambda **kw: T()
    )
    topup = CreditService.create_topup(admin_id=1, value_cents=1000)
    assert topup.qr_code == "PIXCODE"


@pytest.mark.asyncio
async def test_handlers_amount_click_markdownv2(monkeypatch):
    from handlers.credits_handlers import handle_credits_amount_click

    class T:
        def __init__(self):
            self.id = 42
            self.qr_code = "CHAVEPIX"
            self.qr_code_base64 = None
            self.value_cents = 1000

    monkeypatch.setattr(
        "services.credits.credit_service.CreditService.create_topup",
        lambda uid, cents: T(),
    )
    monkeypatch.setattr(
        "workers.credits_tasks.start_topup_verification.delay", lambda *_a, **_k: None
    )
    res = await handle_credits_amount_click(1, 1000)
    assert res.get("parse_mode") == "MarkdownV2"
    assert "```" in res.get("text", "")
    assert "Verificar deposito" in str(res.get("keyboard"))


@pytest.mark.asyncio
async def test_handle_credits_menu_unlimited(monkeypatch):
    monkeypatch.setattr(
        "handlers.credits_handlers.is_unlimited_admin", lambda uid: True
    )
    monkeypatch.setattr(
        "database.credits_repos.CreditWalletRepository.get_balance_cents_sync",
        lambda uid: 999999,
    )

    def fake_sum(admin_id, entry_type, start, end, categories=None):
        duration = (end - start).total_seconds()
        if entry_type == "credit":
            return 5000 if duration > 86_400 else 0
        if entry_type == "debit":
            return 2000 if duration > 86_400 else 700
        return 0

    monkeypatch.setattr("handlers.credits_handlers.sum_ledger_amount", fake_sum)
    monkeypatch.setattr(
        "handlers.credits_handlers.message_token_stats",
        lambda admin_id, start, end: (12, 3456),
    )

    result = await handle_credits_menu(1)
    text = result["text"]
    assert "CENTRAL DE CRÉDITOS" in text
    assert "♾️ Ilimitado" in text
    assert "Total recarregado" in text
    assert "Tokens" in text
    assert result.get("parse_mode") == "Markdown"


@pytest.mark.asyncio
async def test_handle_credits_menu_regular(monkeypatch):
    monkeypatch.setattr(
        "handlers.credits_handlers.is_unlimited_admin", lambda uid: False
    )
    monkeypatch.setattr(
        "database.credits_repos.CreditWalletRepository.get_balance_cents_sync",
        lambda uid: 12345,
    )

    def fake_sum(admin_id, entry_type, start, end, categories=None):
        if entry_type == "credit":
            return 1000
        if entry_type == "debit":
            return 700
        return 0

    monkeypatch.setattr("handlers.credits_handlers.sum_ledger_amount", fake_sum)
    monkeypatch.setattr(
        "handlers.credits_handlers.message_token_stats",
        lambda admin_id, start, end: (5, 1234),
    )

    result = await handle_credits_menu(99)
    text = result["text"]
    assert "CENTRAL DE CRÉDITOS" in text
    assert "R$" in text
    assert "Total recarregado: R$ 10,00" in text
    assert "Total gasto: R$ 7,00" in text
    assert "Mensagens: 5" in text
    assert "Tokens:" in text
    assert result.get("parse_mode") == "Markdown"


class DummyAwait:
    def __init__(self, value):
        self._value = value

    def __await__(self):
        async def _inner():
            return self._value

        return _inner().__await__()
