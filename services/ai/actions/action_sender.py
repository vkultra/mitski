"""
Serviço de envio de blocos de ação
"""

import asyncio
from typing import List, Optional, Tuple

from core.telemetry import logger
from database.repos import AIActionBlockRepository, MediaFileCacheRepository
from workers.api_clients import TelegramAPI


class ActionSenderService:
    """Envia blocos de ação aos usuários"""

    def __init__(self, bot_token: str):
        """
        Args:
            bot_token: Token do bot para enviar mensagens
        """
        self.bot_token = bot_token
        self.api = TelegramAPI()

    async def send_action_blocks(
        self,
        action_id: int,
        chat_id: int,
        bot_id: Optional[int] = None,
        preview_mode: bool = False,
    ) -> List[int]:
        """
        Envia todos os blocos de uma ação

        Args:
            action_id: ID da ação
            chat_id: ID do chat/usuário
            bot_id: ID do bot (para cache de mídia)
            preview_mode: Se True, ignora delays e auto-delete

        Returns:
            Lista de message_ids enviados
        """
        # Buscar blocos ordenados
        blocks = await AIActionBlockRepository.get_blocks_by_action(action_id)

        if not blocks:
            logger.warning("No blocks found for action", extra={"action_id": action_id})
            return []

        message_ids = []

        for block in blocks:
            # Determina tipo de mídia para efeito apropriado
            media_type = block.media_type if block.media_file_id else None

            # Aplica efeito de digitação antes de enviar
            if not preview_mode:
                from services.typing_effect import TypingEffectService

                # Se tem delay configurado, usa ele como base para o typing
                if block.delay_seconds > 0:
                    # Aplica typing durante o delay configurado
                    await TypingEffectService.apply_typing_effect(
                        api=self.api,
                        token=self.bot_token,
                        chat_id=chat_id,
                        text=block.text,
                        media_type=media_type,
                        custom_delay=block.delay_seconds,
                    )
                else:
                    # Calcula delay natural baseado no texto
                    await TypingEffectService.apply_typing_effect(
                        api=self.api,
                        token=self.bot_token,
                        chat_id=chat_id,
                        text=block.text,
                        media_type=media_type,
                    )

            # Preparar conteúdo
            text = block.text or ""
            media_file_id = None
            result = None  # Inicializar result

            # Se tem mídia, verificar cache
            if block.media_file_id and bot_id:
                cached = await MediaFileCacheRepository.get_cached_file_id(
                    original_file_id=block.media_file_id,
                    bot_id=bot_id,
                )

                if cached:
                    media_file_id = cached
                    # Ainda precisa enviar com file_id cacheado
                else:
                    # Fazer streaming da mídia e enviar
                    media_file_id, stream_result = await self._stream_media_to_bot(
                        block.media_file_id,
                        block.media_type,
                        bot_id,
                        chat_id,
                        text,
                    )

                    # Se já enviou via stream, usar o resultado
                    if stream_result:
                        result = stream_result
            elif block.media_file_id:
                # Sem bot_id, usar file_id original
                media_file_id = block.media_file_id

            # Enviar mensagem (APENAS se não foi enviada via stream)
            try:
                # Só enviar se ainda não enviou (result é None)
                if not result:
                    if media_file_id:
                        # Enviar com mídia
                        result = await self._send_media_message(
                            chat_id, media_file_id, block.media_type, text
                        )
                    elif text:
                        # Enviar apenas texto
                        result = await self.api.send_message(
                            token=self.bot_token,
                            chat_id=chat_id,
                            text=text,
                            parse_mode="HTML",
                        )
                    else:
                        continue

                if result and "result" in result:
                    msg_id = result["result"].get("message_id")
                    if msg_id:
                        message_ids.append(msg_id)

                        # Auto-deletar se configurado
                        if not preview_mode and block.auto_delete_seconds > 0:
                            asyncio.create_task(
                                self._auto_delete_message(
                                    chat_id, msg_id, block.auto_delete_seconds
                                )
                            )

            except Exception as e:
                logger.error(
                    "Failed to send action block",
                    extra={"error": str(e), "block_id": block.id},
                )

        return message_ids

    async def _send_media_message(
        self, chat_id: int, file_id: str, media_type: str, caption: str = ""
    ) -> dict:
        """Envia mensagem com mídia baseado no tipo"""
        if media_type == "photo":
            return await self.api.send_photo(
                token=self.bot_token,
                chat_id=chat_id,
                photo=file_id,
                caption=caption,
                parse_mode="HTML",
            )
        elif media_type == "video":
            return await self.api.send_video(
                token=self.bot_token,
                chat_id=chat_id,
                video=file_id,
                caption=caption,
                parse_mode="HTML",
            )
        elif media_type == "audio":
            return await self.api.send_audio(
                token=self.bot_token,
                chat_id=chat_id,
                audio=file_id,
                caption=caption,
                parse_mode="HTML",
            )
        elif media_type == "document" or media_type == "gif":
            return await self.api.send_document(
                token=self.bot_token,
                chat_id=chat_id,
                document=file_id,
                caption=caption,
                parse_mode="HTML",
            )
        else:
            # Tipo desconhecido, enviar como documento
            return await self.api.send_document(
                token=self.bot_token,
                chat_id=chat_id,
                document=file_id,
                caption=caption,
                parse_mode="HTML",
            )

    async def _stream_media_to_bot(
        self,
        original_file_id: str,
        media_type: str,
        bot_id: int,
        chat_id: int,
        caption: str = "",
    ) -> Tuple[Optional[str], Optional[dict]]:
        """
        Faz streaming de mídia do bot gerenciador para bot secundário

        Returns:
            Tupla (novo_file_id, resultado_do_envio)
            - Se já enviou: (new_file_id, result)
            - Se só tem cache: (cached_file_id, None)
        """
        from core.config import settings
        from services.media_stream import MediaStreamService

        # Obter file_id do cache ou stream
        cached_file_id, stream = await MediaStreamService.get_or_stream_media(
            original_file_id=original_file_id,
            bot_id=bot_id,
            media_type=media_type,
            manager_bot_token=settings.MANAGER_BOT_TOKEN,
        )

        # Se já está no cache, retornar sem enviar
        if cached_file_id:
            return cached_file_id, None

        # Se tem stream, enviar e cachear o novo file_id
        if stream:
            # Enviar mídia com stream (ÚNICA VEZ)
            result = await self._send_media_with_stream(
                chat_id=chat_id,
                media_stream=stream,
                media_type=media_type,
                caption=caption,
                original_file_id=original_file_id,
                bot_id=bot_id,
            )

            if result and "result" in result:
                # Extrair novo file_id baseado no tipo
                new_file_id = self._extract_file_id_from_result(
                    result["result"], media_type
                )

                if new_file_id:
                    # Cachear para uso futuro
                    from database.repos import MediaFileCacheRepository

                    await MediaFileCacheRepository.save_cached_file_id(
                        original_file_id=original_file_id,
                        bot_id=bot_id,
                        cached_file_id=new_file_id,
                        media_type=media_type,
                    )
                    return new_file_id, result  # Retornar file_id E resultado

            return original_file_id, result  # Mesmo sem novo file_id, já enviou

        # Fallback - retornar original sem enviar
        return original_file_id, None

    async def _send_media_with_stream(
        self,
        chat_id: int,
        media_stream,
        media_type: str,
        caption: str = "",
        original_file_id: str = "",
        bot_id: int = None,
    ) -> Optional[dict]:
        """Envia mídia usando stream"""
        try:
            # TelegramAPI já aceita BytesIO diretamente
            if media_type == "photo":
                return await self.api.send_photo(
                    token=self.bot_token,
                    chat_id=chat_id,
                    photo=media_stream,  # BytesIO object
                    caption=caption,
                    parse_mode="HTML",
                )
            elif media_type == "video":
                return await self.api.send_video(
                    token=self.bot_token,
                    chat_id=chat_id,
                    video=media_stream,  # BytesIO object
                    caption=caption,
                    parse_mode="HTML",
                )
            elif media_type == "audio":
                return await self.api.send_audio(
                    token=self.bot_token,
                    chat_id=chat_id,
                    audio=media_stream,  # BytesIO object
                    caption=caption,
                    parse_mode="HTML",
                )
            else:
                return await self.api.send_document(
                    token=self.bot_token,
                    chat_id=chat_id,
                    document=media_stream,  # BytesIO object
                    caption=caption,
                    parse_mode="HTML",
                )
        except Exception as e:
            logger.error(
                "Failed to send media with stream",
                extra={"error": str(e), "media_type": media_type},
            )
            return None

    def _extract_file_id_from_result(
        self, result: dict, media_type: str
    ) -> Optional[str]:
        """Extrai file_id do resultado do Telegram baseado no tipo"""
        try:
            if media_type == "photo" and "photo" in result:
                # Para fotos, pegar a maior resolução
                photos = result.get("photo", [])
                if photos:
                    return photos[-1].get("file_id")
            elif media_type == "video" and "video" in result:
                return result["video"].get("file_id")
            elif media_type == "audio" and "audio" in result:
                return result["audio"].get("file_id")
            elif media_type == "document" and "document" in result:
                return result["document"].get("file_id")
            elif media_type == "animation" and "animation" in result:
                return result["animation"].get("file_id")
            elif media_type == "voice" and "voice" in result:
                return result["voice"].get("file_id")
        except Exception as e:
            logger.error(
                "Failed to extract file_id",
                extra={"error": str(e), "media_type": media_type},
            )

        return None

    async def _auto_delete_message(self, chat_id: int, message_id: int, delay: int):
        """Auto-deleta mensagem após delay"""
        await asyncio.sleep(delay)
        try:
            await self.api.delete_message(
                token=self.bot_token, chat_id=chat_id, message_id=message_id
            )
        except Exception as e:
            logger.error("Failed to auto-delete message", extra={"error": str(e)})
