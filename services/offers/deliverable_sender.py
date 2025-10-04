"""
Serviço de envio de blocos de entregável
"""

import asyncio
from typing import List, Optional

from core.telemetry import logger
from database.repos import OfferDeliverableBlockRepository, OfferRepository
from workers.api_clients import TelegramAPI


class DeliverableSender:
    """Envia blocos de entregável formatado"""

    def __init__(self, bot_token: str):
        """
        Inicializa o serviço

        Args:
            bot_token: Token do bot para enviar mensagens
        """
        self.bot_token = bot_token
        self.telegram_api = TelegramAPI()

    async def send_deliverable(
        self,
        offer_id: int,
        chat_id: int,
        preview_mode: bool = False,
    ) -> List[int]:
        """
        Envia o entregável completo de uma oferta

        Args:
            offer_id: ID da oferta
            chat_id: ID do chat para enviar
            preview_mode: Se True, não aplica delays/auto-delete

        Returns:
            Lista de message_ids enviados
        """
        # Buscar blocos do entregável
        blocks = await OfferDeliverableBlockRepository.get_blocks_by_offer(offer_id)

        if not blocks:
            logger.warning(
                "No deliverable blocks found for offer",
                extra={"offer_id": offer_id},
            )
            return []

        message_ids = []

        for block in blocks:
            # Aplicar delay se configurado (exceto em preview)
            if block.delay_seconds > 0 and not preview_mode:
                await asyncio.sleep(block.delay_seconds)

            # Enviar mensagem baseado no tipo de conteúdo
            message_id = await self._send_block(block, chat_id)

            if message_id:
                message_ids.append(message_id)

                # Programar auto-delete se configurado (exceto em preview)
                if block.auto_delete_seconds > 0 and not preview_mode:
                    asyncio.create_task(
                        self._auto_delete_message(
                            chat_id, message_id, block.auto_delete_seconds
                        )
                    )

        logger.info(
            "Deliverable sent successfully",
            extra={
                "offer_id": offer_id,
                "chat_id": chat_id,
                "blocks_sent": len(message_ids),
                "preview_mode": preview_mode,
            },
        )

        return message_ids

    def send_deliverable_sync(
        self,
        offer_id: int,
        chat_id: int,
        preview_mode: bool = False,
    ) -> List[int]:
        """
        Versão síncrona para workers

        Args:
            offer_id: ID da oferta
            chat_id: ID do chat
            preview_mode: Se True, não aplica efeitos

        Returns:
            Lista de message_ids
        """
        import time

        blocks = OfferDeliverableBlockRepository.get_blocks_by_offer_sync(offer_id)

        if not blocks:
            return []

        message_ids = []

        for block in blocks:
            if block.delay_seconds > 0 and not preview_mode:
                time.sleep(block.delay_seconds)

            message_id = self._send_block_sync(block, chat_id)

            if message_id:
                message_ids.append(message_id)

        return message_ids

    async def _send_block(
        self, block: "OfferDeliverableBlock", chat_id: int
    ) -> Optional[int]:
        """
        Envia um bloco individual do entregável

        Args:
            block: Bloco a enviar
            chat_id: ID do chat

        Returns:
            message_id da mensagem enviada ou None
        """
        try:
            # Se tem mídia
            if block.media_file_id:
                return await self._send_media_message(
                    chat_id,
                    block.media_file_id,
                    block.media_type,
                    block.text,
                )

            # Se tem apenas texto
            elif block.text:
                result = await self.telegram_api.send_message(
                    token=self.bot_token,
                    chat_id=chat_id,
                    text=block.text,
                    parse_mode="Markdown",
                )
                return result.get("result", {}).get("message_id")

            return None

        except Exception as e:
            logger.error(
                "Error sending deliverable block",
                extra={
                    "block_id": block.id,
                    "chat_id": chat_id,
                    "error": str(e),
                },
            )
            return None

    def _send_block_sync(
        self, block: "OfferDeliverableBlock", chat_id: int
    ) -> Optional[int]:
        """Versão síncrona para workers"""
        try:
            if block.media_file_id:
                return self._send_media_message_sync(
                    chat_id, block.media_file_id, block.media_type, block.text
                )
            elif block.text:
                result = self.telegram_api.send_message_sync(
                    token=self.bot_token,
                    chat_id=chat_id,
                    text=block.text,
                    keyboard=None,
                )
                return result.get("result", {}).get("message_id")
            return None
        except Exception as e:
            logger.error(
                "Error sending block (sync)",
                extra={"block_id": block.id, "error": str(e)},
            )
            return None

    async def _send_media_message(
        self,
        chat_id: int,
        file_id: str,
        media_type: str,
        caption: str = None,
    ) -> Optional[int]:
        """
        Envia mensagem com mídia

        Args:
            chat_id: ID do chat
            file_id: file_id do Telegram
            media_type: Tipo de mídia
            caption: Legenda opcional

        Returns:
            message_id ou None
        """
        result = None

        try:
            if media_type == "photo":
                result = await self.telegram_api.send_photo(
                    token=self.bot_token,
                    chat_id=chat_id,
                    photo=file_id,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
                )

            elif media_type == "video":
                result = await self.telegram_api.send_video(
                    token=self.bot_token,
                    chat_id=chat_id,
                    video=file_id,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
                )

            elif media_type == "audio":
                result = await self.telegram_api.send_audio(
                    token=self.bot_token,
                    chat_id=chat_id,
                    audio=file_id,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
                )

            elif media_type == "document":
                result = await self.telegram_api.send_document(
                    token=self.bot_token,
                    chat_id=chat_id,
                    document=file_id,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
                )

            elif media_type in ["animation", "gif"]:
                result = await self.telegram_api.send_animation(
                    token=self.bot_token,
                    chat_id=chat_id,
                    animation=file_id,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
                )

            if result:
                return result.get("result", {}).get("message_id")

        except Exception as e:
            logger.error(
                "Error sending media",
                extra={
                    "chat_id": chat_id,
                    "media_type": media_type,
                    "error": str(e),
                },
            )

        return None

    def _send_media_message_sync(
        self, chat_id: int, file_id: str, media_type: str, caption: str = None
    ) -> Optional[int]:
        """Versão síncrona (simplificada para workers)"""
        # Para workers, usa send_message com texto se tiver caption
        if caption:
            result = self.telegram_api.send_message_sync(
                token=self.bot_token, chat_id=chat_id, text=caption, keyboard=None
            )
            return result.get("result", {}).get("message_id")
        return None

    async def _auto_delete_message(
        self, chat_id: int, message_id: int, delay_seconds: int
    ):
        """
        Auto-deleta mensagem após delay

        Args:
            chat_id: ID do chat
            message_id: ID da mensagem
            delay_seconds: Segundos para aguardar antes de deletar
        """
        await asyncio.sleep(delay_seconds)

        try:
            await self.telegram_api.delete_message(
                token=self.bot_token,
                chat_id=chat_id,
                message_id=message_id,
            )

            logger.info(
                "Deliverable message auto-deleted",
                extra={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "delay": delay_seconds,
                },
            )

        except Exception as e:
            logger.error(
                "Error auto-deleting deliverable message",
                extra={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "error": str(e),
                },
            )
