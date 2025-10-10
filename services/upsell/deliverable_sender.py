"""
Sender para blocos de entregável de upsell
"""

import asyncio
from typing import Optional

from core.telemetry import logger
from database.repos import UpsellDeliverableBlockRepository
from services.media_voice_enforcer import VoiceConversionError, normalize_media_type
from workers.api_clients import TelegramAPI


class DeliverableSender:
    """Envia blocos de entregável de upsell"""

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.telegram_api = TelegramAPI()

    async def send_deliverable(
        self, upsell_id: int, chat_id: int, bot_id: Optional[int] = None
    ):
        """Envia todos os blocos do entregável"""
        blocks = await UpsellDeliverableBlockRepository.get_blocks_by_upsell(upsell_id)

        if not blocks:
            return

        for block in blocks:
            if block.delay_seconds > 0:
                await asyncio.sleep(block.delay_seconds)

            await self._send_block(block, chat_id, bot_id)

    def send_deliverable_sync(
        self, upsell_id: int, chat_id: int, bot_id: Optional[int] = None
    ):
        """Versão síncrona para workers"""
        import time

        from database.repos import UpsellDeliverableBlockRepository

        blocks = UpsellDeliverableBlockRepository.get_blocks_by_upsell_sync(upsell_id)

        if not blocks:
            return

        for block in blocks:
            if block.delay_seconds > 0:
                time.sleep(block.delay_seconds)

            asyncio.run(self._send_block(block, chat_id, bot_id))

    async def _send_block(self, block, chat_id: int, bot_id: Optional[int] = None):
        """Envia bloco individual"""
        if block.media_file_id and block.media_type:
            await self._send_media(block, chat_id, bot_id)
        elif block.text:
            await self._send_text(block, chat_id)

    async def _send_text(self, block, chat_id: int):
        """Envia texto simples"""
        await self.telegram_api.send_message(
            token=self.bot_token,
            chat_id=chat_id,
            text=block.text or "",
            parse_mode="Markdown",
        )

    async def _send_media(self, block, chat_id: int, bot_id: Optional[int] = None):
        """Envia mídia com legenda (com suporte a stream entre bots)"""
        source_media_type = block.media_type
        media_type = normalize_media_type(source_media_type)
        caption = block.text if block.text else None
        file_to_send = block.media_file_id
        file_stream = None

        # Se tem bot_id, usar sistema de cache/stream
        if bot_id:
            from services.media_stream import MediaStreamService

            try:
                cached_file_id, stream = await MediaStreamService.get_or_stream_media(
                    original_file_id=block.media_file_id,
                    bot_id=bot_id,
                    media_type=media_type,
                    manager_bot_token=None,
                    source_media_type=source_media_type,
                )
            except VoiceConversionError:
                logger.error(
                    "Voice conversion failed for upsell deliverable block",
                    extra={
                        "upsell_id": getattr(block, "upsell_id", None),
                        "bot_id": bot_id,
                    },
                )
                return

            if cached_file_id:
                # Usar file_id do cache
                file_to_send = cached_file_id
            elif stream:
                # Usar stream
                file_stream = stream

        # Enviar mídia
        result = None
        if media_type == "photo":
            result = await self.telegram_api.send_photo(
                token=self.bot_token,
                chat_id=chat_id,
                photo=file_stream if file_stream else file_to_send,
                caption=caption,
                parse_mode="Markdown" if caption else None,
            )
        elif media_type == "video":
            result = await self.telegram_api.send_video(
                token=self.bot_token,
                chat_id=chat_id,
                video=file_stream if file_stream else file_to_send,
                caption=caption,
                parse_mode="Markdown" if caption else None,
            )
        elif media_type == "voice":
            result = await self.telegram_api.send_voice(
                token=self.bot_token,
                chat_id=chat_id,
                voice=file_stream if file_stream else file_to_send,
                caption=caption,
                parse_mode="Markdown" if caption else None,
            )
        elif media_type == "animation":
            result = await self.telegram_api.send_animation(
                token=self.bot_token,
                chat_id=chat_id,
                animation=file_stream if file_stream else file_to_send,
                caption=caption,
                parse_mode="Markdown" if caption else None,
            )
        else:  # document ou outro tipo
            result = await self.telegram_api.send_document(
                token=self.bot_token,
                chat_id=chat_id,
                document=file_stream if file_stream else file_to_send,
                caption=caption,
                parse_mode="Markdown" if caption else None,
            )

        # Se enviou com stream, cachear o novo file_id
        # TODO: Implementar cache de file_id se necessário
        if result and file_stream and bot_id:
            new_file_id = self._extract_file_id_from_result(result, media_type)
            if new_file_id:
                # Cache será implementado futuramente
                pass

    def _extract_file_id_from_result(
        self, result: dict, media_type: str
    ) -> Optional[str]:
        """Extrai file_id do resultado da API do Telegram"""
        try:
            if "result" in result:
                message = result["result"]
                if media_type == "photo" and "photo" in message:
                    return message["photo"][-1]["file_id"]
                elif media_type in message:
                    return message[media_type]["file_id"]
        except (KeyError, IndexError, TypeError):
            pass
        return None
