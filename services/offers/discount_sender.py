"""Serviço de envio dos blocos de Descontos."""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, List, Optional

from core.telemetry import logger
from database.repos import OfferDiscountBlockRepository
from services.media_voice_enforcer import VoiceConversionError, normalize_media_type
from workers.api_clients import TelegramAPI

if TYPE_CHECKING:  # pragma: no cover - apenas para type checkers
    from database.models import OfferDiscountBlock


class DiscountSender:
    """Envia blocos configurados do menu de descontos."""

    _PIX_PATTERN = re.compile(r"\{pix\}", re.IGNORECASE)

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.telegram_api = TelegramAPI()

    async def send_discount_blocks(
        self,
        offer_id: int,
        chat_id: int,
        pix_code: Optional[str],
        preview_mode: bool = False,
        bot_id: Optional[int] = None,
    ) -> List[int]:
        """Envia blocos de desconto (modo assíncrono)."""

        blocks = await OfferDiscountBlockRepository.get_blocks_by_offer(offer_id)

        if not blocks:
            logger.warning(
                "No discount blocks configured",
                extra={"offer_id": offer_id},
            )
            return []

        message_ids: List[int] = []

        for block in blocks:
            source_media_type = block.media_type if block.media_file_id else None
            media_type = (
                normalize_media_type(source_media_type) if source_media_type else None
            )

            rendered_text = self._render_text(block.text, pix_code, preview_mode)

            if not preview_mode:
                from services.typing_effect import TypingEffectService

                if block.delay_seconds and block.delay_seconds > 0:
                    await TypingEffectService.apply_typing_effect(
                        api=self.telegram_api,
                        token=self.bot_token,
                        chat_id=chat_id,
                        text=rendered_text,
                        media_type=media_type,
                        custom_delay=block.delay_seconds,
                    )
                else:
                    await TypingEffectService.apply_typing_effect(
                        api=self.telegram_api,
                        token=self.bot_token,
                        chat_id=chat_id,
                        text=rendered_text,
                        media_type=media_type,
                    )

            message_id = await self._send_block(
                block, chat_id, rendered_text, pix_code, bot_id=bot_id
            )

            if message_id:
                message_ids.append(message_id)

                if not preview_mode and block.auto_delete_seconds > 0:
                    asyncio.create_task(
                        self._schedule_auto_delete(
                            chat_id, message_id, block.auto_delete_seconds
                        )
                    )

        logger.info(
            "Discount blocks sent",
            extra={
                "offer_id": offer_id,
                "chat_id": chat_id,
                "count": len(message_ids),
                "preview_mode": preview_mode,
            },
        )

        return message_ids

    def _render_text(
        self,
        text: Optional[str],
        pix_code: Optional[str],
        preview_mode: bool,
    ) -> str:
        base_text = text or ""
        replacement = pix_code or ("`PREVIEW_PIX_CODE`" if preview_mode else "")
        if not replacement:
            return base_text
        return self._PIX_PATTERN.sub(replacement, base_text)

    async def _send_block(
        self,
        block: "OfferDiscountBlock",
        chat_id: int,
        rendered_text: str,
        pix_code: Optional[str],
        bot_id: Optional[int] = None,
    ) -> Optional[int]:
        try:
            source_media_type = block.media_type if block.media_file_id else None
            media_type = (
                normalize_media_type(source_media_type) if source_media_type else None
            )

            if block.media_file_id:
                return await self._send_media(
                    chat_id,
                    block.media_file_id,
                    media_type,
                    rendered_text,
                    bot_id=bot_id,
                    source_media_type=source_media_type,
                )

            if rendered_text:
                result = await self.telegram_api.send_message(
                    token=self.bot_token,
                    chat_id=chat_id,
                    text=rendered_text,
                    parse_mode="Markdown",
                )
                return result.get("result", {}).get("message_id")

            return None

        except Exception as exc:  # pragma: no cover - log defensivo
            logger.error(
                "Error sending discount block",
                extra={
                    "block_id": block.id,
                    "chat_id": chat_id,
                    "error": str(exc),
                },
            )
            return None

    async def _send_media(
        self,
        chat_id: int,
        file_id: str,
        media_type: Optional[str],
        caption: str,
        bot_id: Optional[int] = None,
        source_media_type: Optional[str] = None,
    ) -> Optional[int]:
        result = None
        stream = None
        file_to_send = file_id

        try:
            if bot_id:
                from services.media_stream import MediaStreamService

                try:
                    cached_file_id, stream = (
                        await MediaStreamService.get_or_stream_media(
                            original_file_id=file_id,
                            bot_id=bot_id,
                            media_type=media_type,
                            source_media_type=source_media_type,
                        )
                    )
                except VoiceConversionError:
                    logger.error(
                        "Voice conversion failed for discount block",
                        extra={"file_id": file_id, "bot_id": bot_id},
                    )
                    return None

                if cached_file_id:
                    file_to_send = cached_file_id
                elif stream:
                    stream.seek(0)

            if media_type == "photo":
                result = await self.telegram_api.send_photo(
                    token=self.bot_token,
                    chat_id=chat_id,
                    photo=stream if stream else file_to_send,
                    caption=caption or None,
                    parse_mode="Markdown" if caption else None,
                )
            elif media_type == "video":
                result = await self.telegram_api.send_video(
                    token=self.bot_token,
                    chat_id=chat_id,
                    video=stream if stream else file_to_send,
                    caption=caption or None,
                    parse_mode="Markdown" if caption else None,
                )
            elif media_type == "voice":
                result = await self.telegram_api.send_voice(
                    token=self.bot_token,
                    chat_id=chat_id,
                    voice=stream if stream else file_to_send,
                    caption=caption or None,
                    parse_mode="Markdown" if caption else None,
                )
            elif media_type == "document":
                result = await self.telegram_api.send_document(
                    token=self.bot_token,
                    chat_id=chat_id,
                    document=stream if stream else file_to_send,
                    caption=caption or None,
                    parse_mode="Markdown" if caption else None,
                )
            elif media_type in {"animation", "gif"}:
                result = await self.telegram_api.send_animation(
                    token=self.bot_token,
                    chat_id=chat_id,
                    animation=stream if stream else file_to_send,
                    caption=caption or None,
                    parse_mode="Markdown" if caption else None,
                )
            else:
                # fallback para texto se tipo não suportado
                if caption:
                    message = await self.telegram_api.send_message(
                        token=self.bot_token,
                        chat_id=chat_id,
                        text=caption,
                        parse_mode="Markdown",
                    )
                    return message.get("result", {}).get("message_id")

            if result:
                return result.get("result", {}).get("message_id")

        except Exception as exc:  # pragma: no cover - log defensivo
            logger.error(
                "Error sending discount media",
                extra={
                    "chat_id": chat_id,
                    "media_type": media_type,
                    "error": str(exc),
                },
            )
        finally:
            if stream:
                stream.close()

        return None

    async def _schedule_auto_delete(
        self, chat_id: int, message_id: int, delay_seconds: int
    ) -> None:
        await asyncio.sleep(delay_seconds)
        try:
            await self.telegram_api.delete_message(
                token=self.bot_token,
                chat_id=chat_id,
                message_id=message_id,
            )
        except Exception as exc:  # pragma: no cover - log defensivo
            logger.error(
                "Error auto deleting discount message",
                extra={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "error": str(exc),
                },
            )
