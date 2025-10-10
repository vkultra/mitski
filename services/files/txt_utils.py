"""Utilities for reading and writing prompt .txt files."""

from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, Optional

import httpx

from core.telemetry import logger

MAX_TXT_BYTES = 64 * 1024  # 64 KB safety limit


class TxtFileError(Exception):
    """Raised when a .txt file cannot be processed."""


def make_txt_stream(filename: str, content: str) -> BytesIO:
    """Return a BytesIO ready to be uploaded as a .txt document."""
    stream = BytesIO(content.encode("utf-8"))
    stream.name = filename
    stream.seek(0)
    return stream


def _is_txt_document(document: Dict[str, Any]) -> bool:
    file_name = (document.get("file_name") or "").lower()
    mime_type = (document.get("mime_type") or "").lower()
    return file_name.endswith(".txt") or mime_type == "text/plain"


def _validate_document(document: Dict[str, Any]):
    if not _is_txt_document(document):
        raise TxtFileError("Envie um arquivo .txt (texto puro).")

    size = int(document.get("file_size") or 0)
    if size and size > MAX_TXT_BYTES:
        raise TxtFileError("Arquivo .txt muito grande (limite de 64 KB).")


def _decode_content(content: bytes) -> str:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except UnicodeDecodeError as exc:
            raise TxtFileError("Não foi possível decodificar o arquivo .txt.") from exc
    return text


async def download_txt_document(token: str, document: Dict[str, Any]) -> str:
    """Download a Telegram document and return its textual content."""
    _validate_document(document)

    file_id = document.get("file_id")
    if not file_id:
        raise TxtFileError("Arquivo inválido: faltando file_id.")

    async with httpx.AsyncClient(timeout=30.0) as client:
        info_response = await client.get(
            f"https://api.telegram.org/bot{token}/getFile",
            params={"file_id": file_id},
        )
        info_response.raise_for_status()
        info_payload = info_response.json()

        if not info_payload.get("ok"):
            logger.warning(
                "getFile failed",
                extra={"file_id": file_id, "payload": info_payload},
            )
            raise TxtFileError("Falha ao acessar o arquivo no Telegram.")

        result = info_payload.get("result") or {}
        file_path = result.get("file_path")
        file_size = int(result.get("file_size") or 0)

        if not file_path:
            raise TxtFileError("Telegram não retornou o caminho do arquivo.")

        if file_size and file_size > MAX_TXT_BYTES:
            raise TxtFileError("Arquivo .txt muito grande (limite de 64 KB).")

        download_response = await client.get(
            f"https://api.telegram.org/file/bot{token}/{file_path}"
        )
        download_response.raise_for_status()
        content = download_response.content

    if len(content) > MAX_TXT_BYTES:
        raise TxtFileError("Arquivo .txt muito grande (limite de 64 KB).")

    return _decode_content(content)


def build_preview(text: Optional[str], max_chars: int = 80) -> str:
    """Return a short preview for menu rendering."""
    if not text:
        return "--"

    candidate = text.strip()
    if len(candidate) <= max_chars:
        return candidate

    truncated = candidate[: max_chars + 1].rsplit(" ", 1)[0]
    if not truncated:
        truncated = candidate[:max_chars]
    return f"{truncated.strip()}..."
