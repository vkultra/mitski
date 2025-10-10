"""Handlers for Credits menu (manager bot). <280 lines"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from core.telemetry import logger


def _escape_mdv2(text: str) -> str:
    """Escapes Telegram MarkdownV2 special chars."""
    if not text:
        return ""
    specials = r"_[]()~`>#+-=|{}.!*"
    out = []
    for ch in text:
        if ch in specials:
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


from database.credits_repos import CreditTopupRepository, CreditWalletRepository
from services.credits.analytics import message_token_stats, sum_ledger_amount
from services.credits.credit_service import CreditService, is_unlimited_admin
from workers.credits_tasks import start_topup_verification, verify_topup_task


def _fmt_brl(cents: int) -> str:
    v = int(cents) / 100.0
    return f"R$ {v:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


async def handle_credits_menu(user_id: int) -> Dict[str, Any]:
    unlimited = is_unlimited_admin(user_id)
    balance_cents = CreditWalletRepository.get_balance_cents_sync(user_id)
    balance_text = "♾️ Ilimitado (Admin)" if unlimited else _fmt_brl(balance_cents)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start_30 = now - timedelta(days=30)
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_today = start_today + timedelta(days=1)

    total_recharged = sum_ledger_amount(
        user_id, "credit", start_30, now, categories=["topup"]
    )
    total_spent = sum_ledger_amount(user_id, "debit", start_30, now, categories=None)
    today_spent = sum_ledger_amount(user_id, "debit", start_today, end_today, None)
    messages_today, tokens_today = message_token_stats(user_id, start_today, end_today)

    tokens_display = f"{tokens_today:,}".replace(",", ".")

    text = (
        "💰 *CENTRAL DE CRÉDITOS*\n\n"
        f"👑 Saldo Atual: {balance_text}\n\n"
        "📊 Resumo (30 dias):\n"
        f"• Total recarregado: {_fmt_brl(total_recharged)}\n"
        f"• Total gasto: {_fmt_brl(total_spent)}\n\n"
        "📈 Hoje:\n"
        f"• Mensagens: {messages_today}\n"
        f"• Tokens: {tokens_display}\n"
        f"• Gasto: {_fmt_brl(today_spent)}\n\n"
        "Escolha uma opção:"
    )

    keyboard = {
        "inline_keyboard": [
            [{"text": "➕ Adicionar Créditos", "callback_data": "credits_add"}],
            [{"text": "🧾 Minhas recargas", "callback_data": "credits_list"}],
            [{"text": "🔙 Voltar", "callback_data": "back_to_main"}],
        ]
    }
    return {"text": text, "keyboard": keyboard, "parse_mode": "Markdown"}


async def handle_credits_add(user_id: int) -> Dict[str, Any]:
    amounts = [1000, 2500, 5000, 10000]  # R$10, 25, 50, 100
    buttons = [
        [
            {
                "text": _fmt_brl(v),
                "callback_data": f"credits_amount:{v}",
            }
        ]
        for v in amounts
    ]
    buttons.append([{"text": "🔙 Voltar", "callback_data": "credits_menu"}])
    return {
        "text": "Selecione um valor para recarga via PIX:",
        "keyboard": {"inline_keyboard": buttons},
    }


async def handle_credits_amount_click(user_id: int, cents: int) -> Dict[str, Any]:
    if cents < 500:  # min R$5
        return {"text": "Valor mínimo é R$ 5,00.", "keyboard": None}
    try:
        topup = CreditService.create_topup(user_id, cents)
        # schedule auto verification
        start_topup_verification.delay(topup.id)
        # show qr
        header = _escape_mdv2("Recarga criada")
        value_line = _escape_mdv2(f"Valor: {_fmt_brl(cents)}")
        instr = _escape_mdv2("Use a chave PIX abaixo copia e cola para pagar")
        footer = _escape_mdv2("Depois de pagar toque em Verificar deposito")
        code = topup.qr_code or ""
        text = f"{header}\n\n{value_line}\n\n{instr}\n\n```\n{code}\n```\n\n{footer}"
        kb = {
            "inline_keyboard": [
                [
                    {
                        "text": "🔍 Verificar deposito",
                        "callback_data": f"credits_check:{topup.id}",
                    }
                ],
                [{"text": "🔙 Voltar", "callback_data": "credits_menu"}],
            ]
        }
        return {"text": text, "keyboard": kb, "parse_mode": "MarkdownV2"}
    except Exception as e:
        logger.error("Create topup failed", extra={"user": user_id, "error": str(e)})
        return {
            "text": "❌ Falha ao criar recarga. Verifique o Gateway.",
            "keyboard": None,
        }


async def handle_credits_check(user_id: int, topup_id: int) -> Dict[str, Any]:
    # trigger verification now
    verify_topup_task.delay(topup_id)
    topup = CreditTopupRepository.get_by_id_sync(topup_id)
    if not topup:
        return {"text": "Transação não encontrada.", "keyboard": None}

    if topup.status == "paid":
        balance = CreditWalletRepository.get_balance_cents_sync(user_id)
        return {
            "text": (
                "✅ Pagamento confirmado e saldo creditado!\n\n"
                f"Saldo atual: *{_fmt_brl(balance)}*"
            ),
            "keyboard": {
                "inline_keyboard": [
                    [{"text": "🔙 Voltar", "callback_data": "credits_menu"}]
                ]
            },
        }

    return {
        "text": (
            f"Status atual: *{topup.status}*.\n\n"
            "Se você acabou de pagar, aguarde até 1 minuto e verifique novamente."
        ),
        "keyboard": {
            "inline_keyboard": [
                [
                    {
                        "text": "🔄 Verificar novamente",
                        "callback_data": f"credits_check:{topup.id}",
                    }
                ],
                [{"text": "🔙 Voltar", "callback_data": "credits_menu"}],
            ]
        },
    }


async def handle_credits_list(user_id: int) -> Dict[str, Any]:
    items = CreditTopupRepository.list_recent_by_admin_sync(user_id, limit=5)
    if not items:
        return {
            "text": "🧾 Você ainda não tem recargas.",
            "keyboard": {
                "inline_keyboard": [
                    [{"text": "🔙 Voltar", "callback_data": "credits_menu"}]
                ]
            },
        }
    lines = []
    for t in items:
        lines.append(
            f"• {_fmt_brl(int(t.value_cents))} — {t.status} — {t.created_at.strftime('%d/%m %H:%M')}"
        )
    text = "\n".join(lines)
    return {
        "text": f"🧾 Últimas recargas:\n\n{text}",
        "keyboard": {
            "inline_keyboard": [
                [{"text": "🔙 Voltar", "callback_data": "credits_menu"}]
            ]
        },
    }


__all__ = [
    "handle_credits_menu",
    "handle_credits_add",
    "handle_credits_amount_click",
    "handle_credits_check",
    "handle_credits_list",
]
