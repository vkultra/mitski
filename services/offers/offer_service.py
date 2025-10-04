"""
Serviço principal de ofertas
"""

from typing import Dict, Optional

from core.telemetry import logger
from database.repos import OfferRepository

from .offer_detector import OfferDetectorService
from .pitch_sender import PitchSenderService


class OfferService:
    """Serviço principal para gerenciar ofertas"""

    @staticmethod
    async def process_ai_message_for_offers(
        bot_id: int,
        chat_id: int,
        ai_message: str,
        bot_token: str,
        user_telegram_id: Optional[int] = None,
    ) -> Optional[Dict]:
        """
        Processa mensagem da IA para detectar e substituir ofertas

        Args:
            bot_id: ID do bot
            chat_id: ID do chat/usuário
            ai_message: Mensagem gerada pela IA
            bot_token: Token do bot
            user_telegram_id: ID do usuário no Telegram (para {pix})

        Returns:
            Dict com informações da oferta processada ou None
        """
        # Detectar ofertas na mensagem
        offer = await OfferDetectorService.get_first_offer_detected(bot_id, ai_message)

        if not offer:
            return None

        logger.info(
            "Processing offer in AI message",
            extra={
                "bot_id": bot_id,
                "chat_id": chat_id,
                "offer_id": offer.id,
                "offer_name": offer.name,
            },
        )

        # Verificar se deve substituir ou adicionar
        should_replace = OfferDetectorService.should_replace_message(
            ai_message, offer.name
        )

        # Inicializar sender
        sender = PitchSenderService(bot_token)

        # Se deve substituir completamente, não enviar a mensagem original
        if should_replace:
            # Enviar apenas o pitch
            message_ids = await sender.send_pitch(
                offer.id, chat_id, bot_id=bot_id, user_telegram_id=user_telegram_id
            )

            return {
                "offer_detected": True,
                "offer_id": offer.id,
                "offer_name": offer.name,
                "replaced_message": True,
                "messages_sent": len(message_ids),
            }

        # Se não deve substituir, retornar que a oferta foi detectada
        # mas deixar o sistema enviar a mensagem original primeiro
        return {
            "offer_detected": True,
            "offer_id": offer.id,
            "offer_name": offer.name,
            "replaced_message": False,
            "should_append_pitch": True,
        }

    @staticmethod
    async def send_pitch_after_message(
        offer_id: int,
        chat_id: int,
        bot_token: str,
        bot_id: Optional[int] = None,
        user_telegram_id: Optional[int] = None,
    ) -> int:
        """
        Envia pitch após mensagem original

        Args:
            offer_id: ID da oferta
            chat_id: ID do chat
            bot_token: Token do bot
            bot_id: ID do bot (para cache de mídia)
            user_telegram_id: ID do usuário no Telegram (para {pix})

        Returns:
            Número de mensagens enviadas
        """
        sender = PitchSenderService(bot_token)
        message_ids = await sender.send_pitch(
            offer_id, chat_id, bot_id=bot_id, user_telegram_id=user_telegram_id
        )

        return len(message_ids)

    @staticmethod
    async def validate_offer_creation(
        bot_id: int,
        name: str,
    ) -> Dict[str, any]:
        """
        Valida criação de nova oferta

        Args:
            bot_id: ID do bot
            name: Nome da oferta

        Returns:
            Dict com resultado da validação
        """
        # Verificar se já existe
        existing = await OfferRepository.get_offer_by_name(bot_id, name)

        if existing:
            return {
                "valid": False,
                "error": "Já existe uma oferta com este nome",
            }

        # Validar comprimento
        if len(name) < 2:
            return {
                "valid": False,
                "error": "Nome muito curto (mínimo 2 caracteres)",
            }

        if len(name) > 128:
            return {
                "valid": False,
                "error": "Nome muito longo (máximo 128 caracteres)",
            }

        return {"valid": True}

    @staticmethod
    async def format_offer_value(value: str) -> str:
        """
        Formata valor da oferta

        Args:
            value: Valor inserido pelo usuário

        Returns:
            Valor formatado
        """
        # Remove espaços extras
        value = value.strip()

        # Se não começa com R$, adicionar
        if not value.startswith("R$"):
            # Tentar identificar se é um número
            import re

            # Remove tudo exceto números, vírgula e ponto
            clean = re.sub(r"[^\d,.]", "", value)

            if clean:
                # Substitui ponto por vírgula se necessário
                clean = clean.replace(".", ",")

                # Adiciona R$
                value = f"R$ {clean}"

        return value

    @staticmethod
    async def get_offer_statistics(offer_id: int) -> Dict:
        """
        Obtém estatísticas de uma oferta

        Args:
            offer_id: ID da oferta

        Returns:
            Dict com estatísticas
        """
        from database.repos import OfferPitchRepository

        offer = await OfferRepository.get_offer_by_id(offer_id)
        blocks = await OfferPitchRepository.get_blocks_by_offer(offer_id)

        if not offer:
            return {}

        # Calcular estatísticas
        total_delay = sum(block.delay_seconds for block in blocks)
        has_media = any(block.media_file_id for block in blocks)
        has_auto_delete = any(block.auto_delete_seconds > 0 for block in blocks)

        return {
            "offer_name": offer.name,
            "offer_value": offer.value,
            "total_blocks": len(blocks),
            "total_delay_seconds": total_delay,
            "has_media": has_media,
            "has_auto_delete": has_auto_delete,
            "created_at": offer.created_at,
            "is_active": offer.is_active,
        }
