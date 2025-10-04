"""
Clientes para APIs externas (Telegram, etc)
"""

import json
import time
from typing import Any, Dict, Optional

import httpx


class TelegramAPI:
    """Cliente para API do Telegram"""

    BASE_URL = "https://api.telegram.org/bot"

    async def get_me(self, token: str) -> Dict[str, Any]:
        """Obtém informações do bot"""
        async with httpx.AsyncClient(timeout=30.0) as client:
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
        async with httpx.AsyncClient(timeout=30.0) as client:
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

        max_retries = 3
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=30.0) as client:
                    response = client.post(
                        f"{self.BASE_URL}{token}/sendMessage", json=payload
                    )
                    response.raise_for_status()
                    return response.json()
            except (httpx.ConnectError, httpx.ReadTimeout) as e:
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)  # Exponential backoff: 1s, 2s, 4s
                    continue
                raise

    async def send_message(
        self,
        token: str,
        chat_id: int,
        text: str,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Envia mensagem (versão assíncrona)"""
        payload = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = reply_markup

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.BASE_URL}{token}/sendMessage",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def delete_message(self, token: str, chat_id: int, message_id: int) -> bool:
        """Deleta mensagem"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.BASE_URL}{token}/deleteMessage",
                json={"chat_id": chat_id, "message_id": message_id},
            )
            response.raise_for_status()
            return response.json()["result"]

    async def send_photo(
        self,
        token: str,
        chat_id: int,
        photo,  # Can be str (file_id) or BytesIO (stream)
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Envia foto"""
        from io import BytesIO

        # Check if photo is a BytesIO stream
        if isinstance(photo, BytesIO):
            # Use multipart/form-data for file upload
            data = {"chat_id": str(chat_id)}
            if caption:
                data["caption"] = caption
            if parse_mode:
                data["parse_mode"] = parse_mode
            if reply_markup:
                data["reply_markup"] = json.dumps(reply_markup)

            # Get filename from stream or use default
            filename = getattr(photo, "name", "photo.jpg")
            files = {"photo": (filename, photo, "image/jpeg")}

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}{token}/sendPhoto",
                    data=data,
                    files=files,
                )
                response.raise_for_status()
                return response.json()
        else:
            # Use JSON for file_id
            payload = {"chat_id": chat_id, "photo": photo}
            if caption:
                payload["caption"] = caption
            if parse_mode:
                payload["parse_mode"] = parse_mode
            if reply_markup:
                payload["reply_markup"] = reply_markup

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}{token}/sendPhoto",
                    json=payload,
                )
                response.raise_for_status()
                return response.json()

    async def send_video(
        self,
        token: str,
        chat_id: int,
        video,  # Can be str (file_id) or BytesIO (stream)
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Envia vídeo"""
        from io import BytesIO

        # Check if video is a BytesIO stream
        if isinstance(video, BytesIO):
            # Use multipart/form-data for file upload
            data = {"chat_id": str(chat_id)}
            if caption:
                data["caption"] = caption
            if parse_mode:
                data["parse_mode"] = parse_mode
            if reply_markup:
                data["reply_markup"] = json.dumps(reply_markup)

            # Get filename from stream or use default
            filename = getattr(video, "name", "video.mp4")
            files = {"video": (filename, video, "video/mp4")}

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}{token}/sendVideo",
                    data=data,
                    files=files,
                )
                response.raise_for_status()
                return response.json()
        else:
            # Use JSON for file_id
            payload = {"chat_id": chat_id, "video": video}
            if caption:
                payload["caption"] = caption
            if parse_mode:
                payload["parse_mode"] = parse_mode
            if reply_markup:
                payload["reply_markup"] = reply_markup

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}{token}/sendVideo",
                    json=payload,
                )
                response.raise_for_status()
                return response.json()

    async def send_document(
        self,
        token: str,
        chat_id: int,
        document,  # Can be str (file_id) or BytesIO (stream)
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Envia documento"""
        from io import BytesIO

        # Check if document is a BytesIO stream
        if isinstance(document, BytesIO):
            # Use multipart/form-data for file upload
            data = {"chat_id": str(chat_id)}
            if caption:
                data["caption"] = caption
            if parse_mode:
                data["parse_mode"] = parse_mode
            if reply_markup:
                data["reply_markup"] = json.dumps(reply_markup)

            # Get filename from stream or use default
            filename = getattr(document, "name", "document.pdf")
            files = {"document": (filename, document, "application/octet-stream")}

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}{token}/sendDocument",
                    data=data,
                    files=files,
                )
                response.raise_for_status()
                return response.json()
        else:
            # Use JSON for file_id
            payload = {"chat_id": chat_id, "document": document}
            if caption:
                payload["caption"] = caption
            if parse_mode:
                payload["parse_mode"] = parse_mode
            if reply_markup:
                payload["reply_markup"] = reply_markup

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}{token}/sendDocument",
                    json=payload,
                )
                response.raise_for_status()
                return response.json()

    async def send_audio(
        self,
        token: str,
        chat_id: int,
        audio,  # Can be str (file_id) or BytesIO (stream)
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Envia áudio"""
        from io import BytesIO

        # Check if audio is a BytesIO stream
        if isinstance(audio, BytesIO):
            # Use multipart/form-data for file upload
            data = {"chat_id": str(chat_id)}
            if caption:
                data["caption"] = caption
            if parse_mode:
                data["parse_mode"] = parse_mode
            if reply_markup:
                data["reply_markup"] = json.dumps(reply_markup)

            # Get filename from stream or use default
            filename = getattr(audio, "name", "audio.mp3")
            files = {"audio": (filename, audio, "audio/mpeg")}

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}{token}/sendAudio",
                    data=data,
                    files=files,
                )
                response.raise_for_status()
                return response.json()
        else:
            # Use JSON for file_id
            payload = {"chat_id": chat_id, "audio": audio}
            if caption:
                payload["caption"] = caption
            if parse_mode:
                payload["parse_mode"] = parse_mode
            if reply_markup:
                payload["reply_markup"] = reply_markup

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}{token}/sendAudio",
                    json=payload,
                )
                response.raise_for_status()
                return response.json()

    async def send_animation(
        self,
        token: str,
        chat_id: int,
        animation,  # Can be str (file_id) or BytesIO (stream)
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Envia GIF/animação"""
        from io import BytesIO

        # Check if animation is a BytesIO stream
        if isinstance(animation, BytesIO):
            # Use multipart/form-data for file upload
            data = {"chat_id": str(chat_id)}
            if caption:
                data["caption"] = caption
            if parse_mode:
                data["parse_mode"] = parse_mode
            if reply_markup:
                data["reply_markup"] = json.dumps(reply_markup)

            # Get filename from stream or use default
            filename = getattr(animation, "name", "animation.gif")
            files = {"animation": (filename, animation, "image/gif")}

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}{token}/sendAnimation",
                    data=data,
                    files=files,
                )
                response.raise_for_status()
                return response.json()
        else:
            # Use JSON for file_id
            payload = {"chat_id": chat_id, "animation": animation}
            if caption:
                payload["caption"] = caption
            if parse_mode:
                payload["parse_mode"] = parse_mode
            if reply_markup:
                payload["reply_markup"] = reply_markup

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}{token}/sendAnimation",
                    json=payload,
                )
                response.raise_for_status()
                return response.json()

    def answer_callback_query_sync(
        self, token: str, callback_query_id: str, text: str = ""
    ) -> Dict[str, Any]:
        """Responde callback query (versão síncrona)"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=30.0) as client:
                    response = client.post(
                        f"{self.BASE_URL}{token}/answerCallbackQuery",
                        json={"callback_query_id": callback_query_id, "text": text},
                    )
                    response.raise_for_status()
                    return response.json()
            except (httpx.ConnectError, httpx.ReadTimeout) as e:
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)
                    continue
                raise

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

        max_retries = 3
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=30.0) as client:
                    response = client.post(
                        f"{self.BASE_URL}{token}/editMessageText", json=payload
                    )
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as e:
                # Se mensagem já foi editada (400 Bad Request), não falhar
                if e.response.status_code == 400:
                    from core.telemetry import logger

                    logger.warning(
                        "Edit message failed (probably already edited)",
                        extra={"message_id": message_id, "error": str(e)},
                    )
                    return {"ok": False, "description": "message already edited"}
                raise
            except (httpx.ConnectError, httpx.ReadTimeout) as e:
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)
                    continue
                raise

    async def send_chat_action(
        self,
        token: str,
        chat_id: int,
        action: str,
    ) -> Dict[str, Any]:
        """
        Envia ação de chat (typing, upload_photo, etc)

        Args:
            token: Token do bot
            chat_id: ID do chat/usuário
            action: Tipo de ação (typing, upload_photo, record_video, upload_video,
                   record_voice, upload_voice, upload_document, find_location,
                   record_video_note, upload_video_note, choose_sticker)

        Returns:
            Resposta da API do Telegram
        """
        payload = {
            "chat_id": chat_id,
            "action": action,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.BASE_URL}{token}/sendChatAction",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    def send_chat_action_sync(
        self,
        token: str,
        chat_id: int,
        action: str,
    ) -> Dict[str, Any]:
        """
        Envia ação de chat - versão síncrona para workers

        Args:
            token: Token do bot
            chat_id: ID do chat/usuário
            action: Tipo de ação (typing, upload_photo, record_video, upload_video,
                   record_voice, upload_voice, upload_document, find_location,
                   record_video_note, upload_video_note, choose_sticker)

        Returns:
            Resposta da API do Telegram
        """
        payload = {
            "chat_id": chat_id,
            "action": action,
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=30.0) as client:
                    response = client.post(
                        f"{self.BASE_URL}{token}/sendChatAction",
                        json=payload,
                    )
                    response.raise_for_status()
                    return response.json()
            except (httpx.ConnectError, httpx.ReadTimeout) as e:
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)  # Exponential backoff
                    continue
                raise
