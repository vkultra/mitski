"""
Processamento de imagens para Grok API
"""

import base64
from typing import Any, Dict, List

import httpx

from core.telemetry import logger


class ImageHandler:
    """Processa imagens do Telegram para envio ao Grok API"""

    @staticmethod
    async def download_telegram_photo(file_id: str, bot_token: str) -> bytes:
        """
        Baixa foto do Telegram via API

        Args:
            file_id: ID do arquivo no Telegram
            bot_token: Token do bot

        Returns:
            bytes da imagem
        """
        try:
            async with httpx.AsyncClient() as client:
                # 1. Obter file_path
                file_info_response = await client.get(
                    f"https://api.telegram.org/bot{bot_token}/getFile",
                    params={"file_id": file_id},
                )
                file_info_response.raise_for_status()
                file_info = file_info_response.json()

                if not file_info.get("ok"):
                    raise ValueError(f"Failed to get file info: {file_info}")

                file_path = file_info["result"]["file_path"]

                # 2. Baixar arquivo
                file_response = await client.get(
                    f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
                )
                file_response.raise_for_status()

                logger.info(
                    "Telegram photo downloaded",
                    extra={"file_id": file_id, "size": len(file_response.content)},
                )

                return file_response.content

        except Exception as e:
            logger.error(
                "Failed to download Telegram photo",
                extra={"file_id": file_id, "error": str(e)},
            )
            raise

    @staticmethod
    def convert_to_base64(image_bytes: bytes) -> str:
        """
        Converte bytes de imagem para base64 (data URL)

        Args:
            image_bytes: bytes da imagem

        Returns:
            String no formato "data:image/jpeg;base64,..."
        """
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:image/jpeg;base64,{b64}"

    @staticmethod
    def create_multimodal_message(text: str, image_urls: List[str]) -> Dict[str, Any]:
        """
        Cria mensagem multimodal para Grok API

        Formato da API Grok para visão:
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "O que há nesta imagem?"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
            ]
        }

        Args:
            text: Texto da mensagem
            image_urls: Lista de URLs de imagens (base64 ou HTTP)

        Returns:
            Dict no formato esperado pela API
        """
        content = []

        # Adiciona texto primeiro
        if text:
            content.append({"type": "text", "text": text})

        # Adiciona imagens
        for image_url in image_urls:
            content.append({"type": "image_url", "image_url": {"url": image_url}})

        return {"role": "user", "content": content}

    @staticmethod
    def create_text_only_message(text: str) -> Dict[str, Any]:
        """
        Cria mensagem apenas de texto

        Args:
            text: Texto da mensagem

        Returns:
            {"role": "user", "content": "..."}
        """
        return {"role": "user", "content": text}
