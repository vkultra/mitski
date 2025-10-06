from handlers.recovery.callbacks import build_callback, parse_callback


def test_callback_roundtrip():
    callback = build_callback("step_view", step_id=123, extra="value")
    action, payload = parse_callback(callback)
    assert action == "step_view"
    assert payload["step_id"] == 123
    assert payload["extra"] == "value"


def test_invalid_prefix():
    try:
        parse_callback("invalid:token")
    except ValueError as exc:
        assert "invalid_prefix" in str(exc)
    else:
        raise AssertionError("expected ValueError")
