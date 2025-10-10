"""Handlers for the statistics menu of the manager bot."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from core.redis_client import redis_client
from core.telemetry import logger
from database.stats_costs import CostRepository
from handlers.stats_renderer import render_view
from services.conversation_state import ConversationStateManager
from services.stats.calendar import build_day_picker
from services.stats.callbacks import decode_callback, encode_callback
from services.stats.charts import generate_sales_chart
from services.stats.parser import parse_brl_to_cents
from services.stats.schemas import StatsWindow, StatsWindowMode
from services.stats.service import StatsService


def _service(owner_id: int) -> StatsService:
    return StatsService(owner_id)


async def handle_stats_menu(user_id: int) -> Dict[str, Any]:
    if not _ensure_rate_limit(user_id):
        return {"text": "⏳ Muitas solicitações seguidas. Aguarde e tente novamente."}
    service = _service(user_id)
    window = service.build_window(day=date.today())
    summary = service.load_summary(window)
    response = render_view(user_id, summary, "summary")
    _attach_chart(user_id, service, window, response)
    return response


async def handle_stats_callback(user_id: int, token: str) -> Dict[str, Any]:
    if not _ensure_rate_limit(user_id):
        return {"text": "⏳ Muitas solicitações seguidas. Aguarde alguns segundos."}
    try:
        payload = _decode_token(user_id, token)
    except ValueError as exc:  # noqa: BLE001
        logger.warning("Invalid stats token", extra={"error": str(exc)})
        return {"text": "⚠️ Link expirado. Abra novamente no menu."}

    action = payload.get("action")
    mode = payload.get("mode", "day")
    window = _extract_window(mode, payload)
    service = _service(user_id)

    if action in {"navigate", "refresh"}:
        summary = service.load_summary(window)
        view = payload.get("view", "summary")
        response = render_view(user_id, summary, view)
        _attach_chart(
            user_id,
            service,
            window,
            response,
            force_refresh=action == "refresh",
        )
        return response

    if action == "filter":
        view = payload.get("view", "summary")
        calendar_keyboard = build_day_picker(
            user_id,
            window=window,
            view=view,
            stage="filter_start",
        )
        return {
            "text": "📅 *Selecione a data inicial*",
            "keyboard": calendar_keyboard,
            "parse_mode": "Markdown",
        }

    if action == "filter_start":
        start_iso = payload.get("date")
        if not start_iso:
            return {"text": "⚠️ Data inicial inválida. Tente novamente."}

        start_date = date.fromisoformat(start_iso)
        view = payload.get("view", "summary")
        base_window = (
            _window_from_dict(payload.get("window"))
            if payload.get("window")
            else window
        )

        keyboard = build_day_picker(
            user_id,
            window=base_window,
            view=view,
            stage="filter_end",
            selected_start=start_date,
        )
        text = (
            "📅 *Data inicial selecionada:* "
            f"{start_date.strftime('%d/%m/%Y')}\nSelecione a data final."
        )
        return {"text": text, "keyboard": keyboard, "parse_mode": "Markdown"}

    if action == "filter_start_nav":
        anchor_iso = payload.get("anchor")
        if not anchor_iso:
            return {"text": "⚠️ Navegação inválida."}

        anchor = date.fromisoformat(anchor_iso)
        view = payload.get("view", "summary")
        base_window = (
            _window_from_dict(payload.get("window"))
            if payload.get("window")
            else window
        )
        keyboard = build_day_picker(
            user_id,
            window=base_window,
            view=view,
            stage="filter_start",
            anchor=anchor,
        )
        return {
            "text": "📅 *Selecione a data inicial*",
            "keyboard": keyboard,
            "parse_mode": "Markdown",
        }

    if action == "filter_end":
        start_iso = payload.get("start")
        end_iso = payload.get("date")
        if not start_iso or not end_iso:
            return {"text": "⚠️ Datas inválidas. Tente novamente."}

        start_date = date.fromisoformat(start_iso)
        end_date = date.fromisoformat(end_iso)
        if end_date < start_date:
            start_date, end_date = end_date, start_date

        selected_window = StatsWindow(
            mode=StatsWindowMode.RANGE,
            start_date=start_date,
            end_date=end_date,
        )
        summary = service.load_summary(selected_window)
        view = payload.get("view", "summary")
        response = render_view(user_id, summary, view)
        _attach_chart(user_id, service, selected_window, response)
        return response

    if action == "filter_end_nav":
        start_iso = payload.get("start")
        anchor_iso = payload.get("anchor")
        if not start_iso or not anchor_iso:
            return {"text": "⚠️ Navegação inválida."}

        start_date = date.fromisoformat(start_iso)
        anchor = date.fromisoformat(anchor_iso)
        view = payload.get("view", "summary")
        base_window = (
            _window_from_dict(payload.get("window"))
            if payload.get("window")
            else window
        )
        keyboard = build_day_picker(
            user_id,
            window=base_window,
            view=view,
            stage="filter_end",
            selected_start=start_date,
            anchor=anchor,
        )
        text = (
            "📅 *Data inicial selecionada:* "
            f"{start_date.strftime('%d/%m/%Y')}\nSelecione a data final."
        )
        return {"text": text, "keyboard": keyboard, "parse_mode": "Markdown"}

    if action == "cancel_filter":
        view = payload.get("view", "summary")
        base_window = (
            _window_from_dict(payload.get("window"))
            if payload.get("window")
            else window
        )
        summary = service.load_summary(base_window)
        response = render_view(user_id, summary, view)
        _attach_chart(user_id, service, base_window, response)
        return response

    if action == "cost_add":
        return _handle_cost_add(user_id, service, payload)

    if action == "cost_select":
        ConversationStateManager.set_state(
            user_id,
            "stats:awaiting_cost",
            {
                "scope": "bot",
                "bot_id": payload.get("bot_id"),
                "day": payload.get("day"),
                "mode": mode,
            },
        )
        return {"text": "💰 Informe o custo em R$ para este bot (ex: `R$ 1234,56`)."}

    return {"text": "⚠️ Ação não reconhecida."}


async def handle_stats_text(user_id: int, text: str) -> Optional[Dict[str, Any]]:
    state = ConversationStateManager.get_state(user_id)
    if not state:
        return None

    if state["state"] == "stats:awaiting_cost":
        return _handle_cost_input(user_id, text, state["data"])

    return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _handle_cost_add(
    user_id: int,
    service: StatsService,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    mode = payload.get("mode", "day")
    window = _extract_window(mode, payload)
    scope_type = payload.get("scope_type")
    target_day = payload.get("day") or window.end_date.isoformat()

    if scope_type == "general":
        ConversationStateManager.set_state(
            user_id,
            "stats:awaiting_cost",
            {"scope": "general", "day": target_day, "mode": mode},
        )
        return {"text": "💰 Informe o custo geral em R$ (ex: `R$ 500,00`)."}

    bots = service._load_owner_bots()  # noqa: SLF001 - internal helper reused
    if not bots:
        return {"text": "⚠️ Você ainda não possui bots para associar custos."}

    if len(bots) == 1:
        ConversationStateManager.set_state(
            user_id,
            "stats:awaiting_cost",
            {"scope": "bot", "bot_id": bots[0].id, "day": target_day, "mode": mode},
        )
        return {"text": f"💰 Informe o custo para *{bots[0].name}* (ex: `R$ 250,00`)."}

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": bot.name,
                    "callback_data": _encode(
                        user_id,
                        {
                            "scope": "stats",
                            "action": "cost_select",
                            "bot_id": bot.id,
                            "day": target_day,
                            "mode": mode,
                        },
                    ),
                }
            ]
            for bot in bots
        ]
    }
    return {"text": "Selecione o bot para aplicar o custo:", "keyboard": keyboard}


def _handle_cost_input(user_id: int, text: str, data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        cents = parse_brl_to_cents(text)
    except Exception:  # noqa: BLE001
        return {"text": "❌ Valor inválido. Use `R$ 1234,56`."}

    day = date.fromisoformat(data["day"])
    scope = data.get("scope", "general")
    bot_id = data.get("bot_id")
    CostRepository.add_cost(
        owner_id=user_id,
        scope=scope,
        day=day,
        amount_cents=cents,
        bot_id=bot_id,
    )

    ConversationStateManager.clear_state(user_id)
    mode = data.get("mode", "day")
    window = _extract_window(
        mode, {"day": data["day"], "start": data.get("start"), "end": data.get("end")}
    )
    service = _service(user_id)
    summary = service.load_summary(window)
    response = render_view(user_id, summary, "costs")
    response["text"] = "✅ Custo registrado!\n\n" + response["text"]
    _attach_chart(user_id, service, window, response)
    return response


def _decode_token(user_id: int, token: str) -> Dict[str, Any]:
    if token.startswith("stats:"):
        token = token.split(":", 1)[1]
    return decode_callback(user_id, token)


def _extract_window(mode: str, data: Dict[str, Any]) -> StatsWindow:
    if mode == "day":
        day_iso = data.get("day")
        day = date.fromisoformat(day_iso) if day_iso else date.today()
        return StatsWindow(mode=StatsWindowMode.DAY, day=day)
    start_iso = data.get("start") or data.get("day")
    end_iso = data.get("end") or start_iso
    start_day = date.fromisoformat(start_iso)
    end_day = date.fromisoformat(end_iso)
    return StatsWindow(
        mode=StatsWindowMode.RANGE, start_date=start_day, end_date=end_day
    )


def _window_from_dict(data: Optional[Dict[str, Any]]) -> StatsWindow:
    if not data:
        return StatsWindow(mode=StatsWindowMode.DAY, day=date.today())

    mode = data.get("mode", "day")
    if mode == "day":
        day_iso = data.get("day") or data.get("start")
        day = date.fromisoformat(day_iso) if day_iso else date.today()
        return StatsWindow(mode=StatsWindowMode.DAY, day=day)

    start_iso = data.get("start") or data.get("day") or date.today().isoformat()
    end_iso = data.get("end") or start_iso
    start_day = date.fromisoformat(start_iso)
    end_day = date.fromisoformat(end_iso)
    return StatsWindow(
        mode=StatsWindowMode.RANGE, start_date=start_day, end_date=end_day
    )


def _encode(user_id: int, data: Dict[str, Any]) -> str:
    return encode_callback(user_id, data)


def _ensure_rate_limit(user_id: int) -> bool:
    key = f"stats:rl:{user_id}"
    current = redis_client.incr(key)
    if current == 1:
        redis_client.expire(key, 30)
    return current <= 10


def _attach_chart(
    user_id: int,
    service: StatsService,
    window: StatsWindow,
    response: Dict[str, Any],
    *,
    force_refresh: bool = False,
) -> None:
    try:
        result = generate_sales_chart(service, window, force=force_refresh)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to generate stats chart",
            extra={"user_id": user_id, "error": str(exc)},
        )
        return

    if not result:
        return

    response["chart_path"] = str(result.path)
    response["chart_is_new"] = result.fresh
    response.setdefault(
        "chart_caption", response.get("text", "📊 Vendas (últimos 7 dias)")
    )


__all__ = [
    "handle_stats_menu",
    "handle_stats_callback",
    "handle_stats_text",
]
