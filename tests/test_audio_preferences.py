"""Testes para AudioPreferencesService"""

from types import SimpleNamespace

import pytest

from services.audio import (
    AudioPreferenceError,
    AudioPreferenceMode,
    AudioPreferencesService,
)


def test_get_preferences_uses_cache(monkeypatch, mock_redis_client):
    mock_redis_client.flushdb()
    monkeypatch.setattr(
        "services.audio.preferences_service.redis_client", mock_redis_client
    )

    calls = {"count": 0}

    def fake_get_or_create(admin_id):
        calls["count"] += 1
        return SimpleNamespace(mode="whisper", default_reply="Olá")

    monkeypatch.setattr(
        "database.audio_preferences_repo.AudioPreferencesRepository.get_or_create",
        fake_get_or_create,
    )

    prefs = AudioPreferencesService.get_preferences(101)
    assert prefs == {"mode": "whisper", "default_reply": "Olá"}
    assert calls["count"] == 1

    # Segunda chamada deve vir do cache, sem acessar o repositório
    prefs_again = AudioPreferencesService.get_preferences(101)
    assert prefs_again == prefs
    assert calls["count"] == 1


def test_set_mode_updates_cache(monkeypatch, mock_redis_client):
    mock_redis_client.flushdb()
    monkeypatch.setattr(
        "services.audio.preferences_service.redis_client", mock_redis_client
    )

    def fake_update_mode(admin_id, mode):
        return SimpleNamespace(mode=mode, default_reply="Olá")

    monkeypatch.setattr(
        "database.audio_preferences_repo.AudioPreferencesRepository.update_mode",
        fake_update_mode,
    )

    updated = AudioPreferencesService.set_mode(55, AudioPreferenceMode.WHISPER)
    assert updated["mode"] == "whisper"
    assert updated["default_reply"] == "Olá"

    # Cache deve refletir o novo valor
    cached = AudioPreferencesService.get_preferences(55)
    assert cached["mode"] == "whisper"


def test_set_default_reply_validates_input(monkeypatch, mock_redis_client):
    mock_redis_client.flushdb()
    monkeypatch.setattr(
        "services.audio.preferences_service.redis_client", mock_redis_client
    )

    with pytest.raises(AudioPreferenceError):
        AudioPreferencesService.set_default_reply(1, "   ")

    long_text = "a" * 901
    with pytest.raises(AudioPreferenceError):
        AudioPreferencesService.set_default_reply(1, long_text)

    def fake_update_default(admin_id, reply):
        return SimpleNamespace(mode="whisper", default_reply=reply)

    monkeypatch.setattr(
        "database.audio_preferences_repo.AudioPreferencesRepository.update_default_reply",
        fake_update_default,
    )

    result = AudioPreferencesService.set_default_reply(1, "Texto válido")
    assert result["default_reply"] == "Texto válido"
