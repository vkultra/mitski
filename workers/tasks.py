"""
Tasks assíncronas do Celery
"""
from .celery_app import celery_app
from database.repos import BotRepository
from core.rate_limiter import check_rate_limit
from core.security import decrypt
from core.telemetry import logger
import requests


@celery_app.task(bind=True, max_retries=3)
def process_telegram_update(self, bot_id: int, update: dict):
    """Processa update de bot secundário"""
    bot = BotRepository.get_bot_by_id_sync(bot_id)
    if not bot or not bot.is_active:
        logger.warning("Bot inactive or not found", extra={"bot_id": bot_id})
        return

    message = update.get('message', {})
    user_id = message.get('from', {}).get('id')

    if not user_id:
        return

    # Rate limit por bot + usuário
    if not check_rate_limit(bot_id, user_id):
        send_rate_limit_message.delay(bot.id, user_id)
        return

    text = message.get('text', '')

    # Roteamento de comandos
    if text == '/start':
        send_welcome.delay(bot.id, user_id)
    elif text.startswith('/api'):
        call_external_api.delay(bot_id, user_id, text)


@celery_app.task(bind=True, max_retries=3)
def process_manager_update(self, update: dict):
    """Processa update do bot gerenciador"""
    from handlers.manager_handlers import (
        handle_start, handle_callback_add_bot,
        handle_callback_list_bots, handle_callback_deactivate_menu,
        handle_deactivate, handle_register
    )
    from workers.api_clients import TelegramAPI
    import os
    import asyncio

    telegram_api = TelegramAPI()
    manager_token = os.environ.get("MANAGER_BOT_TOKEN")

    # Processar callback query
    callback_query = update.get('callback_query')
    if callback_query:
        user_id = callback_query.get('from', {}).get('id')
        chat_id = callback_query['message']['chat']['id']
        message_id = callback_query['message']['message_id']
        callback_data = callback_query.get('data', '')

        # Responder callback
        telegram_api.answer_callback_query_sync(
            token=manager_token,
            callback_query_id=callback_query['id']
        )

        # Roteamento de callbacks
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        if callback_data == 'add_bot':
            response = loop.run_until_complete(handle_callback_add_bot(user_id))
        elif callback_data == 'list_bots':
            response = loop.run_until_complete(handle_callback_list_bots(user_id))
        elif callback_data == 'deactivate_menu':
            response = loop.run_until_complete(handle_callback_deactivate_menu(user_id))
        elif callback_data.startswith('deactivate:'):
            bot_id = int(callback_data.split(':')[1])
            response_text = loop.run_until_complete(handle_deactivate(user_id, bot_id))
            response = {"text": response_text, "keyboard": None}
        else:
            loop.close()
            return

        loop.close()

        # Editar mensagem com nova resposta
        telegram_api.edit_message_sync(
            token=manager_token,
            chat_id=chat_id,
            message_id=message_id,
            text=response['text'],
            keyboard=response.get('keyboard')
        )
        return

    # Processar mensagem de texto
    message = update.get('message', {})
    user_id = message.get('from', {}).get('id')
    chat_id = message.get('chat', {}).get('id')
    text = message.get('text', '')

    if not user_id or not chat_id:
        return

    # Roteamento de comandos
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    response = None

    if text == '/start':
        response = loop.run_until_complete(handle_start(user_id))
    elif ':' in text and len(text) > 30:  # Parece um token de bot
        response_text = loop.run_until_complete(handle_register(user_id, text.strip()))
        response = {"text": response_text, "keyboard": None}

    loop.close()

    # Enviar resposta
    if response:
        telegram_api.send_message_sync(
            token=manager_token,
            chat_id=chat_id,
            text=response['text'],
            keyboard=response.get('keyboard')
        )


@celery_app.task(bind=True, max_retries=3)
def call_external_api(self, bot_id: int, user_id: int, query: str):
    """Chama API externa com retry"""
    try:
        result = requests.post(
            'https://api.externa.com/endpoint',
            json={'query': query},
            timeout=5
        )
        send_message.delay(bot_id, user_id, result.json())

    except Exception as exc:
        logger.error("API call failed", extra={
            "bot_id": bot_id,
            "user_id": user_id,
            "error": str(exc)
        })
        # Retry com backoff exponencial
        raise self.retry(
            exc=exc,
            countdown=2 ** self.request.retries,
            max_retries=3
        )


@celery_app.task
def send_message(bot_id: int, user_id: int, text: str):
    """Envia mensagem pelo bot correto"""
    bot = BotRepository.get_bot_by_id_sync(bot_id)
    if not bot:
        return

    from workers.api_clients import TelegramAPI
    telegram_api = TelegramAPI()
    telegram_api.send_message_sync(
        token=decrypt(bot.token),
        chat_id=user_id,
        text=text
    )


@celery_app.task
def send_welcome(bot_id: int, user_id: int):
    """Envia mensagem de boas-vindas"""
    send_message.delay(bot_id, user_id, "👋 Bem-vindo! Digite /help para ver os comandos.")


@celery_app.task
def send_rate_limit_message(bot_id: int, user_id: int):
    """Envia mensagem de rate limit"""
    send_message.delay(bot_id, user_id, "⏳ Muitos comandos em pouco tempo. Aguarde alguns segundos.")
