"""Main menu, creation flow and toggle actions for tracking."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Sequence

from database.repos import BotRepository
from handlers.tracking.tokens import build_token
from handlers.tracking.utils import encode_day_page, escape_md
from services.conversation_state import ConversationStateManager
from services.stats.formatters import format_brl
from services.tracking.runtime import should_ignore_untracked
from services.tracking.service import TrackerNotFoundError, TrackerService
from services.tracking.types import TrackerView


async def render_main_menu(user_id: int, service: TrackerService) -> Dict[str, Any]:
    today = date.today()
    bots = await BotRepository.get_bots_by_admin(user_id)
    toggle_label = await _toggle_summary(bots)
    top = service.top_daily(day=today)
    text = _main_text(top, today)
    keyboard = {
        "inline_keyboard": [
            [{"text": "➕ Novo", "callback_data": build_token("n", user_id=user_id)}],
            [
                {
                    "text": "📋 Meus Rastreios",
                    "callback_data": build_token(
                        "l", user_id=user_id, extra=encode_day_page(today, 1)
                    ),
                }
            ],
            [
                {
                    "text": f"🛡️ Bloquear /start sem rastreio: {toggle_label}",
                    "callback_data": build_token("t", user_id=user_id),
                }
            ],
            [
                {
                    "text": "🔄 Atualizar",
                    "callback_data": build_token("m", user_id=user_id),
                }
            ],
        ]
    }
    return {"text": text, "keyboard": keyboard, "parse_mode": "Markdown"}


async def start_creation(user_id: int) -> Dict[str, Any]:
    bots = await BotRepository.get_bots_by_admin(user_id)
    if not bots:
        return {"text": "⚠️ Cadastre um bot antes de criar rastreios."}
    if len(bots) == 1:
        return prompt_name(user_id, bots[0].id)
    rows = []
    for bot in bots:
        label = f"@{bot.username}" if bot.username else f"Bot {bot.id}"
        rows.append(
            [
                {
                    "text": label,
                    "callback_data": build_token("b", user_id=user_id, bot_id=bot.id),
                }
            ]
        )
    rows.append(
        [{"text": "⬅️ Menu", "callback_data": build_token("m", user_id=user_id)}]
    )
    return {
        "text": "Selecione qual bot deseja usar com esse rastreio:",
        "keyboard": {"inline_keyboard": rows},
    }


def prompt_name(user_id: int, bot_id: int) -> Dict[str, Any]:
    ConversationStateManager.set_state(user_id, "tracking:new_name", {"bot_id": bot_id})
    return {
        "text": (
            "🆕 *Novo rastreio*\n"
            "Envie um nome para identificar esse link (ex: Campanha Stories Junho).\n"
            "O nome pode ter até 48 caracteres."
        ),
        "keyboard": {"force_reply": True},
        "parse_mode": "Markdown",
    }


async def render_toggle_menu(service: TrackerService, user_id: int) -> Dict[str, Any]:
    bots = await BotRepository.get_bots_by_admin(user_id)
    if not bots:
        return {"text": "⚠️ Nenhum bot cadastrado."}
    rows = []
    for bot in bots:
        flag, active = service.get_toggle_state(bot.id)
        emoji = "✅" if flag else "❌"
        suffix = "(sem rastreios)" if active == 0 else f"({active} links)"
        label = f"{emoji} @{bot.username or bot.id} {suffix}"
        rows.append(
            [
                {
                    "text": label,
                    "callback_data": build_token(
                        "g",
                        user_id=user_id,
                        bot_id=bot.id,
                        extra="on" if not flag else "off",
                    ),
                }
            ]
        )
    rows.append(
        [{"text": "⬅️ Menu", "callback_data": build_token("m", user_id=user_id)}]
    )
    text = (
        "🛡️ *Bloquear /start sem rastreio*\n"
        "Quando ativo, o bot ignora qualquer /start sem código gerado neste menu.\n"
        "Bots sem rastreio ativo continuam respondendo normalmente."
    )
    return {
        "text": text,
        "keyboard": {"inline_keyboard": rows},
        "parse_mode": "Markdown",
    }


def apply_toggle(
    service: TrackerService, user_id: int, bot_id: int, enable: bool
) -> Dict[str, Any]:
    flag, active = service.set_toggle_state(bot_id, enabled=enable)
    status = "✅ Ativo" if flag else "❌ Desligado"
    if active == 0:
        note = "Nenhum rastreio ativo; novos /start continuarão respondendo."
    else:
        note = "Somente links com código receberão resposta."
    return {
        "text": f"🛡️ Ajuste salvo: {status}. {note}",
        "keyboard": {
            "inline_keyboard": [
                [
                    {
                        "text": "⬅️ Menu",
                        "callback_data": build_token("m", user_id=user_id),
                    }
                ]
            ]
        },
    }


async def handle_text_input(
    user_id: int, text: str, state: Dict[str, Any]
) -> Dict[str, Any]:
    bot_id = state.get("data", {}).get("bot_id")
    if not bot_id:
        ConversationStateManager.clear_state(user_id)
        return {"text": "⚠️ Contexto perdido. Abra o menu novamente."}
    ConversationStateManager.clear_state(user_id)
    service = TrackerService(user_id)
    try:
        tracker = service.create(bot_id=bot_id, name=text)
    except ValueError as exc:
        return {"text": f"❌ {exc}"}
    except TrackerNotFoundError:
        return {"text": "⚠️ Não encontrei esse bot."}
    except Exception as exc:  # pragma: no cover - erro inesperado
        return {"text": f"⚠️ Falha ao criar rastreio: {exc}"}
    message = (
        "✅ *Rastreio criado!*\n"
        f"Nome: *{escape_md(tracker.name)}* (@{tracker.bot_username})\n"
        f"Deep link: `{tracker.link}`\n"
        "Comece a divulgar esse link e acompanhe os resultados aqui."
    )
    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "🔗 Link",
                    "callback_data": build_token(
                        "k", user_id=user_id, tracker_id=tracker.id
                    ),
                },
                {
                    "text": "📊 Dia",
                    "callback_data": build_token(
                        "d",
                        user_id=user_id,
                        tracker_id=tracker.id,
                        extra=date.today().strftime("%Y%m%d"),
                    ),
                },
                {
                    "text": "🗑️ Apagar",
                    "callback_data": build_token(
                        "x",
                        user_id=user_id,
                        tracker_id=tracker.id,
                        extra=date.today().strftime("%Y%m%d"),
                    ),
                },
            ],
            [{"text": "⬅️ Menu", "callback_data": build_token("m", user_id=user_id)}],
        ]
    }
    return {"text": message, "keyboard": keyboard, "parse_mode": "Markdown"}


async def _toggle_summary(bots: Sequence[Any]) -> str:
    enabled = 0
    for bot in bots:
        flag, _ = should_ignore_untracked(bot.id)
        if flag:
            enabled += 1
    return "✅ Ativo" if enabled else "❌ Desligado"


def _main_text(top: Sequence[TrackerView], today: date) -> str:
    lines = [
        "📈 *Rastreio — acompanhe seus links*",
        "",
        "Crie quantos rastreios quiser para cada bot e monitore starts e vendas em segundos.",
        "",
    ]
    if top:
        lines.append(f"🏆 *Destaques de hoje ({today.strftime('%d/%m/%Y')})*: ")
        for item in top:
            bot_label = f"@{item.bot_username}" if item.bot_username else ""
            lines.append(
                f"• {escape_md(item.name)} {bot_label} — 👤 {item.starts} • 🛒 {item.sales} • 💰 {format_brl(item.revenue_cents)}"
            )
    else:
        lines.append(
            "Sem dados hoje ainda. Toque em ➕ Novo para gerar seu primeiro link de rastreio."
        )
    lines.append(
        "\nUse os botões para criar, listar ou ajustar o comportamento do /start."
    )
    return "\n".join(lines)


__all__ = [
    "render_main_menu",
    "start_creation",
    "prompt_name",
    "render_toggle_menu",
    "apply_toggle",
    "handle_text_input",
]
