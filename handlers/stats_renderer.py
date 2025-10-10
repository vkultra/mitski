"""Rendering helpers for statistics views."""

from __future__ import annotations

from typing import Dict

from services.stats.formatters import (
    format_brl,
    format_count,
    format_day_label,
    format_hour,
    format_percent,
)
from services.stats.keyboards import build_cost_actions, build_main_keyboard
from services.stats.schemas import StatsSummary, StatsWindowMode


def render_view(user_id: int, summary: StatsSummary, view: str) -> Dict[str, object]:
    filter_active = summary.window.mode == StatsWindowMode.RANGE
    base_keyboard = build_main_keyboard(
        summary.window,
        user_id=user_id,
        active_view=view,
        filter_active=filter_active,
    )

    payload: Dict[str, object]
    if view == "top":
        payload = {"text": render_top_bots(summary), "keyboard": base_keyboard}
    elif view == "hours":
        payload = {"text": render_hours(summary), "keyboard": base_keyboard}
    elif view == "phases":
        payload = {"text": render_phases(summary), "keyboard": base_keyboard}
    elif view == "costs":
        cost_keyboard = build_cost_actions(summary.window, user_id=user_id)
        cost_keyboard["inline_keyboard"].extend(base_keyboard["inline_keyboard"])
        payload = {"text": render_costs(summary), "keyboard": cost_keyboard}
    else:
        payload = {"text": render_summary(summary), "keyboard": base_keyboard}

    payload.setdefault("parse_mode", "Markdown")
    return payload


def _period_label(summary: StatsSummary) -> str:
    if summary.window.mode == StatsWindowMode.DAY:
        return format_day_label(summary.window.day)
    return (
        f"{summary.window.start_date.strftime('%d/%m/%Y')} → "
        f"{summary.window.end_date.strftime('%d/%m/%Y')}"
    )


def render_summary(summary: StatsSummary) -> str:
    totals = summary.totals
    parts = [
        f"📈 *Estatísticas — {_period_label(summary)}*",
        "",
        f"🧮 Vendas: {format_count(totals.sales_count)} • 💵 {format_brl(totals.gross_cents)}",
        f"🔁 Upsells: {format_count(totals.upsell_count)} • 💸 {format_brl(totals.upsell_gross_cents)}",
        f"🚀 /starts: {format_count(totals.starts_count)} • ✅ Conversão: {format_percent(totals.conversion)}",
    ]
    if totals.total_cost_cents > 0:
        roi_text = format_percent(totals.roi or 0.0)
        parts.append(
            f"📊 ROI: {roi_text} • 💼 Custos: {format_brl(totals.total_cost_cents)}"
        )
    else:
        parts.append("📊 ROI: Defina custos para acompanhar o desempenho")
    return "\n".join(parts)


def render_top_bots(summary: StatsSummary) -> str:
    lines = ["🏆 *Top bots — desempenho por bot*", ""]
    if not summary.top_bots:
        lines.append("Nenhuma venda registrada no período.")
        return "\n".join(lines)

    for index, bot in enumerate(summary.top_bots[:10], start=1):
        roi_text = "-" if bot.roi is None else format_percent(bot.roi)
        lines.append(
            "\n".join(
                [
                    f"{index}. 🤖 {bot.name}",
                    f"   • Vendas: {format_count(bot.sales_count)} • 💵 {format_brl(bot.gross_cents)}",
                    f"   • Upsells: {format_count(bot.upsell_count)} • 💸 {format_brl(bot.upsell_gross_cents)}",
                    f"   • Conversão: {format_percent(bot.conversion)}",
                    f"   • Custos: {format_brl(bot.allocated_cost_cents)} • ROI: {roi_text}",
                ]
            )
        )
    return "\n".join(lines)


def render_hours(summary: StatsSummary) -> str:
    buckets = sorted(summary.hourly, key=lambda item: item.sales_count, reverse=True)
    if not buckets:
        return "⏰ Ainda não há vendas suficientes para montar o gráfico horário."
    lines = ["⏰ *Horários com mais vendas*", ""]
    for bucket in buckets[:6]:
        lines.append(
            f"{format_hour(bucket.hour)} — {format_count(bucket.sales_count)} vendas • {format_brl(bucket.gross_cents)}"
        )
    return "\n".join(lines)


def render_phases(summary: StatsSummary) -> str:
    if not summary.phases:
        return "📉 Configure fases no menu IA e aguarde interações para ver abandono."
    lines = ["📉 *Taxa de abandono por fase*", ""]
    for item in summary.phases[:10]:
        lines.append(
            f"🤖 Bot {item.bot_id} • {item.phase_name}\n"
            f"   Entraram: {format_count(item.entered)}\n"
            f"   Avançaram: {format_count(item.advanced)}\n"
            f"   ❌ Abandono: {format_percent(item.drop_rate)}"
        )
    return "\n".join(lines)


def render_costs(summary: StatsSummary) -> str:
    lines = ["🧾 *Custos lançados*", ""]
    if not summary.costs:
        lines.append("Nenhum custo informado. Use os botões para registrar.")
    else:
        for entry in summary.costs:
            scope = "Geral" if entry.scope == "general" else f"Bot {entry.bot_id}"
            lines.append(
                f"{entry.day.strftime('%d/%m/%Y')} • {scope} • {format_brl(entry.amount_cents)}"
            )
    lines.append("")
    lines.append(
        "💡 Lance quantos custos quiser no dia. O ROI será recalculado automaticamente."
    )
    return "\n".join(lines)


__all__ = [
    "render_view",
    "render_summary",
    "render_top_bots",
    "render_hours",
    "render_phases",
    "render_costs",
]
