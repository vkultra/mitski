"""
Serviço de envio de pitch de ofertas
"""

import asyncio
from typing import TYPE_CHECKING, List, Optional

from core.telemetry import logger
from database.repos import OfferPitchRepository, OfferRepository
from workers.api_clients import TelegramAPI

if TYPE_CHECKING:
    from database.models import OfferPitchBlock


class PitchSenderService:
    """Envia pitch de vendas formatado"""

    def __init__(self, bot_token: str):
        """
        Inicializa o serviço

        Args:
            bot_token: Token do bot para enviar mensagens
        """
        self.bot_token = bot_token
        self.telegram_api = TelegramAPI()
        self.sent_messages: List[int] = (
            []
        )  # Para rastrear mensagens enviadas (auto-delete)

    async def send_pitch(
        self,
        offer_id: int,
        chat_id: int,
        preview_mode: bool = False,
        bot_id: Optional[int] = None,
        user_telegram_id: Optional[int] = None,
    ) -> List[int]:
        """
        Envia o pitch completo de uma oferta

        Args:
            offer_id: ID da oferta
            chat_id: ID do chat para enviar
            preview_mode: Se True, não aplica delays/auto-delete
            bot_id: ID do bot (necessário para processar {pix})
            user_telegram_id: ID do usuário no Telegram (necessário para {pix})

        Returns:
            Lista de message_ids enviados
        """
        # Buscar blocos do pitch
        blocks = await OfferPitchRepository.get_blocks_by_offer(offer_id)

        if not blocks:
            logger.warning(
                "No pitch blocks found for offer",
                extra={"offer_id": offer_id},
            )
            return []

        message_ids = []

        for block in blocks:
            # Aplicar delay se configurado (exceto em preview)
            if block.delay_seconds > 0 and not preview_mode:
                await asyncio.sleep(block.delay_seconds)

            # Enviar mensagem baseado no tipo de conteúdo
            message_id = await self._send_block(
                block, chat_id, offer_id, bot_id, user_telegram_id
            )

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
            "Pitch sent successfully",
            extra={
                "offer_id": offer_id,
                "chat_id": chat_id,
                "blocks_sent": len(message_ids),
                "preview_mode": preview_mode,
            },
        )

        return message_ids

    async def _send_block(
        self,
        block: "OfferPitchBlock",
        chat_id: int,
        offer_id: Optional[int] = None,
        bot_id: Optional[int] = None,
        user_telegram_id: Optional[int] = None,
    ) -> Optional[int]:
        """
        Envia um bloco individual do pitch

        Args:
            block: Bloco a enviar
            chat_id: ID do chat
            offer_id: ID da oferta (para processar {pix})
            bot_id: ID do bot (para processar {pix})
            user_telegram_id: ID do usuário (para processar {pix})

        Returns:
            message_id da mensagem enviada ou None
        """
        try:
            # Processa tag {pix} se presente
            block_text = block.text
            transaction_created = None

            if block_text and offer_id and bot_id and user_telegram_id:
                from services.gateway.pix_processor import PixProcessor

                # Verifica e processa tag {pix}
                if PixProcessor.has_pix_tag(block_text):
                    processed_text, transaction = (
                        await PixProcessor.process_block_with_pix(
                            block_text, offer_id, bot_id, chat_id, user_telegram_id
                        )
                    )
                    block_text = processed_text
                    transaction_created = transaction

                    # Inicia verificação automática se transação foi criada
                    if transaction and hasattr(transaction, "id"):
                        from workers.payment_tasks import start_payment_verification

                        transaction_id = getattr(transaction, "id")
                        start_payment_verification.delay(transaction_id)

            # Se tem mídia
            if block.media_file_id:
                return await self._send_media_message(
                    chat_id,
                    block.media_file_id,
                    block.media_type,
                    block_text or block.text,  # Usa texto processado se disponível
                    bot_id=bot_id,  # Passa bot_id para cache
                )

            # Se tem apenas texto
            elif block_text:
                result = await self.telegram_api.send_message(
                    token=self.bot_token,
                    chat_id=chat_id,
                    text=block_text,
                    parse_mode="Markdown",
                )
                return result.get("result", {}).get("message_id")

            return None

        except Exception as e:
            logger.error(
                "Error sending pitch block",
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
        file_to_send = file_id  # Por padrão, usa o file_id original
        file_stream = None

        try:
            # Se tem bot_id, usar sistema de cache/stream
            if bot_id:
                from services.media_stream import MediaStreamService

                cached_file_id, stream = await MediaStreamService.get_or_stream_media(
                    original_file_id=file_id,
                    bot_id=bot_id,
                    media_type=media_type,
                    manager_bot_token=(
                        self.telegram_api.manager_bot_token
                        if hasattr(self.telegram_api, "manager_bot_token")
                        else None
                    ),
                )

                if cached_file_id:
                    # Usar file_id do cache
                    file_to_send = cached_file_id
                elif stream:
                    # Usar stream
                    file_stream = stream

            # Enviar mídia
            if media_type == "photo":
                result = await self.telegram_api.send_photo(
                    token=self.bot_token,
                    chat_id=chat_id,
                    photo=(
                        file_stream if file_stream else file_to_send
                    ),  # Stream ou file_id
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

            elif media_type == "audio":
                result = await self.telegram_api.send_audio(
                    token=self.bot_token,
                    chat_id=chat_id,
                    audio=file_stream if file_stream else file_to_send,
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

            elif media_type == "animation" or media_type == "gif":
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
                "Error sending media",
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

            # Mapeamento de tipos para campos no resultado
            type_fields = {
                "photo": "photo",  # É um array, pega o último (maior)
                "video": "video",
                "audio": "audio",
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
                "Message auto-deleted",
                extra={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "delay": delay_seconds,
                },
            )

        except Exception as e:
            logger.error(
                "Error auto-deleting message",
                extra={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "error": str(e),
                },
            )

    async def send_offer_notification(
        self,
        offer_id: int,
        chat_id: int,
        trigger_message: str,
    ) -> int:
        """
        Envia notificação de oferta detectada e depois o pitch

        Args:
            offer_id: ID da oferta
            chat_id: ID do chat
            trigger_message: Mensagem que acionou a oferta

        Returns:
            Número de mensagens enviadas
        """
        offer = await OfferRepository.get_offer_by_id(offer_id)

        if not offer:
            return 0

        # Enviar o pitch diretamente (substitui a mensagem da IA)
        message_ids = await self.send_pitch(offer_id, chat_id)

        return len(message_ids)
