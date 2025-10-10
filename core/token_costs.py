"""
Helpers for pricing, currency conversion and token usage estimation.

All monetary values are handled in BRL (centavos as integers) externally.
Prices are configured in USD per 1M tokens for text, and USD per minute for
audio, then converted to BRL using a fixed exchange rate from env.

This module purposely stays small (<280 lines) and dependency‑free.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from core.config import settings

USD_MULT = 100_0000  # helper only for clarity (not used in math below)


def usd_to_brl_cents(usd_amount: float) -> int:
    """Converts USD float to BRL cents using fixed env rate.

    Rounds to nearest centavo.
    """
    rate = float(getattr(settings, "USD_TO_BRL_RATE", 5.80) or 5.80)
    brl = usd_amount * rate
    return int(round(brl * 100))


@dataclass
class TextUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return (
            int(self.prompt_tokens)
            + int(self.completion_tokens)
            + int(self.reasoning_tokens)
        )


def price_table_usd_per_mtok() -> Dict[str, float]:
    """Returns USD prices per 1M tokens for text usage.

    Values come from env and default to the ones defined in AGENTS.md.
    """
    return {
        "input": float(getattr(settings, "PRICE_TEXT_INPUT_PER_MTOK_USD", 0.20)),
        "output": float(getattr(settings, "PRICE_TEXT_OUTPUT_PER_MTOK_USD", 0.50)),
        "cached": float(getattr(settings, "PRICE_TEXT_CACHED_PER_MTOK_USD", 0.05)),
    }


def whisper_cost_brl_cents(minutes: float) -> int:
    """Returns BRL cents for Whisper usage given minutes.

    Uses env WHISPER_COST_PER_MINUTE_USD and USD_TO_BRL_RATE.
    """
    usd_per_min = float(getattr(settings, "WHISPER_COST_PER_MINUTE_USD", 0.006))
    usd_cost = usd_per_min * max(0.0, float(minutes))
    return usd_to_brl_cents(usd_cost)


def text_cost_brl_cents(usage: TextUsage) -> int:
    """Converts text usage (tokens) to BRL cents using env price table.

    Pricing is per 1M tokens. Cached tokens are billed with distinct price.
    Reasoning tokens are included in completion tokens pricing (output).
    """
    prices = price_table_usd_per_mtok()

    input_usd = (usage.prompt_tokens / 1_000_000.0) * prices["input"]
    output_usd = (
        (usage.completion_tokens + usage.reasoning_tokens) / 1_000_000.0
    ) * prices["output"]
    cached_usd = (usage.cached_tokens / 1_000_000.0) * prices["cached"]

    total_usd = input_usd + output_usd + cached_usd
    return usd_to_brl_cents(total_usd)


def estimate_tokens_from_chars(char_count: int) -> int:
    """Roughly estimates tokens from character count.

    Rule of thumb: ~4 characters per token for PT‑BR; configurable via env
    ESTIMATED_CHARS_PER_TOKEN (default 4.0). Clamped to >= 1.
    """
    cpt = float(getattr(settings, "ESTIMATED_CHARS_PER_TOKEN", 4.0) or 4.0)
    cpt = max(1.0, cpt)
    return int(round(max(0, int(char_count)) / cpt))


def estimate_completion_tokens(history_avg: Optional[int], max_tokens: int) -> int:
    """Estimates completion tokens using moving average with caps.

    If history_avg is provided, clamp to [64, max_tokens]. Otherwise, fallback
    to min(300, max_tokens).
    """
    if history_avg and history_avg > 0:
        return max(64, min(int(history_avg), int(max_tokens)))
    return min(300, int(max_tokens))


def apply_conservative_pad(tokens: int, pad_ratio: float = 0.25) -> int:
    """Applies a conservative pad (default 25%) for pre‑checks."""
    return int(round(tokens * (1.0 + float(pad_ratio))))


async def estimate_prompt_tokens_with_tokenize(text: str, tokenizer_call) -> int:
    """Uses provider tokenization if available; falls back to char‑based.

    Args:
        text: concatenated prompt text to tokenize
        tokenizer_call: awaitable that receives `text` and returns token count
    """
    try:
        count = await tokenizer_call(text)
        if isinstance(count, int) and count >= 0:
            return count
    except Exception:
        pass
    return estimate_tokens_from_chars(len(text or ""))


__all__ = [
    "TextUsage",
    "usd_to_brl_cents",
    "text_cost_brl_cents",
    "whisper_cost_brl_cents",
    "estimate_tokens_from_chars",
    "estimate_completion_tokens",
    "apply_conservative_pad",
    "estimate_prompt_tokens_with_tokenize",
]
