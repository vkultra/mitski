"""
Tasks Celery para verificação automática de pagamentos PIX
"""

from datetime import datetime

from core.redis_client import redis_client
from core.security import decrypt
from core.telemetry import logger
from database.repos import (
    BotRepository,
    OfferDeliverableBlockRepository,
    PixTransactionRepository,
)
from services.gateway.gateway_service import GatewayService
from services.gateway.pushinpay_client import PushinPayClient
from workers.celery_app import celery_app


@celery_app.task
def start_payment_verification(transaction_id: int):
    """
    Inicia verificação automática de pagamento PIX

    Agenda verificações a cada 60 segundos por 10 minutos

    Args:
        transaction_id: ID da transação no banco
    """
    logger.info(
        "Starting automatic payment verification",
        extra={"transaction_id": transaction_id},
    )

    # Agenda 10 verificações (1 por minuto)
    for i in range(10):
        verify_payment_task.apply_async(
            args=[transaction_id], countdown=60 * (i + 1)  # 60s, 120s, ..., 600s
        )


@celery_app.task
def verify_payment_task(transaction_id: int):
    """
    Verifica status de um pagamento específico

    Args:
        transaction_id: ID da transação
    """
    transaction = PixTransactionRepository.get_by_id_sync(transaction_id)

    if not transaction:
        logger.warning(
            "Transaction not found for verification",
            extra={"transaction_id": transaction_id},
        )
        return

    # Se já pago ou entregue, não precisa verificar mais
    if transaction.status == "paid" and transaction.delivered_at:
        logger.info(
            "Transaction already paid and delivered",
            extra={"transaction_id": transaction_id},
        )
        return

    # Se status é final (paid ou expired), não verifica API
    if transaction.status in ["paid", "expired"]:
        # Se pago mas não entregue, tenta entregar
        if transaction.status == "paid" and not transaction.delivered_at:
            deliver_content_sync(transaction_id)
        return

    # Verifica se passou 10 minutos
    if (datetime.utcnow() - transaction.created_at).total_seconds() > 600:
        logger.info(
            "Transaction expired (10 min timeout)",
            extra={"transaction_id": transaction_id},
        )
        PixTransactionRepository.update_status_sync(transaction_id, "expired")
        return

    # Busca bot para pegar admin_id e token
    bot = BotRepository.get_bot_by_id_sync(transaction.bot_id)
    if not bot:
        logger.error(
            "Bot not found for verification",
            extra={"bot_id": transaction.bot_id},
        )
        return

    # Busca token (específico > geral)
    token = GatewayService.get_token_for_bot_sync(bot.admin_id, bot.id)
    if not token:
        logger.warning(
            "No token found for payment verification",
            extra={"bot_id": bot.id, "admin_id": bot.admin_id},
        )
        return

    # Rate limit: 1 requisição por minuto por admin
    lock_key = f"pushinpay:verify:{bot.admin_id}"
    if not redis_client.set(lock_key, "1", nx=True, ex=60):
        logger.info(
            "Rate limit active, skipping verification",
            extra={"admin_id": bot.admin_id, "transaction_id": transaction_id},
        )
        return

    try:
        # Verifica status na API PushinPay
        status_data = PushinPayClient.check_payment_status_sync(
            token, transaction.transaction_id
        )

        current_status = status_data.get("status", "created")

        # Atualiza status se mudou
        if current_status != transaction.status:
            PixTransactionRepository.update_status_sync(transaction_id, current_status)

            logger.info(
                "Payment status updated",
                extra={
                    "transaction_id": transaction_id,
                    "old_status": transaction.status,
                    "new_status": current_status,
                },
            )

        # Se pago, entrega conteúdo
        if current_status == "paid" and not transaction.delivered_at:
            deliver_content_sync(transaction_id)

    except Exception as e:
        logger.error(
            "Error verifying payment",
            extra={"transaction_id": transaction_id, "error": str(e)},
        )


def deliver_content_sync(transaction_id: int) -> bool:
    """
    Entrega conteúdo de forma síncrona (para workers)

    Args:
        transaction_id: ID da transação

    Returns:
        True se entregou com sucesso
    """
    transaction = PixTransactionRepository.get_by_id_sync(transaction_id)

    if not transaction:
        return False

    # Verifica se já entregue
    if transaction.delivered_at:
        logger.info(
            "Content already delivered",
            extra={"transaction_id": transaction_id},
        )
        return True

    # Lock para garantir entrega única
    lock_key = f"pix:deliver:{transaction_id}"
    if not redis_client.set(lock_key, "1", nx=True, ex=300):  # 5min TTL
        logger.info(
            "Delivery already in progress",
            extra={"transaction_id": transaction_id},
        )
        return False

    try:
        # Busca blocos de entregável
        blocks = OfferDeliverableBlockRepository.get_blocks_by_offer_sync(
            transaction.offer_id
        )

        if not blocks:
            logger.warning(
                "No deliverable blocks found",
                extra={"offer_id": transaction.offer_id},
            )
            # Marca como entregue mesmo sem blocos
            PixTransactionRepository.mark_delivered_sync(transaction_id)
            return True

        # Busca bot
        bot = BotRepository.get_bot_by_id_sync(transaction.bot_id)
        if not bot:
            logger.error(
                "Bot not found for delivery",
                extra={"bot_id": transaction.bot_id},
            )
            return False

        # Envia blocos
        from services.offers.deliverable_sender import DeliverableSender

        sender = DeliverableSender(decrypt(bot.token))
        sender.send_deliverable_sync(
            transaction.offer_id, transaction.chat_id, preview_mode=False
        )

        # Marca como entregue
        PixTransactionRepository.mark_delivered_sync(transaction_id)

        logger.info(
            "Content delivered successfully",
            extra={
                "transaction_id": transaction_id,
                "offer_id": transaction.offer_id,
                "blocks_count": len(blocks),
            },
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


@celery_app.task
def verify_all_pending_payments():
    """
    Verifica todos os pagamentos pendentes (task agendada)

    Roda periodicamente para garantir que nenhuma verificação seja perdida
    """
    transactions = PixTransactionRepository.get_pending_for_verification_sync(
        limit_minutes=10
    )

    logger.info(
        "Verifying all pending payments",
        extra={"count": len(transactions)},
    )

    for transaction in transactions:
        verify_payment_task.delay(transaction.id)
