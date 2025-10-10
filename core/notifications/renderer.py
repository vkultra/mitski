"""Renderização das mensagens de notificação de vendas."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from html import escape
from typing import Optional

Currency = str


@dataclass(frozen=True)
class SaleMessageData:
    """Dados necessários para montar a mensagem de venda."""

    amount_cents: Optional[int]
    currency: Currency = "BRL"
    buyer_username: Optional[str] = None
    buyer_user_id: Optional[int] = None
    bot_username: Optional[str] = None
    is_upsell: bool = False


def _format_currency(amount_cents: Optional[int], currency: Currency) -> str:
    if amount_cents is None:
        return "Valor não informado"

    value = (Decimal(amount_cents) / Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    formatted = f"{value:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
    prefix = "R$" if currency.upper() == "BRL" else currency.upper()
    return f"{prefix} {formatted}"


def _format_username(username: Optional[str]) -> str:
    if not username:
        return "Usuário sem username"
    username = username.lstrip("@")
    return f"@{escape(username)}"


def render_sale_message(data: SaleMessageData) -> str:
    """Constrói a mensagem HTML respeitando o formato definido."""

    amount_text = escape(_format_currency(data.amount_cents, data.currency))
    buyer_username = _format_username(data.buyer_username)
    buyer_id = (
        str(data.buyer_user_id) if data.buyer_user_id is not None else "não informado"
    )
    bot_username = data.bot_username or "Bot sem username"

    bot_display = (
        f"@{escape(bot_username.lstrip('@'))}"
        if bot_username.startswith("@")
        else escape(bot_username)
    )

    lines = ["🎉 <b>Venda Aprovada!</b>"]
    if data.is_upsell:
        lines.append("🛒 <b>Tipo:</b> Upsell")
    lines.append(f"💰 <b>Valor:</b> {amount_text}")
    lines.append(f"👤 <b>Usuário:</b> {buyer_username} [ID: {escape(buyer_id)}]")
    lines.append(f"🤖 <b>Bot:</b> {bot_display}")

    return "\n".join(lines)


__all__ = ["SaleMessageData", "render_sale_message"]
