"""Serviço para enviar blocos de recuperação."""

from __future__ import annotations

import asyncio
from typing import Iterable, List, Optional

from core.telemetry import logger
from database.models import RecoveryBlock
from services.media_stream import MediaStreamService
from services.media_voice_enforcer import VoiceConversionError, normalize_media_type
from workers.api_clients import TelegramAPI


class RecoveryMessageSender:
    """Envia blocos configurados para um chat específico."""

    def __init__(self, bot_token: str, *, bot_id: Optional[int] = None) -> None:
        self.bot_token = bot_token
        self.bot_id = bot_id
        self.telegram_api = TelegramAPI()

    async def send_blocks(
        self,
        blocks: Iterable[RecoveryBlock],
        *,
        chat_id: int,
        preview: bool = True,
        bot_id: Optional[int] = None,
    ) -> List[int]:
        message_ids: List[int] = []
        effective_bot_id = bot_id or self.bot_id

        for block in blocks:
            try:
                if block.delay_seconds and not preview:
                    await asyncio.sleep(block.delay_seconds)

                if block.media_file_id:
                    message_id = await self._send_media_block(
                        chat_id=chat_id,
                        block=block,
                        bot_id=effective_bot_id,
                    )
                else:
                    message_id = await self._send_text_block(chat_id, block)

                if message_id:
                    message_ids.append(message_id)
                    if block.auto_delete_seconds and not preview:
                        asyncio.create_task(
                            self._schedule_delete(
                                chat_id, message_id, block.auto_delete_seconds
                            )
                        )
            except Exception as exc:  # pragma: no cover - proteção
                logger.error(
                    "Failed to send recovery block",
                    extra={
                        "chat_id": chat_id,
                        "block_id": getattr(block, "id", None),
                        "error": str(exc),
                    },
                )
        return message_ids

    async def _send_text_block(
        self, chat_id: int, block: RecoveryBlock
    ) -> Optional[int]:
        if not block.text:
            return None
        result = await self.telegram_api.send_message(
            token=self.bot_token,
            chat_id=chat_id,
            text=block.text,
            parse_mode=block.parse_mode or "Markdown",
        )
        return result.get("result", {}).get("message_id")

    async def _send_media_block(
        self,
        *,
        chat_id: int,
        block: RecoveryBlock,
        bot_id: Optional[int],
    ) -> Optional[int]:
        source_media_type = block.media_type
        media_type = normalize_media_type(source_media_type)
        file_to_send = block.media_file_id
        stream = None

        if bot_id:
            try:
                cached_file_id, stream = await MediaStreamService.get_or_stream_media(
                    original_file_id=block.media_file_id,
                    bot_id=bot_id,
                    media_type=media_type,
                    source_media_type=source_media_type,
                )
            except VoiceConversionError:
                logger.error(
                    "Voice conversion failed for recovery block",
                    extra={
                        "bot_id": bot_id,
                        "block_id": getattr(block, "id", None),
                    },
                )
                return None
            if cached_file_id:
                file_to_send = cached_file_id
            elif stream:
                file_to_send = stream

        result = None
        kwargs = {
            "token": self.bot_token,
            "chat_id": chat_id,
            "caption": block.text,
            "parse_mode": block.parse_mode if block.text else None,
        }

        if media_type == "photo":
            result = await self.telegram_api.send_photo(photo=file_to_send, **kwargs)
        elif media_type == "video":
            result = await self.telegram_api.send_video(video=file_to_send, **kwargs)
        elif media_type == "voice":
            result = await self.telegram_api.send_voice(voice=file_to_send, **kwargs)
        elif media_type == "document":
            result = await self.telegram_api.send_document(
                document=file_to_send, **kwargs
            )
        elif media_type in {"animation", "gif"}:
            result = await self.telegram_api.send_animation(
                animation=file_to_send, **kwargs
            )
        else:
            logger.warning(
                "Unsupported media type for recovery block",
                extra={"media_type": media_type, "block_id": block.id},
            )
            return None

        if result and bot_id and stream is not None:
            new_file_id = self._extract_file_id(result, media_type)
            if new_file_id:
                await MediaStreamService.cache_media_file_id(
                    original_file_id=block.media_file_id,
                    bot_id=bot_id,
                    new_file_id=new_file_id,
                    media_type=media_type,
                )

        return result.get("result", {}).get("message_id") if result else None

    @staticmethod
    def _extract_file_id(result: dict, media_type: Optional[str]) -> Optional[str]:
        message = result.get("result", {})
        if media_type == "photo":
            photos = message.get("photo", [])
            return photos[-1]["file_id"] if photos else None
        field = {
            "video": "video",
            "voice": "voice",
            "document": "document",
            "animation": "animation",
            "gif": "animation",
        }.get(media_type or "")
        media_obj = message.get(field, {}) if field else {}
        return media_obj.get("file_id")

    async def _schedule_delete(self, chat_id: int, message_id: int, delay: int) -> None:
        await asyncio.sleep(delay)
        try:
            await self.telegram_api.delete_message(
                token=self.bot_token,
                chat_id=chat_id,
                message_id=message_id,
            )
        except Exception as exc:  # pragma: no cover - proteção
            logger.warning(
                "Failed to auto-delete recovery message",
                extra={"chat_id": chat_id, "message_id": message_id, "error": str(exc)},
            )
