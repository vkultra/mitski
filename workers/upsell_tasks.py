"""
Tasks Celery para sistema de Upsell
"""

import asyncio
from datetime import datetime

from core.security import decrypt
from core.telemetry import logger
from database.repos import (
    BotRepository,
    PixTransactionRepository,
    UpsellRepository,
    UserUpsellHistoryRepository,
)
from services.upsell import (
    AnnouncementSender,
    DeliverableSender,
    UpsellScheduler,
    UpsellService,
)
from workers.celery_app import celery_app


@celery_app.task
def activate_upsell_flow(user_id: int, bot_id: int, transaction_id: int):
    """
    Ativa fluxo de upsell após primeiro pagamento

    Chamado por: payment_verifier.deliver_content()

    Args:
        user_id: ID do usuário no Telegram
        bot_id: ID do bot
        transaction_id: ID da transação PIX
    """
    logger.info(
        "Activating upsell flow",
        extra={"user_id": user_id, "bot_id": bot_id, "transaction_id": transaction_id},
    )

    # Verificar se é primeiro pagamento (não tem histórico de upsell)
    history = UserUpsellHistoryRepository.get_user_history_sync(bot_id, user_id)
    if history:
        logger.info(
            "User already in upsell flow", extra={"user_id": user_id, "bot_id": bot_id}
        )
        return

    # Buscar upsell #1
    upsell_1 = UpsellRepository.get_first_upsell_sync(bot_id)
    if not upsell_1:
        logger.info("No default upsell found", extra={"bot_id": bot_id})
        return

    # Verificar se está completo
    if not UpsellService.is_upsell_complete_sync(upsell_1.id):
        logger.info(
            "Upsell not complete, ignoring",
            extra={"upsell_id": upsell_1.id, "bot_id": bot_id},
        )
        return

    # TROCAR PROMPT IMEDIATAMENTE
    from services.upsell import UpsellPhaseManager

    UpsellPhaseManager.activate_upsell_phase_sync(bot_id, user_id, upsell_1.id)

    # Registrar no histórico (sent_at=NULL pois aguarda trigger da IA)
    from database.models import UserUpsellHistory
    from database.repos import SessionLocal

    with SessionLocal() as session:
        history_record = UserUpsellHistory(
            bot_id=bot_id,
            user_telegram_id=user_id,
            upsell_id=upsell_1.id,
            sent_at=None,  # Será preenchido quando IA mencionar trigger
        )
        session.add(history_record)
        session.commit()

    logger.info(
        "Upsell flow activated",
        extra={"user_id": user_id, "bot_id": bot_id, "upsell_id": upsell_1.id},
    )


@celery_app.task
def send_upsell_announcement_triggered(bot_id: int, user_id: int, upsell_id: int):
    """
    Envia anúncio do upsell #1 quando IA menciona trigger

    Chamado por: conversation.py ao detectar trigger

    Args:
        bot_id: ID do bot
        user_id: ID do usuário no Telegram
        upsell_id: ID do upsell
    """
    logger.info(
        "Sending triggered upsell announcement",
        extra={"user_id": user_id, "bot_id": bot_id, "upsell_id": upsell_id},
    )

    # Buscar bot
    bot = BotRepository.get_bot_by_id_sync(bot_id)
    if not bot:
        logger.error("Bot not found", extra={"bot_id": bot_id})
        return

    # Enviar anúncio
    sender = AnnouncementSender(decrypt(bot.token))
    sender.send_announcement_sync(upsell_id, user_id, bot_id)

    # Marcar como enviado
    UserUpsellHistoryRepository.mark_sent_sync(bot_id, user_id, upsell_id)

    logger.info(
        "Upsell announcement sent",
        extra={"user_id": user_id, "bot_id": bot_id, "upsell_id": upsell_id},
    )


@celery_app.task
def check_pending_upsells():
    """
    Verifica upsells agendados prontos para envio

    Executado: A cada 5 minutos via Celery Beat

    Para cada upsell pronto:
    - Envia anúncio
    - Troca prompt da IA
    """
    logger.info("Checking pending upsells")

    current_time = datetime.utcnow()
    pending = UpsellScheduler.get_pending_upsells_sync(current_time)

    if not pending:
        logger.info("No pending upsells")
        return

    logger.info(f"Found {len(pending)} pending upsells")

    for user_id, bot_id, upsell_id in pending:
        send_scheduled_upsell.delay(user_id, bot_id, upsell_id)


@celery_app.task
def send_scheduled_upsell(user_id: int, bot_id: int, upsell_id: int):
    """
    Envia upsell agendado (#2+)

    Args:
        user_id: ID do usuário
        bot_id: ID do bot
        upsell_id: ID do upsell
    """
    logger.info(
        "Sending scheduled upsell",
        extra={"user_id": user_id, "bot_id": bot_id, "upsell_id": upsell_id},
    )

    # Buscar bot e upsell
    bot = BotRepository.get_bot_by_id_sync(bot_id)
    upsell = UpsellRepository.get_upsell_by_id_sync(upsell_id)

    if not bot or not upsell:
        logger.error(
            "Bot or upsell not found", extra={"bot_id": bot_id, "upsell_id": upsell_id}
        )
        return

    # TROCAR PROMPT AGORA
    from services.upsell import UpsellPhaseManager

    UpsellPhaseManager.activate_upsell_phase_sync(bot_id, user_id, upsell_id)

    # Enviar anúncio
    sender = AnnouncementSender(decrypt(bot.token))
    sender.send_announcement_sync(upsell_id, user_id, bot_id)

    # Marcar como enviado
    UserUpsellHistoryRepository.mark_sent_sync(bot_id, user_id, upsell_id)

    logger.info(
        "Scheduled upsell sent",
        extra={"user_id": user_id, "bot_id": bot_id, "upsell_id": upsell_id},
    )


@celery_app.task
def process_upsell_payment(transaction_id: int):
    """
    Processa pagamento de upsell e entrega conteúdo

    Chamado por: payment_verifier ao detectar pagamento

    Args:
        transaction_id: ID da transação PIX
    """
    logger.info("Processing upsell payment", extra={"transaction_id": transaction_id})

    # Buscar transação
    transaction = PixTransactionRepository.get_by_id_sync(transaction_id)

    if not transaction:
        logger.error("Transaction not found", extra={"transaction_id": transaction_id})
        return

    # Verificar se é transação de upsell
    if not transaction.upsell_id:
        logger.warning(
            "Transaction has no upsell_id",
            extra={"transaction_id": transaction_id},
        )
        return

    upsell_id = transaction.upsell_id

    # Entregar deliverable
    bot = BotRepository.get_bot_by_id_sync(transaction.bot_id)
    if not bot:
        logger.error("Bot not found", extra={"bot_id": transaction.bot_id})
        return

    sender = DeliverableSender(decrypt(bot.token))

    sender.send_deliverable_sync(
        upsell_id=upsell_id, chat_id=transaction.chat_id, bot_id=bot.id
    )

    # Marcar como pago
    UserUpsellHistoryRepository.mark_paid_sync(
        bot_id=transaction.bot_id,
        user_telegram_id=transaction.user_telegram_id,
        upsell_id=upsell_id,
        transaction_id=transaction.transaction_id,
    )

    # Agendar próximo upsell
    UpsellScheduler.schedule_next_upsell_sync(
        transaction.user_telegram_id, transaction.bot_id
    )

    logger.info(
        "Upsell payment processed",
        extra={"transaction_id": transaction_id, "upsell_id": upsell_id},
    )


@celery_app.task
def verify_upsell_payment(transaction_id: int, attempt: int = 1):
    """
    Verifica pagamento de upsell automaticamente

    Chamada a cada 60 segundos por até 10 minutos (10 tentativas)

    Args:
        transaction_id: ID da transação PIX
        attempt: Número da tentativa atual (1-10)
    """
    MAX_ATTEMPTS = 10  # 10 tentativas = 10 minutos (60s * 10)

    logger.info(
        "Verifying upsell payment",
        extra={"transaction_id": transaction_id, "attempt": attempt},
    )

    # Buscar transação
    transaction = PixTransactionRepository.get_by_id_sync(transaction_id)

    if not transaction:
        logger.error("Transaction not found", extra={"transaction_id": transaction_id})
        return

    # Se já foi paga, não fazer nada
    if transaction.status == "paid":
        logger.info(
            "Transaction already paid",
            extra={"transaction_id": transaction_id},
        )
        return

    # Verificar pagamento via API do gateway
    from services.gateway.payment_verifier import PaymentVerifier

    payment_status = asyncio.run(PaymentVerifier.verify_payment(transaction_id))

    if payment_status.get("status") == "paid":
        # Pagamento confirmado - processar entrega
        logger.info(
            "Upsell payment confirmed",
            extra={
                "transaction_id": transaction_id,
                "attempt": attempt,
            },
        )

        # Entregar deliverable
        bot = BotRepository.get_bot_by_id_sync(transaction.bot_id)
        if not bot:
            logger.error("Bot not found", extra={"bot_id": transaction.bot_id})
            return

        sender = DeliverableSender(decrypt(bot.token))

        # Agora usamos transaction.upsell_id diretamente
        sender.send_deliverable_sync(
            upsell_id=transaction.upsell_id,
            chat_id=transaction.chat_id,
            bot_id=bot.id,
        )

        # Marcar como pago
        UserUpsellHistoryRepository.mark_paid_sync(
            bot_id=transaction.bot_id,
            user_telegram_id=transaction.user_telegram_id,
            upsell_id=transaction.upsell_id,
            transaction_id=transaction.transaction_id,
        )

        # Agendar próximo upsell
        UpsellScheduler.schedule_next_upsell_sync(
            transaction.user_telegram_id, transaction.bot_id
        )

        logger.info(
            "Upsell delivered automatically",
            extra={
                "transaction_id": transaction_id,
                "upsell_id": transaction.upsell_id,
            },
        )

    elif attempt < MAX_ATTEMPTS:
        # Ainda não pago e ainda há tentativas - agendar próxima verificação
        logger.info(
            "Payment not confirmed yet, scheduling next check",
            extra={
                "transaction_id": transaction_id,
                "attempt": attempt,
                "next_attempt": attempt + 1,
            },
        )

        verify_upsell_payment.apply_async(
            args=[transaction_id, attempt + 1], countdown=60
        )
    else:
        # Atingiu limite de tentativas sem pagamento
        logger.warning(
            "Max verification attempts reached without payment",
            extra={"transaction_id": transaction_id, "attempts": MAX_ATTEMPTS},
        )
