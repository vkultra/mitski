"""
Comandos de debug para testar o sistema de ações, ofertas e pagamentos
"""

import asyncio
from typing import Dict, Optional

from core.telemetry import logger
from database.repos import (
    AIActionRepository,
    OfferDeliverableBlockRepository,
    OfferRepository,
)
from services.ai.actions.action_sender import ActionSenderService
from services.offers.pitch_sender import PitchSenderService
from workers.api_clients import TelegramAPI


class DebugCommandHandler:
    """Handler para comandos de debug do sistema"""

    @staticmethod
    async def handle_venda_aprovada(
        bot_id: int,
        chat_id: int,
        user_telegram_id: int,
        bot_token: str,
        offer_name: Optional[str] = None,
    ) -> Dict:
        """
        Simula uma venda aprovada e entrega o conteúdo

        Args:
            bot_id: ID do bot
            chat_id: ID do chat
            user_telegram_id: ID do usuário
            bot_token: Token do bot
            offer_name: Nome da oferta (opcional, pega a primeira se não especificado)

        Returns:
            Dict com resultado da simulação
        """
        try:
            logger.info(
                "Debug: Simulando venda aprovada",
                extra={
                    "bot_id": bot_id,
                    "chat_id": chat_id,
                    "user_telegram_id": user_telegram_id,
                    "offer_name": offer_name,
                },
            )

            # Buscar oferta
            if offer_name:
                offer = await OfferRepository.get_by_name(bot_id, offer_name)
            else:
                # Pegar primeira oferta ativa do bot
                offers = await OfferRepository.get_offers_by_bot(
                    bot_id, active_only=True
                )
                offer = offers[0] if offers else None

            if not offer:
                await TelegramAPI().send_message(
                    bot_token,
                    chat_id,
                    "⚠️ Nenhuma oferta encontrada para simular venda.",
                )
                return {"success": False, "error": "no_offer_found"}

            # Buscar blocos de entregáveis da oferta
            deliverable_blocks = (
                await OfferDeliverableBlockRepository.get_blocks_by_offer(offer.id)
            )

            if not deliverable_blocks:
                await TelegramAPI().send_message(
                    bot_token,
                    chat_id,
                    f"⚠️ A oferta '{offer.name}' não tem conteúdo de entrega configurado.",
                )
                return {"success": False, "error": "no_deliverable_content"}

            # Simular transação paga
            await TelegramAPI().send_message(
                bot_token,
                chat_id,
                f"✅ Simulando pagamento aprovado para oferta: {offer.name}\n"
                f"💰 Valor: R$ {offer.price}\n\n"
                f"Entregando conteúdo...",
            )

            # Usar DeliverableSender igual ao sistema real
            from services.offers.deliverable_sender import DeliverableSender

            sender = DeliverableSender(bot_token)
            message_ids = await sender.send_deliverable(
                offer_id=offer.id,
                chat_id=chat_id,
                preview_mode=False,  # Enviar como se fosse real
                bot_id=bot_id,
            )

            await TelegramAPI().send_message(
                bot_token,
                chat_id,
                f"✅ Entrega concluída!\n"
                f"📦 {len(message_ids)} blocos entregues\n"
                f"🎯 Debug /vendaaprovada executado com sucesso",
            )

            return {
                "success": True,
                "offer_id": offer.id,
                "offer_name": offer.name,
                "messages_sent": len(message_ids),
            }

        except Exception as e:
            logger.error(
                "Erro no comando debug /vendaaprovada",
                extra={"error": str(e), "bot_id": bot_id},
            )
            await TelegramAPI().send_message(
                bot_token, chat_id, f"❌ Erro ao simular venda: {str(e)}"
            )
            return {"success": False, "error": str(e)}

    @staticmethod
    async def handle_trigger_action(
        bot_id: int, chat_id: int, action_name: str, bot_token: str
    ) -> Dict:
        """
        Dispara uma ação personalizada pelo nome

        Args:
            bot_id: ID do bot
            chat_id: ID do chat
            action_name: Nome da ação
            bot_token: Token do bot

        Returns:
            Dict com resultado do disparo
        """
        try:
            logger.info(
                "Debug: Disparando ação personalizada",
                extra={
                    "bot_id": bot_id,
                    "chat_id": chat_id,
                    "action_name": action_name,
                },
            )

            # Buscar ação
            action = await AIActionRepository.get_by_name(bot_id, action_name)

            if not action:
                await TelegramAPI().send_message(
                    bot_token,
                    chat_id,
                    f"⚠️ Ação '{action_name}' não encontrada.\n"
                    f"Use o nome exato da ação cadastrada.",
                )
                return {"success": False, "error": "action_not_found"}

            if not action.is_active:
                await TelegramAPI().send_message(
                    bot_token, chat_id, f"⚠️ A ação '{action_name}' está desativada."
                )
                return {"success": False, "error": "action_inactive"}

            # Enviar mensagem de debug
            await TelegramAPI().send_message(
                bot_token,
                chat_id,
                f"🎯 Disparando ação: {action.action_name}\n"
                f"📝 Descrição: {action.description or 'Sem descrição'}\n\n"
                f"Enviando blocos...",
            )

            # Enviar blocos da ação
            sender = ActionSenderService(bot_token)
            message_ids = await sender.send_action_blocks(
                action_id=action.id, chat_id=chat_id, bot_id=bot_id
            )

            await TelegramAPI().send_message(
                bot_token,
                chat_id,
                f"✅ Ação executada!\n"
                f"📦 {len(message_ids)} blocos enviados\n"
                f"🎯 Debug /{action_name} executado com sucesso",
            )

            return {
                "success": True,
                "action_id": action.id,
                "action_name": action.action_name,
                "messages_sent": len(message_ids),
            }

        except Exception as e:
            logger.error(
                "Erro no comando debug de ação",
                extra={"error": str(e), "bot_id": bot_id, "action_name": action_name},
            )
            await TelegramAPI().send_message(
                bot_token, chat_id, f"❌ Erro ao disparar ação: {str(e)}"
            )
            return {"success": False, "error": str(e)}

    @staticmethod
    async def handle_offer_pitch(
        bot_id: int,
        chat_id: int,
        user_telegram_id: int,
        offer_name: str,
        bot_token: str,
    ) -> Dict:
        """
        Envia o pitch de uma oferta específica

        Args:
            bot_id: ID do bot
            chat_id: ID do chat
            user_telegram_id: ID do usuário
            offer_name: Nome da oferta
            bot_token: Token do bot

        Returns:
            Dict com resultado do envio
        """
        try:
            logger.info(
                "Debug: Enviando pitch de oferta",
                extra={"bot_id": bot_id, "chat_id": chat_id, "offer_name": offer_name},
            )

            # Buscar oferta
            offer = await OfferRepository.get_by_name(bot_id, offer_name)

            if not offer:
                await TelegramAPI().send_message(
                    bot_token,
                    chat_id,
                    f"⚠️ Oferta '{offer_name}' não encontrada.\n"
                    f"Use o nome exato da oferta cadastrada.",
                )
                return {"success": False, "error": "offer_not_found"}

            if not offer.is_active:
                await TelegramAPI().send_message(
                    bot_token, chat_id, f"⚠️ A oferta '{offer_name}' está desativada."
                )
                return {"success": False, "error": "offer_inactive"}

            # Enviar mensagem de debug
            await TelegramAPI().send_message(
                bot_token,
                chat_id,
                f"🎯 Enviando pitch da oferta: {offer.name}\n"
                f"💰 Valor: R$ {offer.price}\n\n"
                f"Enviando blocos do pitch...",
            )

            # Enviar pitch
            sender = PitchSenderService(bot_token)
            message_ids = await sender.send_pitch(
                offer_id=offer.id,
                chat_id=chat_id,
                bot_id=bot_id,
                user_telegram_id=user_telegram_id,
            )

            await TelegramAPI().send_message(
                bot_token,
                chat_id,
                f"✅ Pitch enviado!\n"
                f"📦 {len(message_ids)} blocos enviados\n"
                f"🎯 Debug /{offer_name} executado com sucesso",
            )

            return {
                "success": True,
                "offer_id": offer.id,
                "offer_name": offer.name,
                "messages_sent": len(message_ids),
            }

        except Exception as e:
            logger.error(
                "Erro no comando debug de pitch",
                extra={"error": str(e), "bot_id": bot_id, "offer_name": offer_name},
            )
            await TelegramAPI().send_message(
                bot_token, chat_id, f"❌ Erro ao enviar pitch: {str(e)}"
            )
            return {"success": False, "error": str(e)}


async def _send_media(
    bot_token: str,
    chat_id: int,
    file_id: str,
    media_type: str,
    caption: Optional[str] = None,
) -> bool:
    """
    Helper para enviar mídia

    Args:
        bot_token: Token do bot
        chat_id: ID do chat
        file_id: ID do arquivo
        media_type: Tipo da mídia
        caption: Legenda opcional

    Returns:
        True se enviou com sucesso
    """
    try:
        api = TelegramAPI()

        if media_type == "photo":
            await api.send_photo(bot_token, chat_id, file_id, caption)
        elif media_type == "video":
            await api.send_video(bot_token, chat_id, file_id, caption)
        elif media_type == "document":
            await api.send_document(bot_token, chat_id, file_id, caption)
        elif media_type == "audio":
            await api.send_audio(bot_token, chat_id, file_id, caption)
        else:
            logger.warning(f"Tipo de mídia não suportado: {media_type}")
            return False

        return True

    except Exception as e:
        logger.error(
            "Erro ao enviar mídia", extra={"error": str(e), "media_type": media_type}
        )
        return False


async def handle_debug_help(bot_id: int, chat_id: int, bot_token: str) -> Dict:
    """
    Lista todos os comandos de debug disponíveis

    Args:
        bot_id: ID do bot
        chat_id: ID do chat
        bot_token: Token do bot

    Returns:
        Dict com informações de ajuda
    """
    try:
        from database.repos import AIActionRepository, OfferRepository

        logger.info(
            "Debug: Listando comandos disponíveis",
            extra={"bot_id": bot_id, "chat_id": chat_id},
        )

        # Buscar ações ativas
        actions = await AIActionRepository.get_actions_by_bot(bot_id, active_only=True)

        # Buscar ofertas ativas
        offers = await OfferRepository.get_offers_by_bot(bot_id, active_only=True)

        # Montar mensagem de ajuda
        help_text = "🛠 **COMANDOS DE DEBUG DISPONÍVEIS**\n\n"
        help_text += "📌 **Comandos Fixos:**\n"
        help_text += (
            "• `/vendaaprovada` - Simula pagamento aprovado e entrega conteúdo\n"
        )
        help_text += "• `/debug_help` - Mostra esta lista de comandos\n\n"

        if actions:
            help_text += "🎯 **Ações Personalizadas:**\n"
            for action in actions:
                help_text += f"• `/{action.action_name}` - {action.description or 'Dispara ação'}\n"
            help_text += "\n"

        if offers:
            help_text += "💰 **Ofertas (Pitch):**\n"
            for offer in offers:
                help_text += f"• `/{offer.name}` - Envia pitch (R$ {offer.price})\n"
            help_text += "\n"

        if not actions and not offers:
            help_text += "⚠️ *Nenhuma ação ou oferta ativa encontrada*\n\n"

        help_text += "📝 **Como usar:**\n"
        help_text += "1. Digite o comando exatamente como mostrado\n"
        help_text += "2. Os comandos simulam o comportamento real\n"
        help_text += "3. Use para testar fluxos sem pagamento real\n\n"
        help_text += "⚡ **Debug Mode Ativo**"

        api = TelegramAPI()
        await api.send_message(bot_token, chat_id, help_text, parse_mode="Markdown")

        return {
            "success": True,
            "actions_count": len(actions),
            "offers_count": len(offers),
        }

    except Exception as e:
        logger.error(
            "Erro ao listar comandos de debug",
            extra={"error": str(e), "bot_id": bot_id},
        )
        api = TelegramAPI()
        await api.send_message(
            bot_token, chat_id, f"❌ Erro ao listar comandos: {str(e)}"
        )
        return {"success": False, "error": str(e)}
