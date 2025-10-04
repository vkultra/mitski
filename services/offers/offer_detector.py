"""
Serviço de detecção de ofertas em mensagens
"""

import re
from typing import TYPE_CHECKING, List, Optional, Tuple

from core.telemetry import logger
from database.repos import OfferRepository

if TYPE_CHECKING:
    from database.models import Offer


class OfferDetectorService:
    """Detecta ofertas mencionadas em mensagens"""

    @staticmethod
    async def detect_offers(bot_id: int, message: str) -> List[Tuple[str, "Offer"]]:
        """
        Detecta todas as ofertas mencionadas em uma mensagem

        Args:
            bot_id: ID do bot
            message: Mensagem para analisar

        Returns:
            Lista de tuplas (nome_detectado, oferta)
        """
        if not message:
            return []

        # Buscar ofertas ativas do bot
        offers = await OfferRepository.get_offers_by_bot(bot_id, active_only=True)

        if not offers:
            return []

        detected = []

        for offer in offers:
            # Verificar se o nome da oferta está na mensagem (case-insensitive)
            # Suporta detecção mesmo entre palavras ou colado
            pattern = re.compile(re.escape(offer.name), re.IGNORECASE)

            if pattern.search(message):
                detected.append((offer.name, offer))
                logger.info(
                    "Offer detected in message",
                    extra={
                        "bot_id": bot_id,
                        "offer_id": offer.id,
                        "offer_name": offer.name,
                        "message_preview": message[:100],
                    },
                )

        return detected

    @staticmethod
    async def get_first_offer_detected(bot_id: int, message: str) -> Optional["Offer"]:
        """
        Retorna a primeira oferta detectada na mensagem

        Args:
            bot_id: ID do bot
            message: Mensagem para analisar

        Returns:
            Primeira oferta detectada ou None
        """
        detected = await OfferDetectorService.detect_offers(bot_id, message)

        if detected:
            return detected[0][1]  # Retorna a oferta (segundo elemento da tupla)

        return None

    @staticmethod
    def should_replace_message(message: str, offer_name: str) -> bool:
        """
        Verifica se a mensagem deve ser substituída pelo pitch

        Regra: Se a mensagem contém APENAS o nome da oferta (com possível pontuação),
        substitui completamente. Caso contrário, adiciona o pitch após a mensagem.

        Args:
            message: Mensagem original
            offer_name: Nome da oferta detectada

        Returns:
            True se deve substituir, False se deve adicionar
        """
        # Remove pontuação e espaços extras
        clean_message = re.sub(r"[^\w\s]", "", message).strip()
        clean_offer = re.sub(r"[^\w\s]", "", offer_name).strip()

        # Se a mensagem limpa é igual ao nome da oferta limpo, substitui
        return clean_message.lower() == clean_offer.lower()

    @staticmethod
    def extract_offer_names(offers: List["Offer"]) -> List[str]:
        """
        Extrai nomes das ofertas para cache

        Args:
            offers: Lista de ofertas

        Returns:
            Lista de nomes de ofertas
        """
        return [offer.name for offer in offers]
