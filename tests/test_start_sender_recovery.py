from types import SimpleNamespace
from typing import Any, Dict

import httpx
import pytest

from database.repos import MediaFileCacheRepository
from services.start.start_sender import StartTemplateSenderService


def _http_error(status: int, description: str) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.telegram.org")
    response = httpx.Response(
        status,
        request=request,
        json={"ok": False, "description": description, "error_code": status},
    )
    return httpx.HTTPStatusError("telegram error", request=request, response=response)


@pytest.mark.asyncio
async def test_media_retry_with_force_stream(monkeypatch):
    service = StartTemplateSenderService("TOKEN")
    block = SimpleNamespace(media_file_id="orig-id", media_type="photo", id=7)

    async def fake_get_or_send_media(*_args, **_kwargs) -> tuple[str, Dict[str, Any]]:
        return "new-id", {
            "result": {"message_id": 91, "photo": [{"file_id": "new-id"}]}
        }

    async def fake_clear_cache(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        StartTemplateSenderService,
        "_get_or_send_media",
        fake_get_or_send_media,
    )
    monkeypatch.setattr(
        MediaFileCacheRepository,
        "clear_cached_file_id",
        fake_clear_cache,
    )

    exc = _http_error(400, "Bad Request: wrong file identifier")
    file_id, result, parse_mode = await service._handle_media_send_failure(
        exc=exc,
        block=block,
        bot_id=1,
        chat_id=1,
        caption="",
        cache_media=True,
        current_file_id="cached-id",
        media_type="photo",
        parse_mode=StartTemplateSenderService.DEFAULT_PARSE_MODE,
    )

    assert file_id == "new-id"
    assert result["result"]["message_id"] == 91
    assert parse_mode == StartTemplateSenderService.DEFAULT_PARSE_MODE


@pytest.mark.asyncio
async def test_media_retry_disables_markdown(monkeypatch):
    service = StartTemplateSenderService("TOKEN")
    block = SimpleNamespace(media_file_id="orig-id", media_type="photo", id=9)

    async def fake_clear_cache(*_args, **_kwargs):
        return None

    async def fake_send_media_message(*_args, **_kwargs):
        return {"result": {"message_id": 42, "photo": [{"file_id": "cached-id"}]}}

    monkeypatch.setattr(
        MediaFileCacheRepository,
        "clear_cached_file_id",
        fake_clear_cache,
    )
    monkeypatch.setattr(
        StartTemplateSenderService,
        "_send_media_message",
        fake_send_media_message,
    )

    exc = _http_error(400, "Bad Request: can't parse entities: Unsupported start tag")
    file_id, result, parse_mode = await service._handle_media_send_failure(
        exc=exc,
        block=block,
        bot_id=1,
        chat_id=1,
        caption="test",
        cache_media=False,
        current_file_id="cached-id",
        media_type="photo",
        parse_mode=StartTemplateSenderService.DEFAULT_PARSE_MODE,
    )

    assert file_id == "cached-id"
    assert result["result"]["message_id"] == 42
    assert parse_mode is None
