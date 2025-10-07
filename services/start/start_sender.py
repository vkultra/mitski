"""Envio de blocos configurados para a mensagem inicial /start."""

from __future__ import annotations

import asyncio
from typing import Dict, List, Optional, Tuple

import httpx

from core.config import settings
from core.telemetry import logger
from database.repos import MediaFileCacheRepository, StartTemplateBlockRepository
from services.media_stream import MediaStreamService
from services.typing_effect import TypingEffectService
from workers.api_clients import TelegramAPI


class StartTemplateSenderService:
    """Envia a mensagem inicial personalizada"""

    DEFAULT_PARSE_MODE = "Markdown"

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.api = TelegramAPI()

    async def send_template(
        self,
        template_id: int,
        bot_id: int,
        chat_id: int,
        preview_mode: bool = False,
        cache_media: bool = True,
    ) -> List[int]:
        blocks = await StartTemplateBlockRepository.list_blocks(template_id)
        if not blocks:
            logger.info(
                "No start blocks to send",
                extra={"template_id": template_id, "bot_id": bot_id},
            )
            return []

        sent_ids: List[int] = []

        for block in blocks:
            media_type = block.media_type if block.media_file_id else None

            if not preview_mode:
                if block.delay_seconds > 0:
                    await TypingEffectService.apply_typing_effect(
                        api=self.api,
                        token=self.bot_token,
                        chat_id=chat_id,
                        text=block.text,
                        media_type=media_type,
                        custom_delay=block.delay_seconds,
                    )
                else:
                    await TypingEffectService.apply_typing_effect(
                        api=self.api,
                        token=self.bot_token,
                        chat_id=chat_id,
                        text=block.text,
                        media_type=media_type,
                    )

            message_result = await self._send_block(
                block,
                bot_id=bot_id,
                chat_id=chat_id,
                cache_media=cache_media,
            )

            if message_result:
                sent_ids.append(message_result)
                if not preview_mode and block.auto_delete_seconds > 0:
                    asyncio.create_task(
                        self._auto_delete_message(
                            chat_id, message_result, block.auto_delete_seconds
                        )
                    )

        logger.info(
            "Start template delivered",
            extra={
                "template_id": template_id,
                "bot_id": bot_id,
                "messages_sent": len(sent_ids),
                "preview": preview_mode,
            },
        )

        return sent_ids

    async def _send_block(
        self,
        block,
        bot_id: int,
        chat_id: int,
        cache_media: bool,
    ) -> Optional[int]:
        text = block.text or ""
        media_file_id = block.media_file_id
        media_type = block.media_type

        result = None
        parse_mode: Optional[str] = self.DEFAULT_PARSE_MODE

        if media_file_id:
            cached_id, result = await self._get_or_send_media(
                original_file_id=media_file_id,
                media_type=media_type,
                bot_id=bot_id,
                chat_id=chat_id,
                caption=text,
                cache_media=cache_media,
                parse_mode=parse_mode,
            )
            media_file_id = cached_id

        if not result:
            if media_file_id:
                try:
                    result = await self._send_media_message(
                        chat_id=chat_id,
                        file_id=media_file_id,
                        media_type=media_type,
                        caption=text,
                        parse_mode=parse_mode,
                    )
                except httpx.HTTPStatusError as exc:
                    (
                        media_file_id,
                        result,
                        parse_mode,
                    ) = await self._handle_media_send_failure(
                        exc=exc,
                        block=block,
                        bot_id=bot_id,
                        chat_id=chat_id,
                        caption=text,
                        cache_media=cache_media,
                        current_file_id=media_file_id,
                        media_type=media_type,
                        parse_mode=parse_mode,
                    )
            elif text:
                result = await self.api.send_message(
                    token=self.bot_token,
                    chat_id=chat_id,
                    text=text,
                    parse_mode="Markdown",
                )

        if result and "result" in result:
            return result["result"].get("message_id")
        return None

    async def _get_or_send_media(
        self,
        original_file_id: str,
        media_type: str,
        bot_id: int,
        chat_id: int,
        caption: str,
        cache_media: bool,
        parse_mode: Optional[str],
        force_stream: bool = False,
    ) -> Tuple[Optional[str], Optional[dict]]:
        if not force_stream:
            cached_id = await MediaFileCacheRepository.get_cached_file_id(
                original_file_id=original_file_id,
                bot_id=bot_id,
            )
            if cached_id:
                return cached_id, None

        cached_id, stream = await MediaStreamService.get_or_stream_media(
            original_file_id=original_file_id,
            bot_id=bot_id,
            media_type=media_type,
            manager_bot_token=settings.MANAGER_BOT_TOKEN,
            skip_cache=force_stream,
        )

        if cached_id:
            return cached_id, None

        if stream:
            result = await self._send_media_with_stream(
                chat_id=chat_id,
                media_stream=stream,
                media_type=media_type,
                caption=caption,
                parse_mode=parse_mode,
            )

            if result and "result" in result:
                new_file_id = self._extract_file_id(result["result"], media_type)
                if new_file_id and cache_media:
                    await MediaFileCacheRepository.save_cached_file_id(
                        original_file_id=original_file_id,
                        bot_id=bot_id,
                        cached_file_id=new_file_id,
                        media_type=media_type,
                    )
                    return new_file_id, result
            # When caching disabled, we don't persist new file_id
            return (None if not cache_media else original_file_id, result)

        return (None if not cache_media else original_file_id, None)

    async def _send_media_with_stream(
        self,
        chat_id: int,
        media_stream,
        media_type: str,
        caption: str,
        parse_mode: Optional[str],
    ) -> Optional[dict]:
        if media_type == "photo":
            return await self.api.send_photo(
                token=self.bot_token,
                chat_id=chat_id,
                photo=media_stream,
                caption=caption,
                parse_mode=parse_mode,
            )
        if media_type == "video":
            return await self.api.send_video(
                token=self.bot_token,
                chat_id=chat_id,
                video=media_stream,
                caption=caption,
                parse_mode=parse_mode,
            )
        if media_type == "audio":
            return await self.api.send_audio(
                token=self.bot_token,
                chat_id=chat_id,
                audio=media_stream,
                caption=caption,
                parse_mode=parse_mode,
            )
        return await self.api.send_document(
            token=self.bot_token,
            chat_id=chat_id,
            document=media_stream,
            caption=caption,
            parse_mode=parse_mode,
        )

    async def _send_media_message(
        self,
        chat_id: int,
        file_id: str,
        media_type: str,
        caption: str,
        parse_mode: Optional[str],
    ) -> dict:
        if media_type == "photo":
            return await self.api.send_photo(
                token=self.bot_token,
                chat_id=chat_id,
                photo=file_id,
                caption=caption,
                parse_mode=parse_mode,
            )
        if media_type == "video":
            return await self.api.send_video(
                token=self.bot_token,
                chat_id=chat_id,
                video=file_id,
                caption=caption,
                parse_mode=parse_mode,
            )
        if media_type == "audio":
            return await self.api.send_audio(
                token=self.bot_token,
                chat_id=chat_id,
                audio=file_id,
                caption=caption,
                parse_mode=parse_mode,
            )
        return await self.api.send_document(
            token=self.bot_token,
            chat_id=chat_id,
            document=file_id,
            caption=caption,
            parse_mode=parse_mode,
        )

    async def _handle_media_send_failure(
        self,
        *,
        exc: httpx.HTTPStatusError,
        block,
        bot_id: int,
        chat_id: int,
        caption: str,
        cache_media: bool,
        current_file_id: Optional[str],
        media_type: Optional[str],
        parse_mode: Optional[str],
    ) -> Tuple[Optional[str], Optional[dict], Optional[str]]:
        details = self._extract_error_details(exc)
        logger.warning(
            "Start media send failed",
            extra={
                "bot_id": bot_id,
                "chat_id": chat_id,
                "template_block_id": getattr(block, "id", None),
                "original_file_id": block.media_file_id,
                "cached_file_id": current_file_id,
                "error_details": details,
            },
        )

        await MediaFileCacheRepository.clear_cached_file_id(
            original_file_id=block.media_file_id,
            bot_id=bot_id,
        )

        description = (details.get("telegram_description") or "").lower()
        is_parse_error = self._is_parse_mode_error(description)
        should_stream = cache_media or self._is_file_reference_error(description)
        next_parse_mode = parse_mode

        if is_parse_error:
            next_parse_mode = None
            target_file_id = current_file_id
            if not target_file_id and block.media_file_id:
                target_file_id, _ = await self._get_or_send_media(
                    original_file_id=block.media_file_id,
                    media_type=media_type,
                    bot_id=bot_id,
                    chat_id=chat_id,
                    caption=caption,
                    cache_media=cache_media,
                    parse_mode=next_parse_mode,
                    force_stream=True,
                )
            if target_file_id:
                result = await self._send_media_message(
                    chat_id=chat_id,
                    file_id=target_file_id,
                    media_type=media_type,
                    caption=caption,
                    parse_mode=next_parse_mode,
                )
                return target_file_id, result, next_parse_mode

        if (should_stream or not current_file_id) and block.media_file_id:
            media_file_id, result = await self._get_or_send_media(
                original_file_id=block.media_file_id,
                media_type=media_type,
                bot_id=bot_id,
                chat_id=chat_id,
                caption=caption,
                cache_media=cache_media,
                parse_mode=parse_mode,
                force_stream=True,
            )
            if result:
                return media_file_id, result, parse_mode
            if media_file_id:
                result = await self._send_media_message(
                    chat_id=chat_id,
                    file_id=media_file_id,
                    media_type=media_type,
                    caption=caption,
                    parse_mode=parse_mode,
                )
                return media_file_id, result, parse_mode

        raise exc

    @staticmethod
    def _extract_error_details(exc: httpx.HTTPStatusError) -> Dict[str, Optional[str]]:
        response = exc.response
        description: Optional[str] = None
        error_code: Optional[int] = None
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if isinstance(payload, dict):
            description = payload.get("description")
            error_code = payload.get("error_code")

        return {
            "status_code": str(response.status_code),
            "reason_phrase": response.reason_phrase,
            "telegram_description": description,
            "telegram_error_code": str(error_code) if error_code is not None else None,
        }

    @staticmethod
    def _is_parse_mode_error(description: str) -> bool:
        return "parse" in description and (
            "entity" in description or "entities" in description
        )

    @staticmethod
    def _is_file_reference_error(description: str) -> bool:
        return any(
            term in description
            for term in (
                "file reference is expired",
                "wrong file identifier",
                "file reference expired",
            )
        )

    @staticmethod
    def _extract_file_id(result_payload: dict, media_type: str) -> Optional[str]:
        if media_type == "photo":
            photos = result_payload.get("photo", [])
            if photos:
                return photos[-1].get("file_id")
        if media_type == "video":
            return result_payload.get("video", {}).get("file_id")
        if media_type == "audio":
            return result_payload.get("audio", {}).get("file_id")
        return result_payload.get("document", {}).get("file_id")

    async def _auto_delete_message(
        self, chat_id: int, message_id: int, delay_seconds: int
    ) -> None:
        await asyncio.sleep(delay_seconds)
        try:
            await self.api.delete_message(
                token=self.bot_token,
                chat_id=chat_id,
                message_id=message_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "Failed to auto delete start message",
                extra={"chat_id": chat_id, "message_id": message_id, "error": str(exc)},
            )
