"""
Clientes para APIs externas (Telegram, etc)
"""

from typing import Any, Dict, Optional

import httpx


class TelegramAPI:
    """Cliente para API do Telegram"""

    BASE_URL = "https://api.telegram.org/bot"

    async def get_me(self, token: str) -> Dict[str, Any]:
        """Obtém informações do bot"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.BASE_URL}{token}/getMe")
            response.raise_for_status()
            return response.json()["result"]

    async def set_webhook(
        self,
        token: str,
        url: str,
        secret_token: str,
        allowed_updates: list,
        drop_pending_updates: bool = True,
    ) -> Dict[str, Any]:
        """Configura webhook do bot"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}{token}/setWebhook",
                json={
                    "url": url,
                    "secret_token": secret_token,
                    "allowed_updates": allowed_updates,
                    "drop_pending_updates": drop_pending_updates,
                },
            )
            response.raise_for_status()
            return response.json()

    def send_message_sync(
        self, token: str, chat_id: int, text: str, keyboard: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Envia mensagem (versão síncrona para workers)"""
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        if keyboard:
            payload["reply_markup"] = keyboard

        with httpx.Client() as client:
            response = client.post(f"{self.BASE_URL}{token}/sendMessage", json=payload)
            response.raise_for_status()
            return response.json()

    async def send_message(self, token: str, chat_id: int, text: str) -> Dict[str, Any]:
        """Envia mensagem (versão assíncrona)"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}{token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
            response.raise_for_status()
            return response.json()

    async def delete_message(self, token: str, chat_id: int, message_id: int) -> bool:
        """Deleta mensagem"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}{token}/deleteMessage",
                json={"chat_id": chat_id, "message_id": message_id},
            )
            response.raise_for_status()
            return response.json()["result"]

    def answer_callback_query_sync(
        self, token: str, callback_query_id: str, text: str = ""
    ) -> Dict[str, Any]:
        """Responde callback query (versão síncrona)"""
        with httpx.Client() as client:
            response = client.post(
                f"{self.BASE_URL}{token}/answerCallbackQuery",
                json={"callback_query_id": callback_query_id, "text": text},
            )
            response.raise_for_status()
            return response.json()

    def edit_message_sync(
        self,
        token: str,
        chat_id: int,
        message_id: int,
        text: str,
        keyboard: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Edita mensagem (versão síncrona)"""
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "Markdown",
        }
        if keyboard:
            payload["reply_markup"] = keyboard

        with httpx.Client() as client:
            response = client.post(
                f"{self.BASE_URL}{token}/editMessageText", json=payload
            )
            response.raise_for_status()
            return response.json()
