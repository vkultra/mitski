"""
Processador de tags PIX e geração de chaves
"""

import re
from typing import Optional, Tuple

from core.telemetry import logger
from database.repos import BotRepository, OfferRepository, PixTransactionRepository

from .gateway_service import GatewayService
from .pushinpay_client import PushinPayClient


class PixProcessor:
    """Processa tags {pix} e gera chaves PIX"""

    @staticmethod
    def has_pix_tag(text: Optional[str]) -> bool:
        """
        Verifica se texto contém tag {pix}

        Args:
            text: Texto a verificar

        Returns:
            True se contém {pix}
        """
        if not text:
            return False
        return "{pix}" in text.lower()

    @staticmethod
    async def process_block_with_pix(
        text: str, offer_id: int, bot_id: int, chat_id: int, user_telegram_id: int
    ) -> Tuple[str, Optional[any]]:
        """
        Processa texto com tag {pix}, substituindo por chave gerada

        Args:
            text: Texto contendo {pix}
            offer_id: ID da oferta
            bot_id: ID do bot
            chat_id: ID do chat
            user_telegram_id: ID do usuário no Telegram

        Returns:
            Tupla (texto_processado, transaction ou None)
        """
        if not PixProcessor.has_pix_tag(text):
            return text, None

        try:
            # Gera PIX
            transaction = await PixProcessor.generate_pix_for_offer(
                offer_id, bot_id, user_telegram_id, chat_id
            )

            if not transaction:
                logger.error(
                    "Failed to generate PIX",
                    extra={
                        "offer_id": offer_id,
                        "bot_id": bot_id,
                        "chat_id": chat_id,
                    },
                )
                # Retorna texto original se falhar
                return text, None

            # Formata chave PIX
            formatted_pix = PixProcessor.format_pix_code(transaction.qr_code)

            # Substitui {pix} pela chave formatada (case-insensitive)
            processed_text = re.sub(
                r"\{pix\}", formatted_pix, text, flags=re.IGNORECASE
            )

            logger.info(
                "PIX tag processed successfully",
                extra={
                    "transaction_id": transaction.id,
                    "offer_id": offer_id,
                    "chat_id": chat_id,
                },
            )

            return processed_text, transaction

        except Exception as e:
            logger.error(
                "Error processing PIX tag",
                extra={
                    "error": str(e),
                    "offer_id": offer_id,
                    "chat_id": chat_id,
                },
            )
            return text, None

    @staticmethod
    async def generate_pix_for_offer(
        offer_id: int, bot_id: int, user_telegram_id: int, chat_id: int
    ):
        """
        Gera PIX para uma oferta

        Args:
            offer_id: ID da oferta
            bot_id: ID do bot
            user_telegram_id: ID do usuário
            chat_id: ID do chat

        Returns:
            PixTransaction criada ou None
        """
        # Busca oferta
        offer = await OfferRepository.get_offer_by_id(offer_id)
        if not offer or not offer.value:
            logger.warning(
                "Offer not found or has no value",
                extra={"offer_id": offer_id},
            )
            return None

        # Converte valor para centavos
        value_cents = PixProcessor.extract_value_in_cents(offer.value)
        if value_cents < 50:
            logger.warning(
                "Offer value below minimum",
                extra={"offer_id": offer_id, "value_cents": value_cents},
            )
            return None

        # Busca bot para pegar admin_id
        bot = await BotRepository.get_bot_by_id(bot_id)
        if not bot:
            logger.error("Bot not found", extra={"bot_id": bot_id})
            return None

        # Busca token (específico > geral)
        token = await GatewayService.get_token_for_bot(bot.admin_id, bot_id)
        if not token:
            logger.warning(
                "No gateway token configured",
                extra={"bot_id": bot_id, "admin_id": bot.admin_id},
            )
            return None

        try:
            # Cria PIX via API
            pix_data = await PushinPayClient.create_pix(token, value_cents)

            # Salva transação no banco
            transaction = await PixTransactionRepository.create_transaction(
                bot_id=bot_id,
                user_telegram_id=user_telegram_id,
                chat_id=chat_id,
                offer_id=offer_id,
                transaction_id=str(pix_data["id"]),
                qr_code=pix_data["qr_code"],
                value_cents=value_cents,
                qr_code_base64=pix_data.get("qr_code_base64"),
            )

            logger.info(
                "PIX generated and saved",
                extra={
                    "transaction_id": transaction.id,
                    "pushinpay_id": pix_data["id"],
                    "value_cents": value_cents,
                },
            )

            return transaction

        except Exception as e:
            logger.error(
                "Error generating PIX",
                extra={
                    "error": str(e),
                    "offer_id": offer_id,
                    "value_cents": value_cents,
                },
            )
            return None

    @staticmethod
    def format_pix_code(qr_code: str) -> str:
        """
        Formata chave PIX em markdown

        Args:
            qr_code: Chave PIX copia e cola

        Returns:
            Chave formatada: `chave_pix`
        """
        return f"`{qr_code}`"

    @staticmethod
    def extract_value_in_cents(value_str: str) -> int:
        """
        Extrai valor em centavos de string formatada

        Args:
            value_str: String com valor (ex: "R$ 7,90", "R$ 15", "7.90")

        Returns:
            Valor em centavos

        Examples:
            "R$ 7,90" -> 790
            "R$ 15" -> 1500
            "R$ 15,00" -> 1500
            "7.90" -> 790
        """
        # Remove símbolos e espaços
        cleaned = re.sub(r"[R$\s]", "", value_str)

        # Se tem vírgula, assume formato BR (7,90)
        if "," in cleaned:
            cleaned = cleaned.replace(".", "")  # Remove separador de milhar
            cleaned = cleaned.replace(",", ".")  # Troca vírgula por ponto

        # Converte para float e depois para centavos
        try:
            value_float = float(cleaned)
            value_cents = int(value_float * 100)
            return value_cents
        except ValueError:
            logger.error(
                "Failed to parse value",
                extra={"value_str": value_str, "cleaned": cleaned},
            )
            return 0
