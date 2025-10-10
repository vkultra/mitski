from core.token_costs import (
    TextUsage,
    apply_conservative_pad,
    estimate_completion_tokens,
    estimate_tokens_from_chars,
    text_cost_brl_cents,
    whisper_cost_brl_cents,
)


def test_chars_to_tokens_and_pad():
    t = estimate_tokens_from_chars(400)
    assert 80 <= t <= 500  # coarse check
    assert apply_conservative_pad(t) >= t


def test_completion_estimator_bounds():
    assert estimate_completion_tokens(0, 1000) == 300
    assert estimate_completion_tokens(50, 1000) == 64  # min clamp
    assert estimate_completion_tokens(2000, 1000) == 1000  # max clamp


def test_text_cost_and_whisper_cost():
    # 1k prompt, 2k completion, 0 cached -> small cents value (>0)
    usage = TextUsage(prompt_tokens=1000, completion_tokens=2000)
    cents = text_cost_brl_cents(usage)
    assert isinstance(cents, int) and cents >= 0

    # 2 minutes of audio
    wcents = whisper_cost_brl_cents(2.0)
    assert isinstance(wcents, int) and wcents >= 0
