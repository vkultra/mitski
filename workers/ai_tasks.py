"""
Tasks de processamento de IA para bots secundários
"""

import asyncio

from core.config import settings
from core.telemetry import logger
from services.ai.conversation import AIConversationService
from workers.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3)
def process_ai_message(
    self,
    bot_id: int,
    user_telegram_id: int,
    text: str,
    photo_file_ids: list = None,
    bot_token: str = None,
):
    """
    Processa mensagem do usuário com IA Grok

    Fluxo:
    1. Busca histórico e configuração
    2. Monta payload com system prompt + fase + histórico
    3. Chama Grok API (reasoning ou non-reasoning) com concorrência
    4. Detecta trigger de mudança de fase
    5. Salva no histórico
    6. Retorna resposta ao usuário (SEM reasoning!)

    Args:
        bot_id: ID do bot
        user_telegram_id: ID do usuário no Telegram
        text: Texto da mensagem
        photo_file_ids: Lista de file_ids de fotos
        bot_token: Token do bot (para baixar imagens)

    Note:
        Usa asyncio.run() para executar código assíncrono
    """
    try:
        # Processar com IA usando asyncio.run()
        response_text = asyncio.run(
            AIConversationService.process_user_message(
                bot_id=bot_id,
                user_telegram_id=user_telegram_id,
                text=text,
                photo_file_ids=photo_file_ids or [],
                bot_token=bot_token,
                xai_api_key=settings.XAI_API_KEY,
            )
        )

        # Verificar se há oferta detectada no sufixo
        offer_id_to_send = None
        if response_text and "__OFFER_DETECTED:" in response_text:
            # Extrair ID da oferta do sufixo
            import re

            match = re.search(r"__OFFER_DETECTED:(\d+)__", response_text)
            if match:
                offer_id_to_send = int(match.group(1))
                # Remover sufixo da mensagem antes de enviar
                response_text = re.sub(r"__OFFER_DETECTED:\d+__", "", response_text)

        # Verificar se há ação detectada no sufixo
        action_id_to_send = None
        if response_text and "__ACTION_DETECTED:" in response_text:
            # Extrair ID da ação do sufixo
            import re

            match = re.search(r"__ACTION_DETECTED:(\d+)__", response_text)
            if match:
                action_id_to_send = int(match.group(1))
                # Remover sufixo da mensagem antes de enviar
                response_text = re.sub(r"__ACTION_DETECTED:\d+__", "", response_text)

        # Enviar resposta (import aqui para evitar circular import)
        from workers.tasks import send_message

        send_message.delay(bot_id, user_telegram_id, response_text)

        # Se há oferta para enviar, enviar pitch após a mensagem
        if offer_id_to_send:
            from services.offers.offer_service import OfferService

            asyncio.run(
                OfferService.send_pitch_after_message(
                    offer_id=offer_id_to_send,
                    chat_id=user_telegram_id,
                    bot_token=bot_token,
                    bot_id=bot_id,
                    user_telegram_id=user_telegram_id,
                )
            )

        # Se há ação para enviar, enviar blocos após a mensagem
        if action_id_to_send:
            from services.ai.actions import ActionService

            asyncio.run(
                ActionService.send_action_blocks_after_message(
                    action_id=action_id_to_send,
                    chat_id=user_telegram_id,
                    bot_token=bot_token,
                    bot_id=bot_id,
                )
            )

        logger.info(
            "AI message processed successfully",
            extra={
                "bot_id": bot_id,
                "user_id": user_telegram_id,
                "response_length": len(response_text),
            },
        )

    except Exception as exc:
        logger.error(
            "AI message processing failed",
            extra={
                "bot_id": bot_id,
                "user_id": user_telegram_id,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
        )

        # Retry com backoff exponencial
        raise self.retry(exc=exc, countdown=2**self.request.retries, max_retries=3)
