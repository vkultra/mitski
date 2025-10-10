from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.files import (
    TxtFileError,
    build_preview,
    download_txt_document,
    make_txt_stream,
)


def test_make_txt_stream_creates_named_stream():
    stream = make_txt_stream("example.txt", "hello")
    assert stream.read() == b"hello"
    assert stream.name == "example.txt"


def test_build_preview_handles_empty():
    assert build_preview("") == "--"


def test_build_preview_truncates_long_text():
    text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit."
    preview = build_preview(text, max_chars=20)
    assert preview.endswith("...")
    assert len(preview) <= 23


@pytest.mark.asyncio
async def test_download_txt_document_success():
    document = {"file_id": "123", "file_name": "prompt.txt", "file_size": 10}

    info_response = MagicMock()
    info_response.status_code = 200
    info_response.json.return_value = {
        "ok": True,
        "result": {"file_path": "documents/prompt.txt", "file_size": 10},
    }

    download_response = MagicMock()
    download_response.status_code = 200
    download_response.content = b"hello"

    client_enter = MagicMock()
    client_enter.get = AsyncMock(side_effect=[info_response, download_response])

    client_mock = MagicMock()
    client_mock.__aenter__ = AsyncMock(return_value=client_enter)
    client_mock.__aexit__ = AsyncMock(return_value=None)

    with patch("services.files.txt_utils.httpx.AsyncClient", return_value=client_mock):
        text = await download_txt_document("token", document)

    assert text == "hello"


@pytest.mark.asyncio
async def test_download_txt_document_rejects_non_txt():
    document = {"file_id": "123", "file_name": "data.json"}

    with pytest.raises(TxtFileError):
        await download_txt_document("token", document)


@pytest.mark.asyncio
async def test_download_txt_document_checks_size_limit():
    document = {
        "file_id": "123",
        "file_name": "prompt.txt",
        "file_size": 100000,
    }

    with pytest.raises(TxtFileError):
        await download_txt_document("token", document)
