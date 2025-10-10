"""
Serviço de stream de mídia entre bots
"""

from io import BytesIO
from typing import Optional, Tuple

import httpx

from core.config import settings
from core.telemetry import logger
from database.repos import MediaFileCacheRepository
from services.media_voice_enforcer import (
    VoiceConversionError,
    convert_stream_to_voice,
    should_convert_to_voice,
)


class MediaStreamService:
    """Gerencia stream de mídia entre bots diferentes"""

    # Mapeamento de extensões padrão por tipo de mídia
    DEFAULT_EXTENSIONS = {
        "photo": "jpg",
        "video": "mp4",
        "audio": "mp3",
        "voice": "ogg",
        "animation": "gif",
        "document": "pdf",
    }

    @staticmethod
    async def get_or_stream_media(
        original_file_id: str,
        bot_id: int,
        media_type: str,
        manager_bot_token: str = None,
        skip_cache: bool = False,
        source_media_type: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[BytesIO]]:
        """
        Obtém file_id do cache ou faz stream da mídia

        Args:
            original_file_id: file_id original do bot gerenciador
            bot_id: ID do bot secundário que vai usar
            media_type: Tipo de mídia (photo, video, etc)
            manager_bot_token: Token do bot gerenciador (para download)
            source_media_type: Tipo original persistido (para conversão)

        Returns:
            Tupla (cached_file_id, stream)
            - Se encontrou no cache: (file_id, None)
            - Se precisa fazer stream: (None, BytesIO)
        """
        # 1. Verificar cache
        if not skip_cache:
            cached_file_id = await MediaFileCacheRepository.get_cached_file_id(
                original_file_id=original_file_id,
                bot_id=bot_id,
                expected_media_type=media_type,
            )

            if cached_file_id:
                logger.info(
                    "Media found in cache",
                    extra={
                        "original_file_id": original_file_id,
                        "bot_id": bot_id,
                        "cached_file_id": cached_file_id,
                    },
                )
                return (cached_file_id, None)

        # 2. Não está no cache - fazer stream
        logger.info(
            "Media not in cache, downloading for stream",
            extra={
                "original_file_id": original_file_id,
                "bot_id": bot_id,
                "media_type": media_type,
            },
        )

        token = manager_bot_token or settings.MANAGER_BOT_TOKEN

        try:
            # Obter informações do arquivo
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Get file info
                file_info_response = await client.get(
                    f"https://api.telegram.org/bot{token}/getFile",
                    params={"file_id": original_file_id},
                )
                file_info_response.raise_for_status()
                file_data = file_info_response.json()

                if not file_data.get("ok"):
                    logger.error(
                        "Failed to get file info",
                        extra={
                            "file_id": original_file_id,
                            "error": file_data.get("description"),
                        },
                    )
                    return (None, None)

                file_path = file_data["result"]["file_path"]
                file_size = file_data["result"].get("file_size", 0)

                # Download file
                file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
                download_response = await client.get(file_url)
                download_response.raise_for_status()

                file_content = download_response.content

                logger.info(
                    "Media downloaded for stream",
                    extra={
                        "file_id": original_file_id,
                        "file_size": len(file_content),
                        "file_path": file_path,
                    },
                )

                # Criar stream com nome apropriado
                file_stream = BytesIO(file_content)

                # Detectar extensão do arquivo
                if media_type == "voice":
                    extension = MediaStreamService.DEFAULT_EXTENSIONS["voice"]
                elif "." in file_path:
                    extension = file_path.split(".")[-1]
                else:
                    extension = MediaStreamService.DEFAULT_EXTENSIONS.get(
                        media_type, "bin"
                    )

                file_stream.name = f"media.{extension}"

                if should_convert_to_voice(source_media_type, media_type):
                    try:
                        file_stream = convert_stream_to_voice(file_stream)
                        logger.info(
                            "Audio converted to voice",
                            extra={
                                "original_file_id": original_file_id,
                                "bot_id": bot_id,
                                "source_media_type": source_media_type,
                            },
                        )
                    except VoiceConversionError as exc:
                        logger.error(
                            "Failed to convert audio to voice",
                            extra={
                                "file_id": original_file_id,
                                "bot_id": bot_id,
                                "error": str(exc),
                            },
                        )
                        raise

                return (None, file_stream)

        except VoiceConversionError:
            raise
        except Exception as e:
            logger.error(
                "Error downloading media for stream",
                extra={
                    "file_id": original_file_id,
                    "bot_id": bot_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            return (None, None)

    @staticmethod
    async def cache_media_file_id(
        original_file_id: str,
        bot_id: int,
        new_file_id: str,
        media_type: str,
    ):
        """
        Salva file_id no cache após envio bem-sucedido

        Args:
            original_file_id: file_id original do bot gerenciador
            bot_id: ID do bot secundário
            new_file_id: Novo file_id retornado pelo Telegram
            media_type: Tipo de mídia
        """
        await MediaFileCacheRepository.save_cached_file_id(
            original_file_id=original_file_id,
            bot_id=bot_id,
            cached_file_id=new_file_id,
            media_type=media_type,
        )

        logger.info(
            "Media file_id cached",
            extra={
                "original_file_id": original_file_id,
                "bot_id": bot_id,
                "cached_file_id": new_file_id,
                "media_type": media_type,
            },
        )
