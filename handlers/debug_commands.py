"""
Comandos de debug para testar o sistema de ações, ofertas e pagamentos
"""

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
        verbose: bool = False,
    ) -> Dict:
        """
        Simula uma venda aprovada e entrega o conteúdo

        Args:
            bot_id: ID do bot
            chat_id: ID do chat
            user_telegram_id: ID do usuário
            bot_token: Token do bot
            offer_name: Nome da oferta (opcional, pega a primeira se não especificado)
            verbose: Se True, mostra mensagens de debug (default: False)

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
                offer = await OfferRepository.get_offer_by_name(bot_id, offer_name)
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

            # Simular transação paga (apenas se verbose)
            if verbose:
                await TelegramAPI().send_message(
                    bot_token,
                    chat_id,
                    f"✅ Simulando pagamento aprovado para oferta: {offer.name}\n"
                    f"💰 Valor: {offer.value or 'Sem valor definido'}\n\n"
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

            # Ativar fluxo de upsell (simular cenário real)
            from workers.upsell_tasks import activate_upsell_flow

            activate_upsell_flow.delay(
                user_id=user_telegram_id,
                bot_id=bot_id,
                transaction_id=0,  # ID fictício para debug
            )

            # Mensagem de confirmação (apenas se verbose)
            if verbose:
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
        bot_id: int,
        chat_id: int,
        action_name: str,
        bot_token: str,
        verbose: bool = False,
    ) -> Dict:
        """
        Dispara uma ação personalizada pelo nome

        Args:
            bot_id: ID do bot
            chat_id: ID do chat
            action_name: Nome da ação
            bot_token: Token do bot
            verbose: Se True, mostra mensagens de debug (default: False)

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
            action = await AIActionRepository.get_action_by_name(bot_id, action_name)

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

            # Enviar mensagem de debug (apenas se verbose)
            if verbose:
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

            # Mensagem de confirmação (apenas se verbose)
            if verbose:
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
        verbose: bool = False,
    ) -> Dict:
        """
        Envia o pitch de uma oferta específica

        Args:
            bot_id: ID do bot
            chat_id: ID do chat
            user_telegram_id: ID do usuário
            offer_name: Nome da oferta
            bot_token: Token do bot
            verbose: Se True, mostra mensagens de debug (default: False)

        Returns:
            Dict com resultado do envio
        """
        try:
            logger.info(
                "Debug: Enviando pitch de oferta",
                extra={"bot_id": bot_id, "chat_id": chat_id, "offer_name": offer_name},
            )

            # Buscar oferta
            offer = await OfferRepository.get_offer_by_name(bot_id, offer_name)

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

            # Enviar mensagem de debug (apenas se verbose)
            if verbose:
                await TelegramAPI().send_message(
                    bot_token,
                    chat_id,
                    f"🎯 Enviando pitch da oferta: {offer.name}\n"
                    f"💰 Valor: {offer.value or 'Sem valor definido'}\n\n"
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

            # Mensagem de confirmação (apenas se verbose)
            if verbose:
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

    @staticmethod
    async def handle_venda_upsell(
        bot_id: int,
        chat_id: int,
        user_telegram_id: int,
        bot_token: str,
        upsell_name: Optional[str] = None,
        verbose: bool = False,
    ) -> Dict:
        """
        Simula pagamento de upsell aprovado e entrega conteúdo

        Args:
            bot_id: ID do bot
            chat_id: ID do chat
            user_telegram_id: ID do usuário
            bot_token: Token do bot
            upsell_name: Nome do upsell (opcional, pega o primeiro se não especificado)
            verbose: Se True, mostra mensagens de debug (default: False)

        Returns:
            Dict com resultado da simulação
        """
        try:
            from database.repos import (
                UpsellDeliverableBlockRepository,
                UpsellRepository,
                UserUpsellHistoryRepository,
            )

            logger.info(
                "Debug: Simulando venda de upsell aprovada",
                extra={
                    "bot_id": bot_id,
                    "chat_id": chat_id,
                    "user_telegram_id": user_telegram_id,
                    "upsell_name": upsell_name,
                },
            )

            # Buscar upsell
            if upsell_name:
                # Buscar por nome (implementar método no repo se necessário)
                upsells = await UpsellRepository.get_upsells_by_bot(bot_id)
                upsell = next((u for u in upsells if u.name == upsell_name), None)
            else:
                # Pegar primeiro upsell ativo do bot
                upsells = await UpsellRepository.get_upsells_by_bot(bot_id)
                upsell = upsells[0] if upsells else None

            if not upsell:
                await TelegramAPI().send_message(
                    bot_token,
                    chat_id,
                    "⚠️ Nenhum upsell encontrado para simular venda.",
                )
                return {"success": False, "error": "no_upsell_found"}

            # Buscar blocos de entregável do upsell
            deliverable_blocks = (
                await UpsellDeliverableBlockRepository.get_blocks_by_upsell(upsell.id)
            )

            if not deliverable_blocks:
                await TelegramAPI().send_message(
                    bot_token,
                    chat_id,
                    f"⚠️ O upsell '{upsell.name}' não tem conteúdo de entrega configurado.",
                )
                return {"success": False, "error": "no_deliverable_content"}

            # Simular transação paga (apenas se verbose)
            if verbose:
                await TelegramAPI().send_message(
                    bot_token,
                    chat_id,
                    f"✅ Simulando pagamento aprovado para upsell: {upsell.name}\n"
                    f"💰 Valor: {upsell.value or 'Sem valor definido'}\n\n"
                    f"Entregando conteúdo...",
                )

            # Usar DeliverableSender igual ao sistema real
            from services.upsell.deliverable_sender import DeliverableSender

            sender = DeliverableSender(bot_token)
            await sender.send_deliverable(
                upsell_id=upsell.id,
                chat_id=chat_id,
                bot_id=bot_id,
            )

            # Marcar como pago no histórico
            await UserUpsellHistoryRepository.mark_paid(
                bot_id=bot_id,
                user_telegram_id=user_telegram_id,
                upsell_id=upsell.id,
                transaction_id=f"debug_{upsell.id}_{user_telegram_id}",
            )

            # Agendar próximo upsell (como no fluxo real)
            from services.upsell.scheduler import UpsellScheduler

            await UpsellScheduler.schedule_next_upsell(user_telegram_id, bot_id)

            # Mensagem de confirmação (apenas se verbose)
            if verbose:
                await TelegramAPI().send_message(
                    bot_token,
                    chat_id,
                    f"✅ Entrega concluída!\n"
                    f"📦 {len(deliverable_blocks)} blocos entregues\n"
                    f"🎯 Debug /vendaupsell executado com sucesso",
                )

            return {
                "success": True,
                "upsell_id": upsell.id,
                "upsell_name": upsell.name,
                "blocks_sent": len(deliverable_blocks),
            }

        except Exception as e:
            logger.error(
                "Erro no comando debug /vendaupsell",
                extra={"error": str(e), "bot_id": bot_id},
            )
            await TelegramAPI().send_message(
                bot_token, chat_id, f"❌ Erro ao simular venda de upsell: {str(e)}"
            )
            return {"success": False, "error": str(e)}

    @staticmethod
    async def handle_upsell_inicial(
        bot_id: int,
        chat_id: int,
        user_telegram_id: int,
        bot_token: str,
        verbose: bool = False,
    ) -> Dict:
        """
        Simula detecção de trigger pela IA e envia anúncio do upsell inicial

        Args:
            bot_id: ID do bot
            chat_id: ID do chat
            user_telegram_id: ID do usuário
            bot_token: Token do bot
            verbose: Se True, mostra mensagens de debug (default: False)

        Returns:
            Dict com resultado da simulação
        """
        try:
            from database.repos import (
                UpsellAnnouncementBlockRepository,
                UpsellRepository,
                UserUpsellHistoryRepository,
            )

            logger.info(
                "Debug: Simulando trigger de upsell inicial detectado",
                extra={
                    "bot_id": bot_id,
                    "chat_id": chat_id,
                    "user_telegram_id": user_telegram_id,
                },
            )

            # Buscar upsell #1 (pré-salvo)
            upsell_1 = await UpsellRepository.get_first_upsell(bot_id)

            if not upsell_1:
                await TelegramAPI().send_message(
                    bot_token,
                    chat_id,
                    "⚠️ Nenhum upsell inicial (#1) encontrado.\n"
                    "O upsell #1 é criado automaticamente ao cadastrar um bot.",
                )
                return {"success": False, "error": "no_initial_upsell"}

            # Verificar se tem trigger configurado
            if not upsell_1.upsell_trigger:
                await TelegramAPI().send_message(
                    bot_token,
                    chat_id,
                    f"⚠️ O upsell '{upsell_1.name}' não tem trigger configurado.\n"
                    f"Configure o trigger no menu de upsells.",
                )
                return {"success": False, "error": "no_trigger_configured"}

            # Buscar blocos de anúncio
            announcement_blocks = (
                await UpsellAnnouncementBlockRepository.get_blocks_by_upsell(
                    upsell_1.id
                )
            )

            if not announcement_blocks:
                await TelegramAPI().send_message(
                    bot_token,
                    chat_id,
                    f"⚠️ O upsell '{upsell_1.name}' não tem blocos de anúncio configurados.",
                )
                return {"success": False, "error": "no_announcement_blocks"}

            # Mensagem de debug (apenas se verbose)
            if verbose:
                await TelegramAPI().send_message(
                    bot_token,
                    chat_id,
                    f"🎯 Simulando trigger detectado: '{upsell_1.upsell_trigger}'\n"
                    f"📢 Upsell: {upsell_1.name}\n"
                    f"💰 Valor: {upsell_1.value or 'Sem valor definido'}\n\n"
                    f"Ativando fase e enviando anúncio...",
                )

            # Ativar fase do upsell (trocar prompt da IA)
            from services.upsell.phase_manager import UpsellPhaseManager

            await UpsellPhaseManager.activate_upsell_phase(
                bot_id, user_telegram_id, upsell_1.id
            )

            # Enviar anúncio
            from services.upsell.announcement_sender import AnnouncementSender

            sender = AnnouncementSender(bot_token)
            await sender.send_announcement(
                upsell_id=upsell_1.id,
                chat_id=chat_id,
                bot_id=bot_id,
            )

            # Marcar como enviado no histórico
            await UserUpsellHistoryRepository.mark_sent(
                bot_id=bot_id,
                user_telegram_id=user_telegram_id,
                upsell_id=upsell_1.id,
            )

            # Mensagem de confirmação (apenas se verbose)
            if verbose:
                await TelegramAPI().send_message(
                    bot_token,
                    chat_id,
                    f"✅ Anúncio enviado!\n"
                    f"📦 {len(announcement_blocks)} blocos enviados\n"
                    f"🔄 Fase da IA ativada\n"
                    f"🎯 Debug /upsellinicial executado com sucesso",
                )

            return {
                "success": True,
                "upsell_id": upsell_1.id,
                "upsell_name": upsell_1.name,
                "trigger": upsell_1.upsell_trigger,
                "blocks_sent": len(announcement_blocks),
            }

        except Exception as e:
            logger.error(
                "Erro no comando debug /upsellinicial",
                extra={"error": str(e), "bot_id": bot_id},
            )
            await TelegramAPI().send_message(
                bot_token, chat_id, f"❌ Erro ao simular trigger de upsell: {str(e)}"
            )
            return {"success": False, "error": str(e)}


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

        help_text += "💰 **Comandos de Upsell:**\n"
        help_text += (
            "• `/vendaupsell` - Simula pagamento de upsell aprovado e entrega\n"
        )
        help_text += "• `/upsellinicial` - Simula trigger detectado e envia anúncio\n\n"

        if actions:
            help_text += "🎯 **Ações Personalizadas:**\n"
            for action in actions:
                help_text += f"• `/{action.action_name}` - {action.description or 'Dispara ação'}\n"
            help_text += "\n"

        if offers:
            help_text += "💰 **Ofertas (Pitch):**\n"
            for offer in offers:
                help_text += (
                    f"• `/{offer.name}` - Envia pitch ({offer.value or 'Sem valor'})\n"
                )
            help_text += "\n"

        if not actions and not offers:
            help_text += "⚠️ *Nenhuma ação ou oferta ativa encontrada*\n\n"

        help_text += "📝 **Como usar:**\n"
        help_text += "1. Digite o comando exatamente como mostrado\n"
        help_text += (
            "2. **Modo Silencioso** (padrão): `/comando` - Simula 100% o real\n"
        )
        help_text += (
            "3. **Modo Verbose**: `/comando verbose` - Mostra mensagens de debug\n"
        )
        help_text += "4. Use para testar fluxos sem pagamento real\n\n"
        help_text += "💡 **Exemplos:**\n"
        help_text += "• `/vendaaprovada` - Entrega sem mensagens extras\n"
        help_text += "• `/vendaaprovada verbose` - Mostra progresso da simulação\n\n"
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

    @staticmethod
    async def handle_mirror_debug(
        bot_id: int,
        chat_id: int,
        user_telegram_id: int,
        bot_token: str,
    ) -> Dict:
        """
        Mostra informações de debug sobre configuração de espelhamento

        Args:
            bot_id: ID do bot
            chat_id: ID do chat
            user_telegram_id: ID do usuário
            bot_token: Token do bot

        Returns:
            Dict com resultado do debug
        """
        try:
            import json

            from core.redis_client import redis_client
            from database.models import MirrorGroup, UserTopic
            from database.repos import SessionLocal

            debug_info = []

            with SessionLocal() as session:
                # 1. Verifica MirrorGroup para este bot
                mirror_group = (
                    session.query(MirrorGroup).filter_by(bot_id=bot_id).first()
                )

                if mirror_group:
                    debug_info.append("✅ **MirrorGroup encontrado no banco:**")
                    debug_info.append(f"  • Bot ID: {mirror_group.bot_id}")
                    debug_info.append(f"  • Group ID: `{mirror_group.group_id}`")
                    debug_info.append(
                        f"  • Ativo: {'✅ Sim' if mirror_group.is_active else '❌ Não'}"
                    )
                    debug_info.append(
                        f"  • Usar gerenciador: {'✅ Sim' if mirror_group.use_manager_bot else '❌ Não'}"
                    )
                    if mirror_group.manager_group_id:
                        debug_info.append(
                            f"  • Grupo gerenciador: `{mirror_group.manager_group_id}`"
                        )
                    debug_info.append(f"  • Batch size: {mirror_group.batch_size}")
                    debug_info.append(f"  • Batch delay: {mirror_group.batch_delay}s")
                    debug_info.append(
                        f"  • Flush timeout: {mirror_group.flush_timeout}s"
                    )
                else:
                    debug_info.append("❌ **MirrorGroup NÃO encontrado no banco**")
                    debug_info.append(
                        "  • Espelhamento não está configurado para este bot"
                    )

                # 2. Verifica cache Redis
                cache_key = f"mirror_config:{bot_id}"
                cache_data = redis_client.get(cache_key)

                debug_info.append("\n🔄 **Cache Redis:**")
                if cache_data:
                    config = json.loads(cache_data)
                    debug_info.append(
                        f"  • ✅ Cache existe (TTL: {redis_client.ttl(cache_key)}s)"
                    )
                    debug_info.append(f"  • Group ID: `{config.get('group_id')}`")
                    debug_info.append(
                        f"  • Usar gerenciador: {config.get('use_manager_bot')}"
                    )
                else:
                    debug_info.append("  • ❌ Sem cache (será buscado do banco)")

                # 3. Verifica buffer para este usuário
                buffer_key = f"buffer:{bot_id}:{user_telegram_id}"
                buffer_count = redis_client.hget(buffer_key, "count")

                debug_info.append("\n📦 **Buffer de mensagens:**")
                if buffer_count:
                    debug_info.append(f"  • ✅ {buffer_count} mensagem(s) no buffer")
                    first_time = redis_client.hget(buffer_key, "first_message_time")
                    if first_time:
                        import time

                        age = int(time.time() - float(first_time))
                        debug_info.append(f"  • Idade do buffer: {age}s")
                else:
                    debug_info.append("  • ✅ Buffer vazio (normal)")

                # 4. Verifica tópico para este usuário
                user_topic = (
                    session.query(UserTopic)
                    .filter_by(bot_id=bot_id, user_telegram_id=user_telegram_id)
                    .first()
                )

                debug_info.append("\n💬 **Tópico do usuário:**")
                if user_topic:
                    debug_info.append(
                        f"  • ✅ Tópico criado (ID: {user_topic.topic_id})"
                    )
                    debug_info.append(
                        f"  • Mensagens espelhadas: {user_topic.messages_mirrored}"
                    )
                    if user_topic.last_batch_sent:
                        debug_info.append(
                            f"  • Último batch: {user_topic.last_batch_sent.strftime('%d/%m/%Y %H:%M')}"
                        )
                    debug_info.append(
                        f"  • Banido: {'❌ Sim' if user_topic.is_banned else '✅ Não'}"
                    )
                    debug_info.append(
                        f"  • IA pausada: {'⏸️ Sim' if user_topic.is_ai_paused else '▶️ Não'}"
                    )
                else:
                    debug_info.append("  • ⚠️ Tópico ainda não criado")
                    debug_info.append(
                        "  • Será criado automaticamente na próxima mensagem"
                    )

            text = "🔍 **DEBUG - ESPELHAMENTO**\n" + "─" * 30 + "\n\n"
            text += "\n".join(debug_info)
            text += "\n\n💡 Use este debug para verificar se tudo está configurado corretamente."

            api = TelegramAPI()
            await api.send_message(bot_token, chat_id, text, parse_mode="Markdown")

            return {
                "success": True,
                "has_mirror_group": (
                    mirror_group is not None if "mirror_group" in locals() else False
                ),
                "has_cache": (
                    cache_data is not None if "cache_data" in locals() else False
                ),
            }

        except Exception as e:
            logger.error(
                "Erro no comando debug de espelhamento",
                extra={"error": str(e), "bot_id": bot_id},
            )
            api = TelegramAPI()
            await api.send_message(bot_token, chat_id, f"❌ Erro no debug: {str(e)}")
            return {"success": False, "error": str(e)}
