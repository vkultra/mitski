"""Tests for statistics callback storage."""

from services.stats import callbacks


def test_encode_decode_callback(monkeypatch, fake_redis):
    monkeypatch.setattr(callbacks, "redis_client", fake_redis)

    user_id = 123
    payload = {"scope": "stats", "action": "navigate", "view": "summary"}

    token = callbacks.encode_callback(user_id, payload)
    assert token.startswith("stats:")

    raw_token = token.split(":", 1)[1]
    decoded = callbacks.decode_callback(user_id, raw_token)
    assert decoded == payload

    # Token is single-use
    try:
        callbacks.decode_callback(user_id, raw_token)
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("token reuse was allowed")
