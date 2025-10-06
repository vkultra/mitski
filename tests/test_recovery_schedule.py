from datetime import datetime, timedelta, timezone

import pytest

from core.recovery import (
    ScheduleType,
    compute_next_occurrence,
    decode_schedule,
    encode_schedule,
    format_schedule_definition,
    parse_schedule_expression,
)


@pytest.mark.parametrize(
    "expression, expected_seconds",
    [
        ("10m", 600),
        (" 15 minutos ", 900),
        ("1h", 3600),
        ("30 min", 1800),
    ],
)
def test_parse_relative(expression, expected_seconds):
    definition = parse_schedule_expression(expression)
    assert definition.type is ScheduleType.RELATIVE
    assert definition.seconds == expected_seconds


def test_parse_next_day():
    definition = parse_schedule_expression("amanhã 12:30")
    assert definition.type is ScheduleType.NEXT_DAY_TIME
    assert definition.time_of_day.hour == 12
    assert definition.time_of_day.minute == 30


@pytest.mark.parametrize(
    "expression, days, hour, minute",
    [
        ("+2d18:00", 2, 18, 0),
        ("+0d07:15", 0, 7, 15),
    ],
)
def test_parse_plus_days(expression, days, hour, minute):
    definition = parse_schedule_expression(expression)
    assert definition.type is ScheduleType.PLUS_DAYS_TIME
    assert definition.days_offset == days
    assert definition.time_of_day.hour == hour
    assert definition.time_of_day.minute == minute


def test_encode_decode_roundtrip():
    original = parse_schedule_expression("10m")
    schedule_type, schedule_value = encode_schedule(original)
    restored = decode_schedule(schedule_type, schedule_value)
    assert restored.type is ScheduleType.RELATIVE
    assert restored.seconds == 600


def test_compute_relative_next_occurrence():
    base = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    definition = parse_schedule_expression("5m")
    next_run = compute_next_occurrence(definition, base_time=base, timezone_name="UTC")
    assert next_run == base + timedelta(minutes=5)


def test_compute_next_day_occurrence():
    base = datetime(2025, 1, 1, 22, 0, tzinfo=timezone.utc)
    definition = parse_schedule_expression("amanhã 08:00")
    next_run = compute_next_occurrence(definition, base_time=base, timezone_name="UTC")
    assert next_run == datetime(2025, 1, 2, 8, 0, tzinfo=timezone.utc)


def test_format_definition():
    definition = parse_schedule_expression("30m")
    assert format_schedule_definition(definition) == "30 min"

    definition = parse_schedule_expression("amanhã 09:00")
    assert format_schedule_definition(definition) == "amanhã 09:00"

    definition = parse_schedule_expression("+2d18:00")
    assert format_schedule_definition(definition) == "+2d 18:00"
