"""
Tasks assíncronas do Celery
"""

import requests

from core.rate_limiter import check_rate_limit
from core.security import decrypt
from core.telemetry import logger
from database.repos import BotRepository

from .celery_app import celery_app


@celery_app.task(bind=True, max_retries=3)
def process_telegram_update(self, bot_id: int, update: dict):
    """Processa update de bot secundário - COM SUPORTE A IA"""
    import asyncio

    from core.security import decrypt
    from database.repos import AIConfigRepository

    bot = BotRepository.get_bot_by_id_sync(bot_id)
    if not bot or not bot.is_active:
        logger.warning("Bot inactive or not found", extra={"bot_id": bot_id})
        return

    message = update.get("message", {})
    user_id = message.get("from", {}).get("id")

    if not user_id:
        return

    # Rate limit por bot + usuário
    if not check_rate_limit(bot_id, user_id):
        send_rate_limit_message.delay(bot.id, user_id)
        return

    text = message.get("text", "")
    photos = message.get("photo", [])

    # NOVO: Verifica se bot tem IA ativada
    ai_config = AIConfigRepository.get_by_bot_id_sync(bot_id)

    if ai_config and ai_config.is_enabled:
        # Processar com IA
        from workers.ai_tasks import process_ai_message

        photo_file_ids = [photo["file_id"] for photo in photos] if photos else []

        process_ai_message.delay(
            bot_id=bot_id,
            user_telegram_id=user_id,
            text=text,
            photo_file_ids=photo_file_ids,
            bot_token=decrypt(bot.token),
        )
    else:
        # Fluxo normal (sem IA)
        if text == "/start":
            from handlers.bot_handlers import handle_bot_start

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            welcome_text = loop.run_until_complete(handle_bot_start(bot.id, user_id))
            loop.close()
            send_message.delay(bot.id, user_id, welcome_text)
        elif text.startswith("/api"):
            call_external_api.delay(bot_id, user_id, text)


@celery_app.task(bind=True, max_retries=3)
def process_manager_update(self, update: dict):
    """Processa update do bot gerenciador"""
    import asyncio
    import os

    from handlers.manager_handlers import (
        handle_callback_add_bot,
        handle_callback_deactivate_menu,
        handle_callback_list_bots,
        handle_deactivate,
        handle_start,
        handle_text_input,
    )
    from workers.api_clients import TelegramAPI

    telegram_api = TelegramAPI()
    manager_token = os.environ.get("MANAGER_BOT_TOKEN")

    # Processar callback query
    callback_query = update.get("callback_query")
    if callback_query:
        user_id = callback_query.get("from", {}).get("id")
        chat_id = callback_query["message"]["chat"]["id"]
        message_id = callback_query["message"]["message_id"]
        callback_data = callback_query.get("data", "")

        # Responder callback
        telegram_api.answer_callback_query_sync(
            token=manager_token, callback_query_id=callback_query["id"]
        )

        # Roteamento de callbacks
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        if callback_data == "add_bot":
            response = loop.run_until_complete(handle_callback_add_bot(user_id))
        elif callback_data == "list_bots":
            response = loop.run_until_complete(handle_callback_list_bots(user_id))
        elif callback_data == "deactivate_menu":
            response = loop.run_until_complete(handle_callback_deactivate_menu(user_id))
        elif callback_data.startswith("deactivate:"):
            bot_id = int(callback_data.split(":")[1])
            response_text = loop.run_until_complete(handle_deactivate(user_id, bot_id))
            response = {"text": response_text, "keyboard": None}
        # IA Menu callbacks
        elif callback_data == "ai_menu":
            from handlers.ai_handlers import handle_ai_menu_click

            response = loop.run_until_complete(handle_ai_menu_click(user_id))
        elif callback_data.startswith("ai_select_bot:"):
            bot_id = int(callback_data.split(":")[1])
            from handlers.ai_handlers import handle_bot_selected_for_ai

            response = loop.run_until_complete(
                handle_bot_selected_for_ai(user_id, bot_id)
            )
        elif callback_data.startswith("ai_general_prompt:"):
            bot_id = int(callback_data.split(":")[1])
            from handlers.ai_handlers import handle_general_prompt_click

            response = loop.run_until_complete(
                handle_general_prompt_click(user_id, bot_id)
            )
        elif callback_data.startswith("ai_create_phase:"):
            bot_id = int(callback_data.split(":")[1])
            from handlers.ai_handlers import handle_create_phase_click

            response = loop.run_until_complete(
                handle_create_phase_click(user_id, bot_id)
            )
        elif callback_data.startswith("ai_toggle_model:"):
            bot_id = int(callback_data.split(":")[1])
            from handlers.ai_handlers import handle_toggle_model

            response = loop.run_until_complete(handle_toggle_model(user_id, bot_id))
        elif callback_data == "back_to_main":
            response = loop.run_until_complete(handle_start(user_id))
        else:
            loop.close()
            return

        loop.close()

        # Editar mensagem com nova resposta
        telegram_api.edit_message_sync(
            token=manager_token,
            chat_id=chat_id,
            message_id=message_id,
            text=response["text"],
            keyboard=response.get("keyboard"),
        )
        return

    # Processar mensagem de texto
    message = update.get("message", {})
    user_id = message.get("from", {}).get("id")
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    if not user_id or not chat_id:
        return

    # Roteamento de comandos e estados conversacionais
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    response = None

    if text == "/start":
        response = loop.run_until_complete(handle_start(user_id))
    else:
        # Tenta processar como entrada de estado conversacional
        response = loop.run_until_complete(handle_text_input(user_id, text))

        # Se não tem estado de bot, verifica estado de IA
        if not response:
            from services.conversation_state import ConversationStateManager

            state_data = ConversationStateManager.get_state(user_id)

            if state_data:
                state = state_data.get("state")
                data = state_data.get("data", {})

                if state == "awaiting_general_prompt":
                    from handlers.ai_handlers import handle_general_prompt_input

                    response = loop.run_until_complete(
                        handle_general_prompt_input(user_id, data["bot_id"], text)
                    )

                elif state == "awaiting_phase_trigger":
                    from handlers.ai_handlers import handle_phase_trigger_input

                    response = loop.run_until_complete(
                        handle_phase_trigger_input(user_id, data["bot_id"], text)
                    )

                elif state == "awaiting_phase_prompt":
                    from handlers.ai_handlers import handle_phase_prompt_input

                    response = loop.run_until_complete(
                        handle_phase_prompt_input(
                            user_id, data["bot_id"], data["trigger"], text
                        )
                    )

    loop.close()

    # Enviar resposta
    if response:
        telegram_api.send_message_sync(
            token=manager_token,
            chat_id=chat_id,
            text=response["text"],
            keyboard=response.get("keyboard"),
        )


@celery_app.task(bind=True, max_retries=3)
def call_external_api(self, bot_id: int, user_id: int, query: str):
    """Chama API externa com retry"""
    try:
        result = requests.post(
            "https://api.externa.com/endpoint", json={"query": query}, timeout=5
        )
        send_message.delay(bot_id, user_id, result.json())

    except Exception as exc:
        logger.error(
            "API call failed",
            extra={"bot_id": bot_id, "user_id": user_id, "error": str(exc)},
        )
        # Retry com backoff exponencial
        raise self.retry(exc=exc, countdown=2**self.request.retries, max_retries=3)


@celery_app.task
def send_message(bot_id: int, user_id: int, text: str):
    """Envia mensagem pelo bot correto"""
    bot = BotRepository.get_bot_by_id_sync(bot_id)
    if not bot:
        return

    from workers.api_clients import TelegramAPI

    telegram_api = TelegramAPI()
    telegram_api.send_message_sync(token=decrypt(bot.token), chat_id=user_id, text=text)


@celery_app.task
def send_welcome(bot_id: int, user_id: int):
    """Envia mensagem de boas-vindas"""
    send_message.delay(
        bot_id, user_id, "👋 Bem-vindo! Digite /help para ver os comandos."
    )


@celery_app.task
def send_rate_limit_message(bot_id: int, user_id: int):
    """Envia mensagem de rate limit"""
    send_message.delay(
        bot_id, user_id, "⏳ Muitos comandos em pouco tempo. Aguarde alguns segundos."
    )
