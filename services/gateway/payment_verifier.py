"""
Verificador de pagamentos e entregador de conteúdo
"""

from typing import Dict

from core.redis_client import redis_client
from core.security import decrypt
from core.telemetry import logger
from database.repos import (
    BotRepository,
    OfferDeliverableBlockRepository,
    PixTransactionRepository,
)
from services.sales import emit_sale_approved

from .gateway_service import GatewayService
from .pushinpay_client import PushinPayClient


class PaymentVerifier:
    """Verifica pagamentos e entrega conteúdo"""

    @staticmethod
    async def verify_payment(transaction_id: int) -> Dict[str, any]:
        """
        Verifica status de um pagamento

        Args:
            transaction_id: ID da transação no banco

        Returns:
            Dict com {status, delivered, transaction}
        """
        transaction = await PixTransactionRepository.get_by_id(transaction_id)

        if not transaction:
            return {"status": "not_found", "delivered": False, "transaction": None}

        # Se já pago e entregue, retorna
        if transaction.status == "paid" and transaction.delivered_at:
            emit_sale_approved(transaction.transaction_id, origin="auto")
            return {"status": "paid", "delivered": True, "transaction": transaction}

        # Se status é final (paid ou expired), não verifica API
        if transaction.status in ["paid", "expired"]:
            if transaction.status == "paid":
                emit_sale_approved(transaction.transaction_id, origin="auto")
            return {
                "status": transaction.status,
                "delivered": transaction.delivered_at is not None,
                "transaction": transaction,
            }

        # Busca token
        bot = await BotRepository.get_bot_by_id(transaction.bot_id)
        if not bot:
            return {"status": "error", "delivered": False, "transaction": transaction}

        token = await GatewayService.get_token_for_bot(bot.admin_id, bot.id)
        if not token:
            return {"status": "error", "delivered": False, "transaction": transaction}

        # Verifica status na API
        try:
            api_status = await PushinPayClient.check_payment_status(
                token, transaction.transaction_id
            )

            # Atualiza status se mudou
            if api_status.get("status") != transaction.status:
                await PixTransactionRepository.update_status(
                    transaction_id, api_status["status"]
                )
                transaction.status = api_status["status"]

            # Se pago, entrega conteúdo
            if api_status["status"] == "paid":
                emit_sale_approved(transaction.transaction_id, origin="auto")
                if not transaction.delivered_at:
                    await PaymentVerifier.deliver_content(transaction_id)
                return {"status": "paid", "delivered": True, "transaction": transaction}

            return {
                "status": api_status["status"],
                "delivered": transaction.delivered_at is not None,
                "transaction": transaction,
            }

        except Exception as e:
            logger.error(
                "Error verifying payment",
                extra={"transaction_id": transaction_id, "error": str(e)},
            )
            return {"status": "error", "delivered": False, "transaction": transaction}

    @staticmethod
    async def deliver_content(transaction_id: int) -> bool:
        """
        Entrega conteúdo para transação paga

        Args:
            transaction_id: ID da transação

        Returns:
            True se entregou com sucesso
        """
        transaction = await PixTransactionRepository.get_by_id(transaction_id)

        if not transaction:
            return False

        # Verifica se já entregue
        if transaction.delivered_at:
            logger.info(
                "Content already delivered",
                extra={"transaction_id": transaction_id},
            )
            return True

        # Redis lock para garantir entrega única
        lock_key = f"pix:deliver:{transaction_id}"
        if not redis_client.set(lock_key, "1", nx=True, ex=300):  # 5min TTL
            logger.info(
                "Content delivery already in progress",
                extra={"transaction_id": transaction_id},
            )
            return False

        try:
            # Busca blocos de entregável
            blocks = await OfferDeliverableBlockRepository.get_blocks_by_offer(
                transaction.offer_id
            )

            if not blocks:
                logger.warning(
                    "No deliverable blocks found",
                    extra={"offer_id": transaction.offer_id},
                )
                # Marca como entregue mesmo sem blocos
                await PixTransactionRepository.mark_delivered(transaction_id)
                return True

            # Busca bot para enviar mensagens
            bot = await BotRepository.get_bot_by_id(transaction.bot_id)
            if not bot:
                logger.error(
                    "Bot not found for delivery",
                    extra={"bot_id": transaction.bot_id},
                )
                return False

            # Importa sender aqui para evitar import circular
            from services.offers.deliverable_sender import DeliverableSender

            # Envia blocos de entregável
            sender = DeliverableSender(decrypt(bot.token))
            await sender.send_deliverable(
                transaction.offer_id,
                transaction.chat_id,
                preview_mode=False,
                bot_id=bot.id,
            )

            # Marca como entregue
            await PixTransactionRepository.mark_delivered(transaction_id)

            logger.info(
                "Content delivered successfully",
                extra={
                    "transaction_id": transaction_id,
                    "offer_id": transaction.offer_id,
                    "blocks_count": len(blocks),
                },
            )

            # Ativar fluxo de upsell se for primeiro pagamento
            from workers.upsell_tasks import activate_upsell_flow

            activate_upsell_flow.delay(
                user_id=transaction.user_telegram_id,
                bot_id=transaction.bot_id,
                transaction_id=transaction_id,
            )

            return True

        except Exception as e:
            logger.error(
                "Error delivering content",
                extra={"transaction_id": transaction_id, "error": str(e)},
            )
            return False

        finally:
            redis_client.delete(lock_key)

    @staticmethod
    def deliver_content_sync(transaction_id: int) -> bool:
        """
        Versão síncrona para workers Celery

        Args:
            transaction_id: ID da transação

        Returns:
            True se entregou com sucesso
        """
        transaction = PixTransactionRepository.get_by_id_sync(transaction_id)

        if not transaction or transaction.delivered_at:
            return True

        # Lock para entrega única
        lock_key = f"pix:deliver:{transaction_id}"
        if not redis_client.set(lock_key, "1", nx=True, ex=300):
            return False

        try:
            blocks = OfferDeliverableBlockRepository.get_blocks_by_offer_sync(
                transaction.offer_id
            )

            if not blocks:
                PixTransactionRepository.mark_delivered_sync(transaction_id)
                return True

            bot = BotRepository.get_bot_by_id_sync(transaction.bot_id)
            if not bot:
                return False

            # Importa sender
            from services.offers.deliverable_sender import DeliverableSender

            sender = DeliverableSender(decrypt(bot.token))
            sender.send_deliverable_sync(
                transaction.offer_id, transaction.chat_id, preview_mode=False
            )

            PixTransactionRepository.mark_delivered_sync(transaction_id)

            logger.info(
                "Content delivered (sync)",
                extra={"transaction_id": transaction_id},
            )

            return True

        except Exception as e:
            logger.error(
                "Error delivering content (sync)",
                extra={"transaction_id": transaction_id, "error": str(e)},
            )
            return False

        finally:
            redis_client.delete(lock_key)

    @staticmethod
    async def send_manual_verification_message(
        offer_id: int, chat_id: int, bot_token: str, bot_id: int = None
    ) -> bool:
        """
        Envia mensagem de verificação manual

        Args:
            offer_id: ID da oferta
            chat_id: ID do chat
            bot_token: Token do bot
            bot_id: ID do bot (para cache de mídia)

        Returns:
            True se enviou com sucesso
        """
        try:
            # Importa sender
            from services.offers.manual_verification_sender import (
                ManualVerificationSender,
            )

            sender = ManualVerificationSender(bot_token)
            await sender.send_manual_verification(offer_id, chat_id, bot_id=bot_id)

            logger.info(
                "Manual verification message sent",
                extra={"offer_id": offer_id, "chat_id": chat_id},
            )

            return True

        except Exception as e:
            logger.error(
                "Error sending manual verification",
                extra={"offer_id": offer_id, "chat_id": chat_id, "error": str(e)},
            )
            return False
