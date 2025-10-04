"""
Serviço de efeito de digitação para simular comportamento humano
"""

import asyncio
import math
from typing import List, Optional, Tuple

from core.config import settings
from core.telemetry import logger


class TypingEffectService:
    """Gerencia efeitos de digitação realistas para mensagens do bot"""

    @staticmethod
    def calculate_typing_delay(text: str) -> float:
        """
        Calcula delay natural baseado no comprimento do texto

        Args:
            text: Texto a ser enviado

        Returns:
            Delay em segundos (entre MIN e MAX configurados)
        """
        if not text:
            return settings.MIN_TYPING_DELAY

        # Calcula tempo baseado em caracteres por segundo
        chars_per_second = settings.TYPING_CHARS_PER_MINUTE / 60.0
        natural_delay = len(text) / chars_per_second

        # Aplica limites mínimo e máximo
        delay = min(
            max(natural_delay, settings.MIN_TYPING_DELAY), settings.MAX_TYPING_DELAY
        )

        logger.debug(
            "Typing delay calculated",
            extra={
                "text_length": len(text),
                "natural_delay": round(natural_delay, 2),
                "final_delay": round(delay, 2),
            },
        )

        return delay

    @staticmethod
    def split_message(text: str) -> List[str]:
        """
        Divide mensagem em múltiplas partes usando separador |

        Args:
            text: Texto completo possivelmente com separadores

        Returns:
            Lista de mensagens separadas
        """
        if not text or "|" not in text:
            return [text] if text else []

        # Divide e limpa espaços extras
        parts = [part.strip() for part in text.split("|") if part.strip()]

        logger.debug(
            "Message split",
            extra={"original_length": len(text), "parts_count": len(parts)},
        )

        return parts

    @staticmethod
    def get_action_for_media(media_type: Optional[str]) -> str:
        """
        Retorna a ação apropriada do sendChatAction para o tipo de mídia

        Args:
            media_type: Tipo de mídia (photo, video, audio, etc)

        Returns:
            Ação correspondente para sendChatAction
        """
        action_map = {
            "photo": "upload_photo",
            "video": "upload_video",
            "audio": "upload_audio",
            "voice": "upload_voice",
            "document": "upload_document",
            "animation": "upload_document",  # GIFs são enviados como documento
            "video_note": "upload_video_note",
            "location": "find_location",
            "sticker": "choose_sticker",
        }

        return action_map.get(media_type, "typing")

    @staticmethod
    async def apply_typing_effect(
        api,  # TelegramAPI instance
        token: str,
        chat_id: int,
        text: Optional[str] = None,
        media_type: Optional[str] = None,
        custom_delay: Optional[float] = None,
    ) -> None:
        """
        Aplica efeito de digitação antes de enviar mensagem

        Args:
            api: Instância da TelegramAPI
            token: Token do bot
            chat_id: ID do chat/usuário
            text: Texto da mensagem (para calcular delay)
            media_type: Tipo de mídia sendo enviada
            custom_delay: Delay customizado (ignora cálculo)
        """
        # Determina ação apropriada
        action = TypingEffectService.get_action_for_media(media_type)

        # Calcula ou usa delay customizado
        if custom_delay is not None:
            delay = custom_delay
        else:
            delay = TypingEffectService.calculate_typing_delay(text or "")

        try:
            # Para delays longos, envia ação múltiplas vezes
            if delay > settings.TYPING_ACTION_INTERVAL:
                intervals = math.ceil(delay / settings.TYPING_ACTION_INTERVAL)

                for i in range(intervals):
                    # Envia ação
                    await api.send_chat_action(
                        token=token, chat_id=chat_id, action=action
                    )

                    # Aguarda intervalo (ou resto do delay)
                    if i < intervals - 1:
                        await asyncio.sleep(settings.TYPING_ACTION_INTERVAL)
                    else:
                        remaining = delay - (i * settings.TYPING_ACTION_INTERVAL)
                        if remaining > 0:
                            await asyncio.sleep(remaining)
            else:
                # Delay curto, envia ação uma vez e aguarda
                await api.send_chat_action(token=token, chat_id=chat_id, action=action)
                await asyncio.sleep(delay)

            logger.debug(
                "Typing effect applied",
                extra={
                    "chat_id": chat_id,
                    "action": action,
                    "delay": round(delay, 2),
                    "has_text": bool(text),
                    "media_type": media_type,
                },
            )

        except Exception as e:
            # Não falha se typing effect der erro
            logger.warning(
                "Failed to apply typing effect",
                extra={
                    "chat_id": chat_id,
                    "error": str(e),
                    "action": action,
                },
            )

    @staticmethod
    def apply_typing_effect_sync(
        api,  # TelegramAPI instance
        token: str,
        chat_id: int,
        text: Optional[str] = None,
        media_type: Optional[str] = None,
        custom_delay: Optional[float] = None,
    ) -> None:
        """
        Versão síncrona para uso em workers Celery

        Args:
            api: Instância da TelegramAPI
            token: Token do bot
            chat_id: ID do chat/usuário
            text: Texto da mensagem (para calcular delay)
            media_type: Tipo de mídia sendo enviada
            custom_delay: Delay customizado (ignora cálculo)
        """
        import time

        # Determina ação apropriada
        action = TypingEffectService.get_action_for_media(media_type)

        # Calcula ou usa delay customizado
        if custom_delay is not None:
            delay = custom_delay
        else:
            delay = TypingEffectService.calculate_typing_delay(text or "")

        try:
            # Para delays longos, envia ação múltiplas vezes
            if delay > settings.TYPING_ACTION_INTERVAL:
                intervals = math.ceil(delay / settings.TYPING_ACTION_INTERVAL)

                for i in range(intervals):
                    # Envia ação
                    api.send_chat_action_sync(
                        token=token, chat_id=chat_id, action=action
                    )

                    # Aguarda intervalo (ou resto do delay)
                    if i < intervals - 1:
                        time.sleep(settings.TYPING_ACTION_INTERVAL)
                    else:
                        remaining = delay - (i * settings.TYPING_ACTION_INTERVAL)
                        if remaining > 0:
                            time.sleep(remaining)
            else:
                # Delay curto, envia ação uma vez e aguarda
                api.send_chat_action_sync(token=token, chat_id=chat_id, action=action)
                time.sleep(delay)

            logger.debug(
                "Typing effect applied (sync)",
                extra={
                    "chat_id": chat_id,
                    "action": action,
                    "delay": round(delay, 2),
                    "has_text": bool(text),
                    "media_type": media_type,
                },
            )

        except Exception as e:
            # Não falha se typing effect der erro
            logger.warning(
                "Failed to apply typing effect (sync)",
                extra={
                    "chat_id": chat_id,
                    "error": str(e),
                    "action": action,
                },
            )

    @staticmethod
    async def send_messages_with_typing(
        api,  # TelegramAPI instance
        token: str,
        chat_id: int,
        messages: List[Tuple[str, Optional[str]]],  # List of (text, media_type)
    ) -> None:
        """
        Envia múltiplas mensagens com efeito de digitação entre elas

        Args:
            api: Instância da TelegramAPI
            token: Token do bot
            chat_id: ID do chat/usuário
            messages: Lista de tuplas (texto, tipo_de_mídia)
        """
        for i, (text, media_type) in enumerate(messages):
            # Aplica efeito de digitação
            await TypingEffectService.apply_typing_effect(
                api=api, token=token, chat_id=chat_id, text=text, media_type=media_type
            )

            # Envia mensagem (será implementado pelo chamador)
            # O serviço de typing effect apenas cuida do delay e ação

            logger.debug(
                f"Typing effect for message {i+1}/{len(messages)}",
                extra={
                    "chat_id": chat_id,
                    "message_index": i,
                    "total_messages": len(messages),
                },
            )
