"""Cliente especializado para envio e validação de notificações."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import httpx

from core.telemetry import logger


class TelegramNotificationClient:
    """Cliente enxuto da API do Telegram voltado para notificações."""

    BASE_URL = "https://api.telegram.org/bot"

    def __init__(self, token: str, *, timeout: float = 20.0, max_retries: int = 3):
        self.token = token
        self.timeout = timeout
        self.max_retries = max_retries

    def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True,
    ) -> Dict[str, Any]:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
        }
        return self._post("sendMessage", payload)

    def get_chat(self, chat_id: int | str) -> Dict[str, Any]:
        return self._post("getChat", {"chat_id": chat_id})

    def _post(self, method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.BASE_URL}{self.token}/{method}"
        backoff = 1.0

        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(url, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    if not data.get("ok", False):
                        raise httpx.HTTPStatusError(
                            f"Telegram API error: {data}", request=response.request, response=response
                        )
                    return data["result"]
            except httpx.HTTPStatusError as exc:  # Algo retornou erro
                status = exc.response.status_code if exc.response else "n/a"
                if status == 429 and attempt < self.max_retries:
                    retry_after = exc.response.json().get("parameters", {}).get("retry_after", backoff)
                    time.sleep(float(retry_after))
                    backoff *= 2
                    continue
                if status in {500, 502, 503, 504} and attempt < self.max_retries:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                logger.error(
                    "Telegram API call failed",
                    extra={
                        "method": method,
                        "status": status,
                        "error": str(exc),
                        "payload": {k: v for k, v in payload.items() if k != "text"},
                    },
                )
                raise
            except (httpx.ConnectError, httpx.ReadTimeout) as exc:
                if attempt < self.max_retries:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                logger.error(
                    "Telegram request failed",
                    extra={"method": method, "error": str(exc)},
                )
                raise

        raise RuntimeError("Unable to reach Telegram API after retries")


__all__ = ["TelegramNotificationClient"]
