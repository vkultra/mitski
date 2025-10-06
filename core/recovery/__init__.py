"""Componentes core para a feature de recuperação."""

from .schedule import (
    ScheduleDefinition,
    ScheduleParseError,
    ScheduleType,
    compute_next_occurrence,
    decode_schedule,
    encode_schedule,
    format_schedule_definition,
    parse_schedule_expression,
)
from .state import (
    allocate_episode,
    clear_episode,
    current_episode,
    generate_episode_id,
    get_campaign_version,
    get_inactivity_version,
    get_last_activity,
    mark_user_activity,
    remember_campaign_version,
    try_allocate_episode,
)

__all__ = [
    "ScheduleDefinition",
    "ScheduleParseError",
    "ScheduleType",
    "compute_next_occurrence",
    "decode_schedule",
    "encode_schedule",
    "format_schedule_definition",
    "parse_schedule_expression",
    "allocate_episode",
    "clear_episode",
    "current_episode",
    "generate_episode_id",
    "get_campaign_version",
    "get_inactivity_version",
    "get_last_activity",
    "mark_user_activity",
    "remember_campaign_version",
    "try_allocate_episode",
]
