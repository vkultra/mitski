"""
Sender para blocos de anúncio de upsell (similar a PitchSender)
"""

import asyncio
from typing import Optional

from core.telemetry import logger
from database.repos import UpsellAnnouncementBlockRepository
from services.gateway.upsell_pix_processor import UpsellPixProcessor
from workers.api_clients import TelegramAPI


class AnnouncementSender:
    """Envia blocos de anúncio de upsell"""

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.telegram_api = TelegramAPI()

    async def send_announcement(
        self, upsell_id: int, chat_id: int, bot_id: Optional[int] = None
    ):
        """Envia todos os blocos do anúncio"""
        blocks = await UpsellAnnouncementBlockRepository.get_blocks_by_upsell(upsell_id)

        if not blocks:
            return

        for block in blocks:
            # Delay antes de enviar
            if block.delay_seconds > 0:
                await asyncio.sleep(block.delay_seconds)

            await self._send_block(block, chat_id, bot_id)

    def send_announcement_sync(
        self, upsell_id: int, chat_id: int, bot_id: Optional[int] = None
    ):
        """Versão síncrona para workers"""
        import time

        from database.repos import UpsellAnnouncementBlockRepository

        blocks = UpsellAnnouncementBlockRepository.get_blocks_by_upsell_sync(upsell_id)

        if not blocks:
            return

        for block in blocks:
            # Delay
            if block.delay_seconds > 0:
                time.sleep(block.delay_seconds)

            asyncio.run(self._send_block(block, chat_id, bot_id))

    async def _send_block(self, block, chat_id: int, bot_id: Optional[int] = None):
        """Envia bloco individual"""
        # Determinar tipo de envio
        if block.media_file_id and block.media_type:
            # Enviar mídia com legenda
            await self._send_media(block, chat_id, bot_id)
        elif block.text:
            # Enviar apenas texto
            await self._send_text(block, chat_id, block.upsell_id, bot_id)

    async def _send_text(
        self, block, chat_id: int, upsell_id: int, bot_id: Optional[int] = None
    ):
        """Envia texto simples (processando tag {pixupsell} se houver)"""
        text = block.text or ""

        # Verificar se tem tag {pixupsell}
        if UpsellPixProcessor.has_pixupsell_tag(text) and bot_id:
            text, transaction = await UpsellPixProcessor.process_block_with_pixupsell(
                text=text,
                upsell_id=upsell_id,
                bot_id=bot_id,
                chat_id=chat_id,
                user_telegram_id=chat_id,
            )

            if transaction:
                # Iniciar verificação automática de pagamento
                from workers.upsell_tasks import verify_upsell_payment

                transaction_id = int(transaction.id)  # type: ignore
                verify_upsell_payment.apply_async(args=[transaction_id], countdown=60)

                logger.info(
                    "Upsell PIX generated and verification scheduled",
                    extra={
                        "transaction_id": transaction_id,
                        "upsell_id": upsell_id,
                        "chat_id": chat_id,
                    },
                )

        await self.telegram_api.send_message(
            token=self.bot_token,
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown",
        )

    async def _send_media(self, block, chat_id: int, bot_id: Optional[int] = None):
        """Envia mídia com legenda (com suporte a stream entre bots)"""
        # Processar texto/legenda
        caption = block.text or ""
        if UpsellPixProcessor.has_pixupsell_tag(caption) and bot_id:
            caption, transaction = (
                await UpsellPixProcessor.process_block_with_pixupsell(
                    text=caption,
                    upsell_id=block.upsell_id,
                    bot_id=bot_id,
                    chat_id=chat_id,
                    user_telegram_id=chat_id,
                )
            )

            if transaction:
                # Iniciar verificação automática de pagamento
                from workers.upsell_tasks import verify_upsell_payment

                transaction_id = int(transaction.id)  # type: ignore
                verify_upsell_payment.apply_async(args=[transaction_id], countdown=60)

                logger.info(
                    "Upsell PIX generated in media caption, verification scheduled",
                    extra={
                        "transaction_id": transaction_id,
                        "upsell_id": block.upsell_id,
                        "chat_id": chat_id,
                    },
                )

        # Preparar mídia com suporte a stream entre bots
        caption = caption if caption else None
        file_to_send = block.media_file_id
        file_stream = None

        # Se tem bot_id, usar sistema de cache/stream
        if bot_id:
            from services.media_stream import MediaStreamService

            cached_file_id, stream = await MediaStreamService.get_or_stream_media(
                original_file_id=block.media_file_id,
                bot_id=bot_id,
                media_type=block.media_type,
                manager_bot_token=None,
            )

            if cached_file_id:
                # Usar file_id do cache
                file_to_send = cached_file_id
            elif stream:
                # Usar stream
                file_stream = stream

        # Enviar mídia usando métodos específicos
        result = None
        if block.media_type == "photo":
            result = await self.telegram_api.send_photo(
                token=self.bot_token,
                chat_id=chat_id,
                photo=file_stream if file_stream else file_to_send,
                caption=caption,
                parse_mode="Markdown" if caption else None,
            )
        elif block.media_type == "video":
            result = await self.telegram_api.send_video(
                token=self.bot_token,
                chat_id=chat_id,
                video=file_stream if file_stream else file_to_send,
                caption=caption,
                parse_mode="Markdown" if caption else None,
            )
        elif block.media_type == "audio":
            result = await self.telegram_api.send_audio(
                token=self.bot_token,
                chat_id=chat_id,
                audio=file_stream if file_stream else file_to_send,
                caption=caption,
                parse_mode="Markdown" if caption else None,
            )
        elif block.media_type == "animation":
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
            new_file_id = self._extract_file_id_from_result(result, block.media_type)
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
