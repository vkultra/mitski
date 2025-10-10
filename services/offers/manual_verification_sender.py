"""
Serviço de envio de blocos de verificação manual
"""

import asyncio
from typing import TYPE_CHECKING, List, Optional

from core.telemetry import logger
from database.repos import OfferManualVerificationBlockRepository
from services.media_voice_enforcer import VoiceConversionError, normalize_media_type
from workers.api_clients import TelegramAPI

if TYPE_CHECKING:
    from database.models import OfferManualVerificationBlock


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
        bot_id: int = None,
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
            # Determina tipo de mídia para efeito apropriado
            source_media_type = block.media_type if block.media_file_id else None
            media_type = (
                normalize_media_type(source_media_type) if source_media_type else None
            )

            # Aplica efeito de digitação antes de enviar
            from services.typing_effect import TypingEffectService

            # Se tem delay configurado, usa ele como base para o typing
            if block.delay_seconds > 0:
                # Aplica typing durante o delay configurado
                await TypingEffectService.apply_typing_effect(
                    api=self.telegram_api,
                    token=self.bot_token,
                    chat_id=chat_id,
                    text=block.text,
                    media_type=media_type,
                    custom_delay=block.delay_seconds,
                )
            else:
                # Calcula delay natural baseado no texto
                await TypingEffectService.apply_typing_effect(
                    api=self.telegram_api,
                    token=self.bot_token,
                    chat_id=chat_id,
                    text=block.text,
                    media_type=media_type,
                )

            # Enviar mensagem
            message_id = await self._send_block(block, chat_id, bot_id=bot_id)

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
        self, block: "OfferManualVerificationBlock", chat_id: int, bot_id: int = None
    ) -> Optional[int]:
        """
        Envia um bloco individual

        Args:
            block: Bloco a enviar
            chat_id: ID do chat
            bot_id: ID do bot (para cache de mídia)

        Returns:
            message_id ou None
        """
        try:
            source_media_type = block.media_type if block.media_file_id else None
            media_type = (
                normalize_media_type(source_media_type) if source_media_type else None
            )
            # Se tem mídia
            if block.media_file_id:
                return await self._send_media_message(
                    chat_id,
                    block.media_file_id,
                    media_type,
                    block.text,
                    bot_id=bot_id,
                    source_media_type=source_media_type,
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
        bot_id: int = None,
        source_media_type: Optional[str] = None,
    ) -> Optional[int]:
        """
        Envia mensagem com mídia (com suporte a stream entre bots)

        Args:
            chat_id: ID do chat
            file_id: file_id do Telegram (original do bot gerenciador)
            media_type: Tipo de mídia
            caption: Legenda opcional
            bot_id: ID do bot secundário (para cache de mídia)

        Returns:
            message_id ou None
        """
        result = None
        file_to_send = file_id
        file_stream = None

        try:
            # Se tem bot_id, usar sistema de cache/stream
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
                        "Voice conversion failed for manual verification block",
                        extra={
                            "file_id": file_id,
                            "bot_id": bot_id,
                        },
                    )
                    return None

                if cached_file_id:
                    file_to_send = cached_file_id
                elif stream:
                    file_stream = stream

            # Enviar mídia
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

            elif media_type == "document":
                result = await self.telegram_api.send_document(
                    token=self.bot_token,
                    chat_id=chat_id,
                    document=file_stream if file_stream else file_to_send,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
                )

            elif media_type in ["animation", "gif"]:
                result = await self.telegram_api.send_animation(
                    token=self.bot_token,
                    chat_id=chat_id,
                    animation=file_stream if file_stream else file_to_send,
                    caption=caption,
                    parse_mode="Markdown" if caption else None,
                )

            # Se enviou com stream, cachear o novo file_id
            if result and file_stream and bot_id:
                new_file_id = self._extract_file_id_from_result(result, media_type)
                if new_file_id:
                    from services.media_stream import MediaStreamService

                    await MediaStreamService.cache_media_file_id(
                        original_file_id=file_id,
                        bot_id=bot_id,
                        new_file_id=new_file_id,
                        media_type=media_type,
                    )

            if result:
                return result.get("result", {}).get("message_id")

        except Exception as e:
            logger.error(
                "Error sending verification media",
                extra={
                    "chat_id": chat_id,
                    "media_type": media_type,
                    "used_stream": file_stream is not None,
                    "error": str(e),
                },
            )

        return None

    def _extract_file_id_from_result(
        self, result: dict, media_type: str
    ) -> Optional[str]:
        """Extrai file_id do resultado da API do Telegram"""
        try:
            message = result.get("result", {})
            type_fields = {
                "photo": "photo",
                "video": "video",
                "voice": "voice",
                "document": "document",
                "animation": "animation",
            }

            field = type_fields.get(media_type)
            if not field:
                return None

            if media_type == "photo":
                photos = message.get("photo", [])
                if photos:
                    return photos[-1].get("file_id")
            else:
                media_obj = message.get(field, {})
                return media_obj.get("file_id")

        except Exception as e:
            logger.error(
                "Error extracting file_id from result",
                extra={"media_type": media_type, "error": str(e)},
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
