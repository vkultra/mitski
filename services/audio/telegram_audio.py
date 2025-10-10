"""Utilitário para download de áudios/vozes do Telegram."""

from __future__ import annotations

from typing import Any, Dict

import httpx

from core.telemetry import logger

GET_FILE_ENDPOINT = "https://api.telegram.org/bot{token}/getFile"
DOWNLOAD_ENDPOINT = "https://api.telegram.org/file/bot{token}/{path}"
HTTP_TIMEOUT = 15.0


class TelegramAudioService:
    """Download seguro de arquivos de áudio/voz do Telegram"""

    def __init__(self, bot_token: str) -> None:
        self.bot_token = bot_token

    def fetch(self, file_id: str) -> bytes:
        """Baixa bytes do arquivo associado ao file_id"""
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            file_info = self._get_file_info(client, file_id)
            file_path = file_info.get("file_path")
            if not file_path:
                raise RuntimeError("file_path ausente na resposta do Telegram")

            response: httpx.Response = client.get(
                DOWNLOAD_ENDPOINT.format(token=self.bot_token, path=file_path)
            )
            response.raise_for_status()
            content: bytes = response.content
            logger.info(
                "Telegram audio downloaded",
                extra={
                    "file_id": file_id,
                    "size_bytes": len(content),
                    "file_path_tail": file_path[-32:],
                },
            )
            return content

    def _get_file_info(self, client: httpx.Client, file_id: str) -> Dict[str, Any]:
        response: httpx.Response = client.get(
            GET_FILE_ENDPOINT.format(token=self.bot_token), params={"file_id": file_id}
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not payload.get("ok"):
            raise RuntimeError(f"Falha ao buscar file info: {payload}")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("Resposta inválida ao buscar file info")
        return result
