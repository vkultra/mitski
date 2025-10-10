"""Tests ensuring manager callbacks deliver chart images when available."""

from pathlib import Path

import pytest

pytest.importorskip("matplotlib")


class DummyTelegramAPI:
    """Collects calls performed by the worker during tests."""

    def __init__(self) -> None:
        self.edits = []
        self.media_edits = []

    def answer_callback_query_sync(
        self, token: str, callback_query_id: str
    ) -> None:  # noqa: D401
        return None

    def edit_message_sync(
        self, token: str, chat_id: int, message_id: int, text: str, keyboard=None
    ):  # noqa: D401
        self.edits.append(
            {
                "token": token,
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "keyboard": keyboard,
            }
        )
        return True

    def edit_message_media_sync(
        self,
        token: str,
        chat_id: int,
        message_id: int,
        photo_path: str,
        caption=None,
        keyboard=None,
    ):  # noqa: D401
        self.media_edits.append(
            {
                "token": token,
                "chat_id": chat_id,
                "message_id": message_id,
                "photo_path": photo_path,
                "caption": caption,
                "keyboard": keyboard,
            }
        )
        return {"message_id": message_id}


def _stats_response(chart_path: Path, *, fresh: bool) -> dict:
    return {
        "text": "Summary",
        "keyboard": {"inline_keyboard": []},
        "chart_path": str(chart_path),
        "chart_is_new": fresh,
        "chart_caption": "📊 Vendas (últimos 7 dias)",
    }


def _build_update() -> dict:
    return {
        "callback_query": {
            "id": "cb123",
            "from": {"id": 321},
            "message": {"chat": {"id": 321}, "message_id": 567},
            "data": "stats:token",
        }
    }


@pytest.fixture
def dummy_api(monkeypatch):
    api = DummyTelegramAPI()
    monkeypatch.setattr("workers.api_clients.TelegramAPI", lambda: api)
    return api


def test_manager_callback_sends_chart(tmp_path, monkeypatch, dummy_api):
    chart_path = tmp_path / "chart.png"
    chart_path.write_bytes(b"fake")

    async def fake_callback(user_id: int, token: str):
        return _stats_response(chart_path, fresh=True)

    monkeypatch.setattr("handlers.stats_handlers.handle_stats_callback", fake_callback)
    monkeypatch.setenv("MANAGER_BOT_TOKEN", "123:ABC")

    from workers.tasks import process_manager_update

    process_manager_update.run(_build_update())

    assert len(dummy_api.edits) == 1
    assert len(dummy_api.media_edits) == 1
    assert dummy_api.media_edits[0]["photo_path"] == str(chart_path)
    assert (
        dummy_api.media_edits[0]["caption"]
        == _stats_response(chart_path, fresh=True)["chart_caption"]
    )


def test_manager_callback_skips_cached_chart(tmp_path, monkeypatch, dummy_api):
    chart_path = tmp_path / "chart.png"
    chart_path.write_bytes(b"fake")

    async def fake_callback(user_id: int, token: str):
        return _stats_response(chart_path, fresh=False)

    monkeypatch.setattr("handlers.stats_handlers.handle_stats_callback", fake_callback)
    monkeypatch.setenv("MANAGER_BOT_TOKEN", "123:ABC")

    from workers.tasks import process_manager_update

    process_manager_update.run(_build_update())

    assert len(dummy_api.edits) == 1
    assert len(dummy_api.media_edits) == 1
