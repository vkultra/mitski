"""
Roteador para comandos de debug - integra com o sistema principal
"""

from typing import Optional

from core.telemetry import logger
from database.repos import AIActionRepository, OfferRepository

from .debug_commands import DebugCommandHandler


class DebugCommandRouter:
    """Roteador que identifica e direciona comandos de debug"""

    @staticmethod
    async def is_debug_command(text: str) -> bool:
        """
        Verifica se o texto é um comando de debug

        Args:
            text: Texto da mensagem

        Returns:
            True se for comando de debug
        """
        if not text or not text.startswith("/"):
            return False

        # Comandos fixos de debug
        if text.lower() in [
            "/vendaaprovada",
            "/venda_aprovada",
            "/debug_help",
            "/debug",
        ]:
            return True

        # Remover a barra inicial
        command = text[1:].lower()

        # Verificar se é um comando dinâmico (ação ou oferta)
        # Isso será validado posteriormente ao processar
        return True  # Retorna True para todos os comandos iniciados com /

    @staticmethod
    async def route_debug_command(
        bot_id: int, chat_id: int, user_telegram_id: int, text: str, bot_token: str
    ) -> Optional[dict]:
        """
        Roteia comando de debug para o handler apropriado

        Args:
            bot_id: ID do bot
            chat_id: ID do chat
            user_telegram_id: ID do usuário
            text: Texto do comando
            bot_token: Token do bot

        Returns:
            Resultado do comando ou None se não for debug
        """
        if not text or not text.startswith("/"):
            return None

        # Normalizar comando
        command = text[1:].strip()  # Remove a barra inicial
        command_lower = command.lower()

        logger.info(
            "Processing debug command",
            extra={
                "bot_id": bot_id,
                "chat_id": chat_id,
                "command": command,
                "user_telegram_id": user_telegram_id,
            },
        )

        # Comando: /debug_help ou /debug
        if command_lower in ["debug_help", "debug"]:
            from .debug_commands import handle_debug_help

            return await handle_debug_help(
                bot_id=bot_id, chat_id=chat_id, bot_token=bot_token
            )

        # Comando: /vendaaprovada (com suporte a verbose)
        if command_lower.startswith("vendaaprovada") or command_lower.startswith(
            "venda_aprovada"
        ):
            # Verificar se tem parâmetro verbose
            verbose = "verbose" in command_lower or "v" in command_lower.split()
            return await DebugCommandHandler.handle_venda_aprovada(
                bot_id=bot_id,
                chat_id=chat_id,
                user_telegram_id=user_telegram_id,
                bot_token=bot_token,
                verbose=verbose,
            )

        # Verificar se é uma ação (termo de ações)
        # Separar comando base e verificar verbose
        parts = command.split()
        base_command = parts[0] if parts else command
        verbose = len(parts) > 1 and parts[1].lower() in ["verbose", "v"]

        action = await AIActionRepository.get_action_by_name(bot_id, base_command)
        if action and action.is_active:
            logger.info(
                "Debug command matched action",
                extra={
                    "bot_id": bot_id,
                    "action_name": action.action_name,
                    "action_id": action.id,
                    "verbose": verbose,
                },
            )
            return await DebugCommandHandler.handle_trigger_action(
                bot_id=bot_id,
                chat_id=chat_id,
                action_name=base_command,
                bot_token=bot_token,
                verbose=verbose,
            )

        # Verificar se é uma oferta
        offer = await OfferRepository.get_offer_by_name(bot_id, base_command)
        if offer and offer.is_active:
            logger.info(
                "Debug command matched offer",
                extra={
                    "bot_id": bot_id,
                    "offer_name": offer.name,
                    "offer_id": offer.id,
                    "verbose": verbose,
                },
            )
            return await DebugCommandHandler.handle_offer_pitch(
                bot_id=bot_id,
                chat_id=chat_id,
                user_telegram_id=user_telegram_id,
                offer_name=base_command,
                bot_token=bot_token,
                verbose=verbose,
            )

        # Se não é nenhum comando reconhecido, retorna None
        logger.debug(
            "Command not recognized as debug command",
            extra={"bot_id": bot_id, "command": command},
        )
        return None

    @staticmethod
    async def list_available_debug_commands(bot_id: int) -> dict:
        """
        Lista todos os comandos de debug disponíveis para um bot

        Args:
            bot_id: ID do bot

        Returns:
            Dict com comandos disponíveis
        """
        # Buscar ações ativas
        actions = await AIActionRepository.get_actions_by_bot(bot_id, active_only=True)
        action_commands = [f"/{action.action_name}" for action in actions]

        # Buscar ofertas ativas
        offers = await OfferRepository.get_offers_by_bot(bot_id, active_only=True)
        offer_commands = [f"/{offer.name}" for offer in offers]

        return {
            "fixed_commands": [
                {
                    "command": "/vendaaprovada",
                    "description": "Simula pagamento aprovado e entrega conteúdo",
                }
            ],
            "action_commands": action_commands,
            "offer_commands": offer_commands,
            "total": 1 + len(action_commands) + len(offer_commands),
        }
