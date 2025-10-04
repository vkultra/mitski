"""
Serviço de envio de blocos de verificação manual
"""

import asyncio
from typing import List, Optional

from core.telemetry import logger
from database.repos import OfferManualVerificationBlockRepository
from workers.api_clients import TelegramAPI


class ManualVerificationSender:
    """Envia blocos de verificação manual"""

    def __init__(self, bot_token: str):
        """
        Inicializa o serviço

        Args:
            bot_token: Token do bot para enviar mensagens
        """
        self.bot_token = bot_token
        self.telegram_api = TelegramAPI()

    async def send_manual_verification(
        self,
        offer_id: int,
        chat_id: int,
    ) -> List[int]:
        """
        Envia mensagens de verificação manual

        Args:
            offer_id: ID da oferta
            chat_id: ID do chat para enviar

        Returns:
            Lista de message_ids enviados
        """
        # Buscar blocos de verificação manual
        blocks = await OfferManualVerificationBlockRepository.get_blocks_by_offer(
            offer_id
        )

        if not blocks:
            logger.warning(
                "No manual verification blocks found",
                extra={"offer_id": offer_id},
            )
            return []

        message_ids = []

        for block in blocks:
            # Aplicar delay se configurado
            if block.delay_seconds > 0:
                await asyncio.sleep(block.delay_seconds)

            # Enviar mensagem
            message_id = await self._send_block(block, chat_id)

            if message_id:
                message_ids.append(message_id)

                # Programar auto-delete se configurado
                if block.auto_delete_seconds > 0:
                    asyncio.create_task(
                        self._auto_delete_message(
                            chat_id, message_id, block.auto_delete_seconds
                        )
                    )

        logger.info(
            "Manual verification sent successfully",
            extra={
                "offer_id": offer_id,
                "chat_id": chat_id,
                "blocks_sent": len(message_ids),
            },
        )

        return message_ids

    async def _send_block(
        self, block: "OfferManualVerificationBlock", chat_id: int
    ) -> Optional[int]:
        """
        Envia um bloco individual

        Args:
            block: Bloco a enviar
            chat_id: ID do chat

        Returns:
            message_id ou None
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
                "Error sending manual verification block",
                extra={
                    "block_id": block.id,
                    "chat_id": chat_id,
                    "error": str(e),
                },
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
                "Error sending verification media",
                extra={"chat_id": chat_id, "media_type": media_type, "error": str(e)},
            )

        return None

    async def _auto_delete_message(
        self, chat_id: int, message_id: int, delay_seconds: int
    ):
        """
        Auto-deleta mensagem após delay

        Args:
            chat_id: ID do chat
            message_id: ID da mensagem
            delay_seconds: Segundos para aguardar
        """
        await asyncio.sleep(delay_seconds)

        try:
            await self.telegram_api.delete_message(
                token=self.bot_token,
                chat_id=chat_id,
                message_id=message_id,
            )

            logger.info(
                "Verification message auto-deleted",
                extra={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "delay": delay_seconds,
                },
            )

        except Exception as e:
            logger.error(
                "Error auto-deleting verification message",
                extra={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "error": str(e),
                },
            )
