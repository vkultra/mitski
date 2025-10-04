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
    chat_id = message.get("chat", {}).get("id", user_id)

    # NOVO: Verificar se é comando de debug primeiro
    if text and text.startswith("/"):
        from handlers.debug_commands_router import DebugCommandRouter

        # Tentar processar como comando de debug
        debug_result = asyncio.run(
            DebugCommandRouter.route_debug_command(
                bot_id=bot_id,
                chat_id=chat_id,
                user_telegram_id=user_id,
                text=text,
                bot_token=decrypt(bot.token),
            )
        )

        # Se foi processado como debug, retorna
        if debug_result:
            logger.info(
                "Debug command processed",
                extra={
                    "bot_id": bot_id,
                    "user_id": user_id,
                    "command": text,
                    "result": debug_result,
                },
            )
            return

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

            welcome_text = asyncio.run(handle_bot_start(bot.id, user_id))
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
    from handlers.phase_handlers import (
        handle_confirm_delete_phase,
        handle_create_initial_phase_click,
        handle_delete_phase,
        handle_initial_phase_prompt_input,
        handle_list_phases,
        handle_set_initial_phase,
        handle_view_phase,
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

        # Usar asyncio.run() ao invés de criar/destruir loops
        response = None

        if callback_data == "add_bot":
            response = asyncio.run(handle_callback_add_bot(user_id))
        elif callback_data == "list_bots":
            response = asyncio.run(handle_callback_list_bots(user_id))
        elif callback_data == "deactivate_menu":
            response = asyncio.run(handle_callback_deactivate_menu(user_id))
        elif callback_data.startswith("deactivate:"):
            bot_id = int(callback_data.split(":")[1])
            response_text = asyncio.run(handle_deactivate(user_id, bot_id))
            response = {"text": response_text, "keyboard": None}
        # IA Menu callbacks
        elif callback_data == "ai_menu":
            from handlers.ai_handlers import handle_ai_menu_click

            response = asyncio.run(handle_ai_menu_click(user_id))
        elif callback_data.startswith("ai_select_bot:"):
            bot_id = int(callback_data.split(":")[1])
            from handlers.ai_handlers import handle_bot_selected_for_ai

            response = asyncio.run(handle_bot_selected_for_ai(user_id, bot_id))
        elif callback_data.startswith("ai_general_prompt:"):
            bot_id = int(callback_data.split(":")[1])
            from handlers.ai_handlers import handle_general_prompt_click

            response = asyncio.run(handle_general_prompt_click(user_id, bot_id))
        elif callback_data.startswith("ai_create_phase:"):
            bot_id = int(callback_data.split(":")[1])
            from handlers.ai_handlers import handle_create_phase_click

            response = asyncio.run(handle_create_phase_click(user_id, bot_id))
        elif callback_data.startswith("ai_toggle_model:"):
            bot_id = int(callback_data.split(":")[1])
            from handlers.ai_handlers import handle_toggle_model

            response = asyncio.run(handle_toggle_model(user_id, bot_id))
        # Phase management callbacks
        elif callback_data.startswith("ai_list_phases:"):
            bot_id = int(callback_data.split(":")[1])
            response = asyncio.run(handle_list_phases(user_id, bot_id))
        elif callback_data.startswith("ai_view_phase:"):
            phase_id = int(callback_data.split(":")[1])
            response = asyncio.run(handle_view_phase(user_id, phase_id))
        elif callback_data.startswith("ai_create_initial:"):
            bot_id = int(callback_data.split(":")[1])
            response = asyncio.run(handle_create_initial_phase_click(user_id, bot_id))
        elif callback_data.startswith("ai_set_initial:"):
            phase_id = int(callback_data.split(":")[1])
            response = asyncio.run(handle_set_initial_phase(user_id, phase_id))
        elif callback_data.startswith("ai_confirm_delete:"):
            phase_id = int(callback_data.split(":")[1])
            response = asyncio.run(handle_confirm_delete_phase(user_id, phase_id))
        elif callback_data.startswith("ai_delete_phase:"):
            phase_id = int(callback_data.split(":")[1])
            response = asyncio.run(handle_delete_phase(user_id, phase_id))
        # Offer menu callbacks
        elif callback_data == "noop":
            # Callback que não faz nada (usado em botões informativos)
            response = None
        elif callback_data.startswith("offer_menu_page:"):
            parts = callback_data.split(":")
            bot_id = int(parts[1])
            page = int(parts[2])
            from handlers.offers import handle_offer_menu

            response = asyncio.run(handle_offer_menu(user_id, bot_id, page=page))
        elif callback_data.startswith("offer_menu:"):
            bot_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_offer_menu

            response = asyncio.run(handle_offer_menu(user_id, bot_id))
        elif callback_data.startswith("offer_create:"):
            bot_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_create_offer

            response = asyncio.run(handle_create_offer(user_id, bot_id))
        elif callback_data.startswith("offer_list:"):
            bot_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_list_offers

            response = asyncio.run(handle_list_offers(user_id, bot_id))
        elif callback_data.startswith("offer_list_delete:"):
            bot_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_list_offers_delete

            response = asyncio.run(handle_list_offers_delete(user_id, bot_id))
        elif callback_data.startswith("offer_associate:"):
            parts = callback_data.split(":")
            bot_id = int(parts[1])
            offer_id = int(parts[2])
            from handlers.offers import handle_associate_offer

            response = asyncio.run(handle_associate_offer(user_id, bot_id, offer_id))
        elif callback_data.startswith("offer_dissociate:"):
            parts = callback_data.split(":")
            bot_id = int(parts[1])
            offer_id = int(parts[2])
            from handlers.offers import handle_dissociate_offer

            response = asyncio.run(handle_dissociate_offer(user_id, bot_id, offer_id))
        elif callback_data.startswith("offer_pitch:"):
            offer_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_offer_pitch_menu

            response = asyncio.run(handle_offer_pitch_menu(user_id, offer_id))
        elif callback_data.startswith("pitch_add:"):
            offer_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_create_pitch_block

            response = asyncio.run(handle_create_pitch_block(user_id, offer_id))
        elif callback_data.startswith("pitch_text:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_block_text_click

            response = asyncio.run(handle_block_text_click(user_id, block_id))
        elif callback_data.startswith("pitch_media:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_block_media_click

            response = asyncio.run(handle_block_media_click(user_id, block_id))
        elif callback_data.startswith("pitch_effects:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_block_effects_click

            response = asyncio.run(handle_block_effects_click(user_id, block_id))
        elif callback_data.startswith("pitch_delay:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_block_delay_click

            response = asyncio.run(handle_block_delay_click(user_id, block_id))
        elif callback_data.startswith("pitch_autodel:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_block_autodel_click

            response = asyncio.run(handle_block_autodel_click(user_id, block_id))
        elif callback_data.startswith("pitch_delete:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_delete_block

            response = asyncio.run(handle_delete_block(user_id, block_id))
        elif callback_data.startswith("pitch_preview:"):
            offer_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_preview_pitch

            response = asyncio.run(handle_preview_pitch(user_id, offer_id))
        # Deliverable block routes
        elif callback_data.startswith("deliv_blocks:"):
            offer_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_deliverable_blocks_menu

            response = asyncio.run(handle_deliverable_blocks_menu(user_id, offer_id))
        elif callback_data.startswith("deliv_block_add:"):
            offer_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_create_deliverable_block

            response = asyncio.run(handle_create_deliverable_block(user_id, offer_id))
        elif callback_data.startswith("deliv_block_text:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_deliverable_block_text_click

            response = asyncio.run(
                handle_deliverable_block_text_click(user_id, block_id)
            )
        elif callback_data.startswith("deliv_block_media:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_deliverable_block_media_click

            response = asyncio.run(
                handle_deliverable_block_media_click(user_id, block_id)
            )
        elif callback_data.startswith("deliv_block_effects:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_deliverable_block_effects_click

            response = asyncio.run(
                handle_deliverable_block_effects_click(user_id, block_id)
            )
        elif callback_data.startswith("deliv_block_delay:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_deliverable_block_delay_click

            response = asyncio.run(
                handle_deliverable_block_delay_click(user_id, block_id)
            )
        elif callback_data.startswith("deliv_block_autodel:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_deliverable_block_autodel_click

            response = asyncio.run(
                handle_deliverable_block_autodel_click(user_id, block_id)
            )
        elif callback_data.startswith("deliv_block_delete:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_delete_deliverable_block

            response = asyncio.run(handle_delete_deliverable_block(user_id, block_id))
        elif callback_data.startswith("deliv_block_preview:"):
            offer_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_preview_deliverable

            response = asyncio.run(handle_preview_deliverable(user_id, offer_id))
        # Manual verification routes
        elif callback_data.startswith("manver_menu:"):
            offer_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_manual_verification_menu

            response = asyncio.run(handle_manual_verification_menu(user_id, offer_id))
        elif callback_data.startswith("manver_set_trigger:"):
            offer_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_set_verification_trigger

            response = asyncio.run(handle_set_verification_trigger(user_id, offer_id))
        elif callback_data.startswith("manver_block_add:"):
            offer_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_create_manual_verification_block

            response = asyncio.run(
                handle_create_manual_verification_block(user_id, offer_id)
            )
        elif callback_data.startswith("manver_block_text:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_manual_verification_block_text_click

            response = asyncio.run(
                handle_manual_verification_block_text_click(user_id, block_id)
            )
        elif callback_data.startswith("manver_block_media:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_manual_verification_block_media_click

            response = asyncio.run(
                handle_manual_verification_block_media_click(user_id, block_id)
            )
        elif callback_data.startswith("manver_block_effects:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_manual_verification_block_effects_click

            response = asyncio.run(
                handle_manual_verification_block_effects_click(user_id, block_id)
            )
        elif callback_data.startswith("manver_block_delay:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_manual_verification_block_delay_click

            response = asyncio.run(
                handle_manual_verification_block_delay_click(user_id, block_id)
            )
        elif callback_data.startswith("manver_block_autodel:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_manual_verification_block_autodel_click

            response = asyncio.run(
                handle_manual_verification_block_autodel_click(user_id, block_id)
            )
        elif callback_data.startswith("manver_block_delete:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_delete_manual_verification_block

            response = asyncio.run(
                handle_delete_manual_verification_block(user_id, block_id)
            )
        elif callback_data.startswith("manver_block_preview:"):
            offer_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_preview_manual_verification

            response = asyncio.run(
                handle_preview_manual_verification(user_id, offer_id)
            )
        elif callback_data.startswith("offer_save:"):
            offer_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_save_offer

            response = asyncio.run(handle_save_offer(user_id, offer_id))
        elif callback_data.startswith("offer_delete_confirm:"):
            offer_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_delete_offer_confirm

            response = asyncio.run(handle_delete_offer_confirm(user_id, offer_id))
        elif callback_data.startswith("offer_delete:"):
            offer_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_delete_offer

            response = asyncio.run(handle_delete_offer(user_id, offer_id))
        elif callback_data.startswith("offer_edit:"):
            offer_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_offer_edit_menu

            response = asyncio.run(handle_offer_edit_menu(user_id, offer_id))
        elif callback_data.startswith("offer_value_click:"):
            offer_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_offer_value_click

            response = asyncio.run(handle_offer_value_click(user_id, offer_id))
        elif callback_data.startswith("offer_deliverable_menu:"):
            offer_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_offer_deliverable_menu

            response = asyncio.run(handle_offer_deliverable_menu(user_id, offer_id))
        elif callback_data.startswith("offer_manual_verify_toggle:"):
            offer_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_offer_manual_verification_toggle

            response = asyncio.run(
                handle_offer_manual_verification_toggle(user_id, offer_id)
            )
        elif callback_data.startswith("offer_save_final:"):
            offer_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_offer_save_final

            response = asyncio.run(handle_offer_save_final(user_id, offer_id))
        elif callback_data.startswith("deliverable_add:"):
            offer_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_create_deliverable

            response = asyncio.run(handle_create_deliverable(user_id, offer_id))
        elif callback_data.startswith("deliverable_delete:"):
            deliverable_id = int(callback_data.split(":")[1])
            from handlers.offers import handle_delete_deliverable

            response = asyncio.run(handle_delete_deliverable(user_id, deliverable_id))
        # Gateway callbacks
        elif callback_data == "gateway_menu":
            from handlers.gateway import handle_gateway_menu

            response = asyncio.run(handle_gateway_menu(user_id))
        elif callback_data == "gateway_pushinpay":
            from handlers.gateway import handle_pushinpay_menu

            response = asyncio.run(handle_pushinpay_menu(user_id))
        elif callback_data == "gateway_add_token":
            from handlers.gateway.token_handlers import handle_request_token

            response = asyncio.run(handle_request_token(user_id))
        elif callback_data == "gateway_edit_token":
            from handlers.gateway.token_handlers import handle_edit_token

            response = asyncio.run(handle_edit_token(user_id))
        elif callback_data == "gateway_update_token":
            from handlers.gateway import handle_update_token

            response = asyncio.run(handle_update_token(user_id))
        elif callback_data == "gateway_delete_token":
            from handlers.gateway import handle_delete_token

            response = asyncio.run(handle_delete_token(user_id))
        # Action menu callbacks
        elif callback_data.startswith("action_menu:"):
            bot_id = int(callback_data.split(":")[1])
            from handlers.ai.action_menu_handlers import handle_action_menu_click

            response = asyncio.run(handle_action_menu_click(user_id, bot_id))
        elif callback_data.startswith("action_add:"):
            bot_id = int(callback_data.split(":")[1])
            from handlers.ai.action_menu_handlers import handle_add_action_click

            response = asyncio.run(handle_add_action_click(user_id, bot_id))
        elif callback_data.startswith("action_edit:"):
            action_id = int(callback_data.split(":")[1])
            from handlers.ai.action_menu_handlers import handle_action_edit_menu

            response = asyncio.run(handle_action_edit_menu(user_id, action_id))
        elif callback_data.startswith("action_toggle_track:"):
            action_id = int(callback_data.split(":")[1])
            from handlers.ai.action_menu_handlers import handle_toggle_track

            response = asyncio.run(handle_toggle_track(user_id, action_id))
        elif callback_data.startswith("action_block_add:"):
            action_id = int(callback_data.split(":")[1])
            from handlers.ai.action_menu_handlers import handle_create_action_block

            response = asyncio.run(handle_create_action_block(user_id, action_id))
        elif callback_data.startswith("action_block_delete:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.ai.action_crud_handlers import handle_delete_action_block

            response = asyncio.run(handle_delete_action_block(user_id, block_id))
        elif callback_data.startswith("action_delete:"):
            action_id = int(callback_data.split(":")[1])
            from handlers.ai.action_crud_handlers import handle_delete_action

            response = asyncio.run(handle_delete_action(user_id, action_id))
        elif callback_data.startswith("action_delete_confirm:"):
            action_id = int(callback_data.split(":")[1])
            from handlers.ai.action_crud_handlers import handle_delete_action_confirm

            response = asyncio.run(handle_delete_action_confirm(user_id, action_id))
        elif callback_data.startswith("action_preview:"):
            action_id = int(callback_data.split(":")[1])
            from handlers.ai.action_crud_handlers import handle_preview_action

            response = asyncio.run(handle_preview_action(user_id, action_id))
        # Action block handlers
        elif callback_data.startswith("action_block_text:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.ai.action_block_handlers import handle_action_block_text_click

            response = asyncio.run(handle_action_block_text_click(user_id, block_id))
        elif callback_data.startswith("action_block_media:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.ai.action_block_handlers import (
                handle_action_block_media_click,
            )

            response = asyncio.run(handle_action_block_media_click(user_id, block_id))
        elif callback_data.startswith("action_block_effects:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.ai.action_block_handlers import (
                handle_action_block_effects_click,
            )

            response = asyncio.run(handle_action_block_effects_click(user_id, block_id))
        elif callback_data.startswith("action_block_delay:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.ai.action_block_handlers import (
                handle_action_block_delay_click,
            )

            response = asyncio.run(handle_action_block_delay_click(user_id, block_id))
        elif callback_data.startswith("action_block_autodel:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.ai.action_block_handlers import (
                handle_action_block_autodel_click,
            )

            response = asyncio.run(handle_action_block_autodel_click(user_id, block_id))
        elif callback_data.startswith("action_block_view:"):
            block_id = int(callback_data.split(":")[1])
            from handlers.ai.action_block_handlers import handle_action_block_view

            response = asyncio.run(handle_action_block_view(user_id, block_id))
        elif callback_data == "back_to_main":
            response = asyncio.run(handle_start(user_id))

        # Responder callback IMEDIATAMENTE (antes de editar mensagem)
        # para evitar timeout do Telegram (~5 segundos)
        try:
            telegram_api.answer_callback_query_sync(
                token=manager_token, callback_query_id=callback_query["id"]
            )
        except Exception as e:
            logger.warning(
                "Falha ao responder callback (provavelmente expirado)",
                extra={"callback_id": callback_query["id"], "error": str(e)},
            )

        # Se houver response, editar mensagem
        if response:
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
    response = None

    if text == "/start":
        response = asyncio.run(handle_start(user_id))
    else:
        # Tenta processar como entrada de estado conversacional
        response = asyncio.run(handle_text_input(user_id, text))

        # Se não tem estado de bot, verifica estado de IA
        if not response:
            from services.conversation_state import ConversationStateManager

            state_data = ConversationStateManager.get_state(user_id)

            if state_data:
                state = state_data.get("state")
                data = state_data.get("data", {})

                if state == "awaiting_general_prompt":
                    from handlers.ai_handlers import handle_general_prompt_input

                    response = asyncio.run(
                        handle_general_prompt_input(user_id, data["bot_id"], text)
                    )

                elif state == "awaiting_phase_name":
                    from handlers.ai_handlers import handle_phase_name_input

                    response = asyncio.run(
                        handle_phase_name_input(user_id, data["bot_id"], text)
                    )

                elif state == "awaiting_phase_trigger":
                    from handlers.ai_handlers import handle_phase_trigger_input

                    response = asyncio.run(
                        handle_phase_trigger_input(
                            user_id, data["bot_id"], data["name"], text
                        )
                    )

                elif state == "awaiting_phase_prompt":
                    from handlers.ai_handlers import handle_phase_prompt_input

                    response = asyncio.run(
                        handle_phase_prompt_input(
                            user_id, data["bot_id"], data["name"], data["trigger"], text
                        )
                    )

                elif state == "awaiting_initial_phase_prompt":
                    response = asyncio.run(
                        handle_initial_phase_prompt_input(user_id, data["bot_id"], text)
                    )

                # Offer states
                elif state == "awaiting_offer_name":
                    from handlers.offers import handle_offer_name_input

                    response = asyncio.run(
                        handle_offer_name_input(user_id, data["bot_id"], text)
                    )

                elif state == "awaiting_offer_value":
                    from handlers.offers import handle_offer_value_input

                    response = asyncio.run(
                        handle_offer_value_input(
                            user_id, data["bot_id"], data["offer_id"], text
                        )
                    )

                elif state == "awaiting_offer_value_edit":
                    from handlers.offers import handle_offer_value_edit_input

                    response = asyncio.run(
                        handle_offer_value_edit_input(user_id, data["offer_id"], text)
                    )

                elif state == "awaiting_deliverable_content":
                    from handlers.offers import handle_deliverable_content_input

                    response = asyncio.run(
                        handle_deliverable_content_input(
                            user_id, data["offer_id"], text
                        )
                    )

                # Gateway states
                elif state == "awaiting_gateway_token":
                    from handlers.gateway.token_handlers import handle_token_input

                    response = asyncio.run(handle_token_input(user_id, text))

                # Action states
                elif state == "awaiting_action_name":
                    from handlers.ai.action_menu_handlers import (
                        handle_action_name_input,
                    )

                    response = asyncio.run(
                        handle_action_name_input(user_id, data["bot_id"], text)
                    )
                elif state == "awaiting_action_block_text":
                    from handlers.ai.action_block_handlers import (
                        handle_action_block_text_input,
                    )

                    response = asyncio.run(
                        handle_action_block_text_input(
                            user_id, data["block_id"], data["action_id"], text
                        )
                    )
                elif state == "awaiting_action_block_delay":
                    from handlers.ai.action_block_handlers import (
                        handle_action_block_delay_input,
                    )

                    response = asyncio.run(
                        handle_action_block_delay_input(
                            user_id, data["block_id"], data["action_id"], text
                        )
                    )
                elif state == "awaiting_action_block_autodel":
                    from handlers.ai.action_block_handlers import (
                        handle_action_block_autodel_input,
                    )

                    response = asyncio.run(
                        handle_action_block_autodel_input(
                            user_id, data["block_id"], data["action_id"], text
                        )
                    )

                elif state == "awaiting_block_text":
                    from handlers.offers import handle_block_text_input

                    response = asyncio.run(
                        handle_block_text_input(
                            user_id, data["block_id"], data["offer_id"], text
                        )
                    )

                elif state == "awaiting_block_media":
                    # Handle media upload
                    photos = message.get("photo", [])
                    video = message.get("video")
                    audio = message.get("audio")
                    document = message.get("document")
                    animation = message.get("animation")

                    media_file_id = None
                    media_type = None

                    if photos:
                        # Use largest photo
                        media_file_id = photos[-1]["file_id"]
                        media_type = "photo"
                    elif video:
                        media_file_id = video["file_id"]
                        media_type = "video"
                    elif audio:
                        media_file_id = audio["file_id"]
                        media_type = "audio"
                    elif document:
                        media_file_id = document["file_id"]
                        media_type = "document"
                    elif animation:
                        media_file_id = animation["file_id"]
                        media_type = "animation"

                    if media_file_id:
                        from handlers.offers import handle_block_media_input

                        response = asyncio.run(
                            handle_block_media_input(
                                user_id,
                                data["block_id"],
                                data["offer_id"],
                                media_file_id,
                                media_type,
                            )
                        )
                    else:
                        response = {
                            "text": "❌ Por favor, envie uma mídia (foto, vídeo, áudio, gif ou documento).",
                            "keyboard": None,
                        }

                elif state == "awaiting_action_block_media":
                    # Processar mídia para bloco de ação
                    photos = message.get("photo", [])
                    video = message.get("video")
                    audio = message.get("audio")
                    document = message.get("document")
                    animation = message.get("animation")

                    media_file_id = None
                    media_type = None

                    if photos:
                        # Use largest photo
                        media_file_id = photos[-1]["file_id"]
                        media_type = "photo"
                    elif video:
                        media_file_id = video["file_id"]
                        media_type = "video"
                    elif audio:
                        media_file_id = audio["file_id"]
                        media_type = "audio"
                    elif document:
                        media_file_id = document["file_id"]
                        media_type = "document"
                    elif animation:
                        media_file_id = animation["file_id"]
                        media_type = "animation"

                    if media_file_id:
                        from handlers.ai.action_block_handlers import (
                            handle_action_block_media_input,
                        )

                        response = asyncio.run(
                            handle_action_block_media_input(
                                user_id,
                                data["block_id"],
                                data["action_id"],
                                media_file_id,
                                media_type,
                            )
                        )
                    else:
                        response = {
                            "text": "❌ Por favor, envie uma mídia (foto, vídeo, áudio, gif ou documento).",
                            "keyboard": None,
                        }

                elif state == "awaiting_block_delay":
                    from handlers.offers import handle_block_delay_input

                    response = asyncio.run(
                        handle_block_delay_input(
                            user_id, data["block_id"], data["offer_id"], text
                        )
                    )

                elif state == "awaiting_block_autodel":
                    from handlers.offers import handle_block_autodel_input

                    response = asyncio.run(
                        handle_block_autodel_input(
                            user_id, data["block_id"], data["offer_id"], text
                        )
                    )

                # Deliverable block states
                elif state == "awaiting_deliv_block_text":
                    from handlers.offers import handle_deliverable_block_text_input

                    response = asyncio.run(
                        handle_deliverable_block_text_input(
                            user_id, data["block_id"], data["offer_id"], text
                        )
                    )

                elif state == "awaiting_deliv_block_media":
                    # Handle media upload
                    photos = message.get("photo", [])
                    video = message.get("video")
                    audio = message.get("audio")
                    document = message.get("document")
                    animation = message.get("animation")

                    media_file_id = None
                    media_type = None

                    if photos:
                        # Pegar foto de maior resolução
                        media_file_id = photos[-1]["file_id"]
                        media_type = "photo"
                    elif video:
                        media_file_id = video["file_id"]
                        media_type = "video"
                    elif audio:
                        media_file_id = audio["file_id"]
                        media_type = "audio"
                    elif document:
                        media_file_id = document["file_id"]
                        media_type = "document"
                    elif animation:
                        media_file_id = animation["file_id"]
                        media_type = "animation"

                    if media_file_id:
                        from handlers.offers import handle_deliverable_block_media_input

                        response = asyncio.run(
                            handle_deliverable_block_media_input(
                                user_id,
                                data["block_id"],
                                data["offer_id"],
                                media_file_id,
                                media_type,
                            )
                        )
                    else:
                        response = {
                            "text": "❌ Tipo de mídia não suportado. Envie foto, vídeo, áudio, gif ou documento.",
                            "keyboard": None,
                        }

                elif state == "awaiting_deliv_block_delay":
                    from handlers.offers import handle_deliverable_block_delay_input

                    response = asyncio.run(
                        handle_deliverable_block_delay_input(
                            user_id, data["block_id"], data["offer_id"], text
                        )
                    )

                elif state == "awaiting_deliv_block_autodel":
                    from handlers.offers import handle_deliverable_block_autodel_input

                    response = asyncio.run(
                        handle_deliverable_block_autodel_input(
                            user_id, data["block_id"], data["offer_id"], text
                        )
                    )

                # Manual verification states
                elif state == "awaiting_manver_trigger":
                    from handlers.offers import handle_verification_trigger_input

                    response = asyncio.run(
                        handle_verification_trigger_input(
                            user_id, data["offer_id"], text
                        )
                    )

                elif state == "awaiting_manver_block_text":
                    from handlers.offers import (
                        handle_manual_verification_block_text_input,
                    )

                    response = asyncio.run(
                        handle_manual_verification_block_text_input(
                            user_id, data["block_id"], data["offer_id"], text
                        )
                    )

                elif state == "awaiting_manver_block_media":
                    # Handle media upload
                    photos = message.get("photo", [])
                    video = message.get("video")
                    audio = message.get("audio")
                    document = message.get("document")
                    animation = message.get("animation")

                    media_file_id = None
                    media_type = None

                    if photos:
                        media_file_id = photos[-1]["file_id"]
                        media_type = "photo"
                    elif video:
                        media_file_id = video["file_id"]
                        media_type = "video"
                    elif audio:
                        media_file_id = audio["file_id"]
                        media_type = "audio"
                    elif document:
                        media_file_id = document["file_id"]
                        media_type = "document"
                    elif animation:
                        media_file_id = animation["file_id"]
                        media_type = "animation"

                    if media_file_id:
                        from handlers.offers import (
                            handle_manual_verification_block_media_input,
                        )

                        response = asyncio.run(
                            handle_manual_verification_block_media_input(
                                user_id,
                                data["block_id"],
                                data["offer_id"],
                                media_file_id,
                                media_type,
                            )
                        )
                    else:
                        response = {
                            "text": "❌ Tipo de mídia não suportado. Envie foto, vídeo, áudio, gif ou documento.",
                            "keyboard": None,
                        }

                elif state == "awaiting_manver_block_delay":
                    from handlers.offers import (
                        handle_manual_verification_block_delay_input,
                    )

                    response = asyncio.run(
                        handle_manual_verification_block_delay_input(
                            user_id, data["block_id"], data["offer_id"], text
                        )
                    )

                elif state == "awaiting_manver_block_autodel":
                    from handlers.offers import (
                        handle_manual_verification_block_autodel_input,
                    )

                    response = asyncio.run(
                        handle_manual_verification_block_autodel_input(
                            user_id, data["block_id"], data["offer_id"], text
                        )
                    )

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
