"""Parsers e utilidades para agendamento de mensagens de recuperação."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from enum import Enum
from typing import Optional, Tuple

try:  # Python >=3.9
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - fallback para ambientes antigos
    from backports.zoneinfo import ZoneInfo  # type: ignore

DEFAULT_TZ = "UTC"


class ScheduleParseError(ValueError):
    """Erro lançado quando a expressão de agenda é inválida."""


class ScheduleType(str, Enum):
    """Tipos suportados de agendamento."""

    RELATIVE = "relative"
    NEXT_DAY_TIME = "next_day_time"
    PLUS_DAYS_TIME = "plus_days_time"


@dataclass(frozen=True)
class ScheduleDefinition:
    """Representa um agendamento estruturado."""

    type: ScheduleType
    seconds: Optional[int] = None
    time_of_day: Optional[time] = None
    days_offset: Optional[int] = None

    def __post_init__(self):  # validação defensiva
        if self.type is ScheduleType.RELATIVE and self.seconds is None:
            raise ValueError("Relative schedule requires seconds")
        if self.type is ScheduleType.NEXT_DAY_TIME and self.time_of_day is None:
            raise ValueError("Next-day schedule requires time_of_day")
        if self.type is ScheduleType.PLUS_DAYS_TIME:
            if self.time_of_day is None:
                raise ValueError("Plus-days schedule requires time_of_day")
            if self.days_offset is None:
                raise ValueError("Plus-days schedule requires days_offset")
            if self.days_offset < 0:
                raise ValueError("days_offset must be >= 0")


_RELATIVE_UNITS = {
    "s": 1,
    "seg": 1,
    "segundo": 1,
    "segundos": 1,
    "m": 60,
    "min": 60,
    "minuto": 60,
    "minutos": 60,
    "h": 3600,
    "hora": 3600,
    "horas": 3600,
    "d": 86400,
    "dia": 86400,
    "dias": 86400,
}

_RELATIVE_PATTERN = re.compile(
    r"^\+?(?P<value>\d+)(?P<unit>s|seg|segundo|segundos|m|min|minuto|minutos|h|hora|horas|d|dia|dias)$"
)
_NEXT_DAY_PATTERN = re.compile(r"^amanha(?:\s+(?:as)?)?\s*(?P<hour>\d{1,2}:\d{2})$")
_PLUS_DAY_PATTERN = re.compile(
    r"^\+(?P<days>\d{1,3})d(?:\s*(?:as)?)?\s*(?P<hour>\d{1,2}:\d{2})$"
)
_TIME_ONLY_PATTERN = re.compile(r"^(?P<hour>\d{1,2}:\d{2})$")


def _normalize_expression(expression: str) -> str:
    if not expression or not expression.strip():
        raise ScheduleParseError("Expressão vazia.")
    normalized = unicodedata.normalize("NFKD", expression.strip())
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    normalized = normalized.lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _parse_time(hour_fragment: str) -> time:
    hour, minute = hour_fragment.split(":", 1)
    hour_int = int(hour)
    minute_int = int(minute)
    if not (0 <= hour_int < 24 and 0 <= minute_int < 60):
        raise ScheduleParseError("Horário inválido. Use HH:MM entre 00:00 e 23:59.")
    return time(hour_int, minute_int)


def parse_schedule_expression(expression: str) -> ScheduleDefinition:
    """Converte string fornecida pelo admin em definição estruturada."""

    normalized = _normalize_expression(expression)

    if normalized in {"0", "agora", "imediato", "imediatamente"}:
        return ScheduleDefinition(ScheduleType.RELATIVE, seconds=0)

    compact = normalized.replace(" ", "")

    match = _RELATIVE_PATTERN.match(compact)
    if match:
        seconds = int(match.group("value")) * _RELATIVE_UNITS[match.group("unit")]
        return ScheduleDefinition(ScheduleType.RELATIVE, seconds=seconds)

    match = _NEXT_DAY_PATTERN.match(normalized)
    if match:
        return ScheduleDefinition(
            ScheduleType.NEXT_DAY_TIME, time_of_day=_parse_time(match.group("hour"))
        )

    match = _PLUS_DAY_PATTERN.match(compact)
    if match:
        days = int(match.group("days"))
        return ScheduleDefinition(
            ScheduleType.PLUS_DAYS_TIME,
            time_of_day=_parse_time(match.group("hour")),
            days_offset=days,
        )

    if normalized.startswith("+d"):
        raise ScheduleParseError(
            "Use formato +2d18:00 para definir dias e horário (ex.: +2d 18:00)."
        )

    match = _TIME_ONLY_PATTERN.match(normalized)
    if match:
        return ScheduleDefinition(
            ScheduleType.PLUS_DAYS_TIME,
            time_of_day=_parse_time(match.group("hour")),
            days_offset=0,
        )

    raise ScheduleParseError(
        "Formato inválido. Exemplos: 10m, 1h, 30 minutos, amanhã 12:00, +2d18:00."
    )


def encode_schedule(definition: ScheduleDefinition) -> Tuple[str, str]:
    """Serializa definição para persistência (type, value)."""

    if definition.type is ScheduleType.RELATIVE:
        return definition.type.value, str(definition.seconds)
    if definition.type is ScheduleType.NEXT_DAY_TIME:
        assert definition.time_of_day is not None
        return definition.type.value, definition.time_of_day.strftime("%H:%M")
    if definition.type is ScheduleType.PLUS_DAYS_TIME:
        assert definition.time_of_day is not None
        days = definition.days_offset or 0
        return (
            definition.type.value,
            f"{days}|{definition.time_of_day.strftime('%H:%M')}",
        )
    raise ScheduleParseError("Tipo de agenda desconhecido.")


def decode_schedule(schedule_type: str, schedule_value: str) -> ScheduleDefinition:
    """Reconstrói definição a partir dos valores salvos."""

    try:
        schedule_enum = ScheduleType(schedule_type)
    except ValueError as exc:  # pragma: no cover - proteção
        raise ScheduleParseError(f"Tipo de agenda inválido: {schedule_type}") from exc

    if schedule_enum is ScheduleType.RELATIVE:
        seconds = int(schedule_value)
        return ScheduleDefinition(schedule_enum, seconds=seconds)

    if schedule_enum is ScheduleType.NEXT_DAY_TIME:
        return ScheduleDefinition(
            schedule_enum, time_of_day=_parse_time(schedule_value)
        )

    if schedule_enum is ScheduleType.PLUS_DAYS_TIME:
        try:
            days_fragment, hour_fragment = schedule_value.split("|", 1)
        except ValueError as exc:
            raise ScheduleParseError(
                "Valor inválido para agenda +dias. Esperado N|HH:MM."
            ) from exc
        return ScheduleDefinition(
            schedule_enum,
            time_of_day=_parse_time(hour_fragment),
            days_offset=int(days_fragment),
        )

    raise ScheduleParseError(f"Tipo de agenda inválido: {schedule_type}")


def compute_next_occurrence(
    definition: ScheduleDefinition,
    *,
    base_time: datetime,
    timezone_name: Optional[str] = None,
) -> datetime:
    """Calcula próxima execução em UTC."""

    tz_name = timezone_name or DEFAULT_TZ
    try:
        tz = ZoneInfo(tz_name)
    except Exception as exc:  # pragma: no cover - proteção
        raise ScheduleParseError(f"Timezone inválido: {tz_name}") from exc

    if base_time.tzinfo is None:
        base_time = base_time.replace(tzinfo=timezone.utc)

    base_local = base_time.astimezone(tz)

    if definition.type is ScheduleType.RELATIVE:
        assert definition.seconds is not None
        target = base_time + timedelta(seconds=definition.seconds)
        return target.astimezone(timezone.utc)

    if definition.type is ScheduleType.NEXT_DAY_TIME:
        assert definition.time_of_day is not None
        next_date = (base_local + timedelta(days=1)).date()
        next_local = datetime.combine(next_date, definition.time_of_day, tz)
        return next_local.astimezone(timezone.utc)

    if definition.type is ScheduleType.PLUS_DAYS_TIME:
        assert definition.time_of_day is not None
        days = definition.days_offset or 0
        candidate_date = (base_local + timedelta(days=days)).date()
        next_local = datetime.combine(candidate_date, definition.time_of_day, tz)
        if next_local <= base_local:
            next_local = datetime.combine(
                candidate_date + timedelta(days=1), definition.time_of_day, tz
            )
        return next_local.astimezone(timezone.utc)

    raise ScheduleParseError("Tipo de agenda não suportado para cálculo.")


def _humanize_seconds(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} s"
    if seconds % 3600 == 0:
        hours = seconds // 3600
        return f"{hours} h" if hours > 1 else "1 h"
    if seconds % 60 == 0:
        minutes = seconds // 60
        return f"{minutes} min"
    minutes, secs = divmod(seconds, 60)
    return f"{minutes} min {secs} s"


def format_schedule_definition(definition: ScheduleDefinition) -> str:
    """Retorna string amigável para o admin."""

    if definition.type is ScheduleType.RELATIVE:
        assert definition.seconds is not None
        return _humanize_seconds(definition.seconds)

    if definition.type is ScheduleType.NEXT_DAY_TIME:
        assert definition.time_of_day is not None
        return f"amanhã {definition.time_of_day.strftime('%H:%M')}"

    if definition.type is ScheduleType.PLUS_DAYS_TIME:
        assert definition.time_of_day is not None
        days = definition.days_offset or 0
        prefix = "+0d" if days == 0 else f"+{days}d"
        return f"{prefix} {definition.time_of_day.strftime('%H:%M')}"

    return "—"
