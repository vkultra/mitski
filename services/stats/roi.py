"""ROI and cost allocation helpers."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Dict


def compute_roi(gross_cents: int, cost_cents: int) -> float | None:
    if cost_cents <= 0:
        return None
    return (gross_cents - cost_cents) / cost_cents


def allocate_general_costs(
    total_general_cents: int,
    gross_by_bot: Dict[int, int],
) -> Dict[int, int]:
    if total_general_cents <= 0 or not gross_by_bot:
        return {bot_id: 0 for bot_id in gross_by_bot}

    total_gross = sum(max(value, 0) for value in gross_by_bot.values())
    if total_gross <= 0:
        count = len(gross_by_bot)
        if count == 0:
            return {bot_id: 0 for bot_id in gross_by_bot}
        base = total_general_cents // count
        remainder = total_general_cents % count
        allocations = {}
        for idx, (bot_id, _) in enumerate(sorted(gross_by_bot.items())):
            allocations[bot_id] = base + (1 if idx < remainder else 0)
        return allocations

    allocations: Dict[int, int] = {}
    distributed = 0
    ordered = sorted(gross_by_bot.items(), key=lambda item: item[1], reverse=True)
    total_decimal = Decimal(total_general_cents)

    for bot_id, gross in ordered:
        share = Decimal(max(gross, 0)) / Decimal(total_gross)
        cents = int(
            (total_decimal * share).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
        allocations[bot_id] = cents
        distributed += cents

    difference = total_general_cents - distributed
    idx = 0
    length = len(ordered)
    while difference != 0 and length:
        bot_id, _ = ordered[idx]
        if difference > 0:
            allocations[bot_id] += 1
            difference -= 1
        elif allocations[bot_id] > 0:
            allocations[bot_id] -= 1
            difference += 1
        idx = (idx + 1) % length

    return allocations


__all__ = ["compute_roi", "allocate_general_costs"]
