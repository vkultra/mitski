"""
Tasks de processamento de IA para bots secundários
"""

import asyncio

from core.config import settings
from core.telemetry import logger
from services.ai.conversation import AIConversationService
from workers.celery_app import celery_app
from workers.tasks import send_message


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
    3. Chama Grok API (reasoning ou non-reasoning)
    4. Detecta trigger de mudança de fase
    5. Salva no histórico
    6. Retorna resposta ao usuário (SEM reasoning!)

    Args:
        bot_id: ID do bot
        user_telegram_id: ID do usuário no Telegram
        text: Texto da mensagem
        photo_file_ids: Lista de file_ids de fotos
        bot_token: Token do bot (para baixar imagens)
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Processar com IA
        response_text = loop.run_until_complete(
            AIConversationService.process_user_message(
                bot_id=bot_id,
                user_telegram_id=user_telegram_id,
                text=text,
                photo_file_ids=photo_file_ids or [],
                bot_token=bot_token,
                xai_api_key=settings.XAI_API_KEY,
            )
        )

        loop.close()

        # Enviar resposta
        send_message.delay(bot_id, user_telegram_id, response_text)

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
