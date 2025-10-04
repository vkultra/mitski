"""
Serviço de gerenciamento de conversação com IA
"""

from typing import Any, Dict, List

from core.telemetry import logger
from database.repos import (
    AIConfigRepository,
    AIPhaseRepository,
    ConversationHistoryRepository,
    UserAISessionRepository,
)
from services.ai.grok_client import GrokAPIClient
from services.ai.image_handler import ImageHandler
from services.ai.phase_detector import PhaseDetectorService


class AIConversationService:
    """Gerencia conversação com IA Grok"""

    HISTORY_LIMIT = 7  # Manter últimas 7 mensagens (14 entries: user+assistant)

    @staticmethod
    async def process_user_message(
        bot_id: int,
        user_telegram_id: int,
        text: str,
        photo_file_ids: List[str] = None,
        bot_token: str = None,
        xai_api_key: str = None,
    ) -> str:
        """
        Processa mensagem do usuário e retorna resposta da IA

        Args:
            bot_id: ID do bot
            user_telegram_id: ID do usuário no Telegram
            text: Texto da mensagem
            photo_file_ids: Lista de file_ids de fotos
            bot_token: Token do bot (para baixar imagens)
            xai_api_key: API key da xAI

        Returns:
            Resposta da IA (SEM reasoning)
        """
        logger.info(
            "AI conversation started",
            extra={
                "bot_id": bot_id,
                "user_telegram_id": user_telegram_id,
                "has_photos": bool(photo_file_ids),
                "num_photos": len(photo_file_ids) if photo_file_ids else 0,
                "user_message": text[:200],
            },
        )

        # 1. Buscar configuração
        ai_config = await AIConfigRepository.get_by_bot_id(bot_id)
        if not ai_config or not ai_config.is_enabled:
            raise ValueError("AI not enabled")

        logger.info(
            "AI config loaded",
            extra={
                "bot_id": bot_id,
                "model_type": ai_config.model_type,
                "temperature": float(ai_config.temperature),
                "max_tokens": ai_config.max_tokens,
                "general_prompt_preview": (
                    ai_config.general_prompt[:200] if ai_config.general_prompt else None
                ),
            },
        )

        # 2. Buscar/criar sessão
        session = await UserAISessionRepository.get_or_create_session(
            bot_id, user_telegram_id
        )

        # 3. Buscar histórico (últimas 7 msgs = 14 entries)
        history = await ConversationHistoryRepository.get_recent_messages(
            bot_id, user_telegram_id, limit=AIConversationService.HISTORY_LIMIT * 2
        )

        # 4. Buscar fase atual
        current_phase = None
        if session.current_phase_id:
            current_phase = await AIPhaseRepository.get_by_id(session.current_phase_id)

        logger.info(
            "Session and history loaded",
            extra={
                "bot_id": bot_id,
                "user_telegram_id": user_telegram_id,
                "current_phase_id": session.current_phase_id,
                "current_phase_name": (
                    current_phase.phase_name if current_phase else None
                ),
                "history_size": len(history),
            },
        )

        # 5. Processar imagens
        image_urls = []
        if photo_file_ids and bot_token:
            for file_id in photo_file_ids:
                try:
                    image_bytes = await ImageHandler.download_telegram_photo(
                        file_id, bot_token
                    )
                    image_b64 = ImageHandler.convert_to_base64(image_bytes)
                    image_urls.append(image_b64)
                except Exception as e:
                    logger.error("Failed to process image", extra={"error": str(e)})

        # 6. Montar mensagens
        messages = AIConversationService._build_messages(
            ai_config, history, current_phase, text, image_urls
        )

        # 7. Chamar Grok API com controle de concorrência
        from core.config import settings

        grok_client = GrokAPIClient(
            api_key=xai_api_key,
            max_concurrent=settings.GROK_MAX_CONCURRENT_REQUESTS,
        )

        model = (
            "grok-4-fast-reasoning"
            if ai_config.model_type == "reasoning"
            else "grok-4-fast-non-reasoning"
        )

        api_response = await grok_client.chat_completion(
            messages=messages,
            model=model,
            temperature=float(ai_config.temperature),
            max_tokens=ai_config.max_tokens,
        )

        # 8. Extrair resposta
        extracted = await grok_client.extract_response(api_response)
        answer = extracted["content"]
        usage = extracted["usage"]

        # 9. Detectar trigger
        all_phases = await AIPhaseRepository.get_phases_by_bot(bot_id)
        detected_trigger = PhaseDetectorService.detect_trigger(answer, all_phases)

        if detected_trigger:
            new_phase = await AIPhaseRepository.get_phase_by_trigger(
                bot_id, detected_trigger
            )
            await UserAISessionRepository.update_current_phase(
                bot_id, user_telegram_id, new_phase.id
            )
            logger.info(
                "Phase transition detected",
                extra={
                    "bot_id": bot_id,
                    "user_telegram_id": user_telegram_id,
                    "detected_trigger": detected_trigger,
                    "new_phase_id": new_phase.id,
                    "new_phase_name": new_phase.phase_name,
                },
            )

        # 10. Salvar histórico
        await ConversationHistoryRepository.add_message(
            bot_id=bot_id,
            user_telegram_id=user_telegram_id,
            role="user",
            content=text,
            has_image=len(image_urls) > 0,
            image_url=image_urls[0] if image_urls else None,
        )

        await ConversationHistoryRepository.add_message(
            bot_id=bot_id,
            user_telegram_id=user_telegram_id,
            role="assistant",
            content=answer,
            prompt_tokens=usage.get("prompt_tokens", 0),
            cached_tokens=usage.get("cached_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            reasoning_tokens=usage.get("reasoning_tokens", 0),
        )

        # 11. Limpar histórico antigo
        await ConversationHistoryRepository.clean_old_messages(
            bot_id, user_telegram_id, keep=AIConversationService.HISTORY_LIMIT * 2
        )

        # 12. Incrementar contador
        await UserAISessionRepository.increment_message_count(bot_id, user_telegram_id)

        await grok_client.close()

        logger.info(
            "AI conversation completed",
            extra={
                "bot_id": bot_id,
                "user_telegram_id": user_telegram_id,
                "response_length": len(answer),
                "total_tokens": usage.get("total_tokens", 0),
            },
        )

        # 13. Verificar se há ofertas na resposta da IA
        from services.offers.offer_service import OfferService

        offer_result = await OfferService.process_ai_message_for_offers(
            bot_id=bot_id,
            chat_id=user_telegram_id,
            ai_message=answer,
            bot_token=bot_token,
        )

        # Se uma oferta foi detectada e deve substituir a mensagem
        if offer_result and offer_result.get("replaced_message"):
            logger.info(
                "Offer replaced AI message",
                extra={
                    "bot_id": bot_id,
                    "user_telegram_id": user_telegram_id,
                    "offer_id": offer_result.get("offer_id"),
                    "offer_name": offer_result.get("offer_name"),
                },
            )
            # Retornar None para indicar que a mensagem foi substituída
            return None

        # Se deve adicionar pitch após a mensagem, adicionar marcador
        # Será processado em ai_tasks.py para evitar enviar o sufixo ao usuário
        if offer_result and offer_result.get("should_append_pitch"):
            answer = f"{answer}__OFFER_DETECTED:{offer_result['offer_id']}__"

        # 14. Verificar se a IA enviou termo de verificação manual
        from services.gateway.payment_verifier import PaymentVerifier

        manual_verify_result = (
            await AIConversationService._check_manual_verification_trigger(
                bot_id=bot_id,
                chat_id=user_telegram_id,
                ai_message=answer,
                bot_token=bot_token,
            )
        )

        if manual_verify_result and manual_verify_result.get("triggered"):
            logger.info(
                "Manual verification triggered by AI",
                extra={
                    "bot_id": bot_id,
                    "user_telegram_id": user_telegram_id,
                    "offer_id": manual_verify_result.get("offer_id"),
                    "trigger": manual_verify_result.get("trigger"),
                },
            )

        return answer

    @staticmethod
    def _build_messages(
        ai_config, history: List, current_phase, user_text: str, image_urls: List[str]
    ) -> List[Dict[str, Any]]:
        """Monta payload de mensagens"""
        messages = []

        # System prompt
        system_prompt = ai_config.general_prompt or "Você é um assistente útil."

        if current_phase:
            system_prompt += f"\n\n{current_phase.phase_prompt}"

        messages.append({"role": "system", "content": system_prompt})

        # Histórico
        for entry in history:
            messages.append({"role": entry.role, "content": entry.content})

        # Mensagem atual
        if image_urls:
            user_message = ImageHandler.create_multimodal_message(user_text, image_urls)
        else:
            user_message = ImageHandler.create_text_only_message(user_text)

        messages.append(user_message)

        return messages

    @staticmethod
    async def _check_manual_verification_trigger(
        bot_id: int, chat_id: int, ai_message: str, bot_token: str
    ) -> Dict[str, Any]:
        """
        Verifica se a mensagem da IA contém termo de verificação manual de alguma oferta

        Args:
            bot_id: ID do bot
            chat_id: ID do chat
            ai_message: Mensagem da IA
            bot_token: Token do bot

        Returns:
            Dict com {triggered: bool, offer_id: int, trigger: str, payment_found: bool}
        """
        from database.repos import OfferRepository, PixTransactionRepository

        # Buscar ofertas com termo de verificação configurado
        offers = await OfferRepository.get_offers_by_bot(bot_id, active_only=True)

        for offer in offers:
            if not offer.manual_verification_trigger:
                continue

            # Verificar se o termo está na mensagem da IA (case-insensitive)
            if offer.manual_verification_trigger.lower() in ai_message.lower():
                logger.info(
                    "Manual verification trigger detected",
                    extra={
                        "bot_id": bot_id,
                        "chat_id": chat_id,
                        "offer_id": offer.id,
                        "trigger": offer.manual_verification_trigger,
                    },
                )

                # Buscar transações PIX pendentes deste usuário nesta oferta
                # (criadas nos últimos 15 minutos)
                pending_transactions = (
                    PixTransactionRepository.get_pending_by_user_and_offer_sync(
                        bot_id=bot_id,
                        user_telegram_id=chat_id,
                        offer_id=offer.id,
                        minutes_ago=15,
                    )
                )

                if pending_transactions:
                    # Há transação pendente - verificar pagamento
                    from services.gateway.payment_verifier import PaymentVerifier

                    transaction = pending_transactions[0]

                    # Verificar status via API
                    payment_status = await PaymentVerifier.verify_payment(
                        transaction.id
                    )

                    if payment_status.get("status") == "paid":
                        # Pagamento encontrado - entregar conteúdo
                        await PaymentVerifier.deliver_content(transaction.id)

                        logger.info(
                            "Manual verification - payment found and delivered",
                            extra={
                                "bot_id": bot_id,
                                "transaction_id": transaction.id,
                                "offer_id": offer.id,
                            },
                        )

                        return {
                            "triggered": True,
                            "offer_id": offer.id,
                            "trigger": offer.manual_verification_trigger,
                            "payment_found": True,
                        }
                    else:
                        # Pagamento não encontrado - enviar blocos de verificação manual
                        from services.offers.manual_verification_sender import (
                            ManualVerificationSender,
                        )

                        sender = ManualVerificationSender(bot_token)
                        await sender.send_manual_verification(offer.id, chat_id)

                        logger.info(
                            "Manual verification - payment not found, sent manual blocks",
                            extra={
                                "bot_id": bot_id,
                                "transaction_id": transaction.id,
                                "offer_id": offer.id,
                            },
                        )

                        return {
                            "triggered": True,
                            "offer_id": offer.id,
                            "trigger": offer.manual_verification_trigger,
                            "payment_found": False,
                        }
                else:
                    # Não há transação pendente
                    logger.info(
                        "Manual verification triggered but no pending transaction",
                        extra={
                            "bot_id": bot_id,
                            "chat_id": chat_id,
                            "offer_id": offer.id,
                        },
                    )

        return {"triggered": False}
