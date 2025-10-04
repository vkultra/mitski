"""
Serviço principal de gerenciamento de ações
"""

from typing import Dict, List, Optional

from core.telemetry import logger
from database.repos import AIActionRepository, UserActionStatusRepository

from .action_detector import ActionDetectorService
from .action_sender import ActionSenderService


class ActionService:
    """Serviço principal para gerenciar ações da IA"""

    @staticmethod
    async def process_ai_message_for_actions(
        bot_id: int,
        chat_id: int,
        user_telegram_id: int,
        ai_message: str,
        bot_token: str,
    ) -> Optional[Dict]:
        """
        Processa mensagem da IA para detectar e substituir ações

        Args:
            bot_id: ID do bot
            chat_id: ID do chat
            user_telegram_id: ID do usuário no Telegram
            ai_message: Mensagem gerada pela IA
            bot_token: Token do bot

        Returns:
            Dict com informações da ação processada ou None
        """
        # Detectar ações na mensagem
        action = await ActionDetectorService.detect_action_in_message(
            bot_id, ai_message
        )

        if not action:
            return None

        logger.info(
            "Processing action in AI message",
            extra={
                "bot_id": bot_id,
                "chat_id": chat_id,
                "user_telegram_id": user_telegram_id,
                "action_id": action.id,
                "action_name": action.action_name,
                "track_usage": action.track_usage,
            },
        )

        # Se tem rastreamento ativo, atualizar status para ACTIVATED
        if action.track_usage:
            await UserActionStatusRepository.update_status_to_activated(
                bot_id, user_telegram_id, action.id
            )

        # Verificar se deve substituir ou adicionar
        should_replace = ActionDetectorService.should_replace_message(
            ai_message, action.action_name
        )

        # Inicializar sender
        sender = ActionSenderService(bot_token)

        # Se deve substituir completamente
        if should_replace:
            # Enviar apenas os blocos da ação
            message_ids = await sender.send_action_blocks(
                action_id=action.id, chat_id=chat_id, bot_id=bot_id
            )

            return {
                "action_detected": True,
                "action_id": action.id,
                "action_name": action.action_name,
                "replaced_message": True,
                "messages_sent": len(message_ids),
            }

        # Se não deve substituir, retornar que a ação foi detectada
        # mas deixar o sistema enviar a mensagem original primeiro
        return {
            "action_detected": True,
            "action_id": action.id,
            "action_name": action.action_name,
            "replaced_message": False,
            "should_append_blocks": True,
        }

    @staticmethod
    async def send_action_blocks_after_message(
        action_id: int,
        chat_id: int,
        bot_token: str,
        bot_id: Optional[int] = None,
    ) -> int:
        """
        Envia blocos da ação após mensagem original

        Args:
            action_id: ID da ação
            chat_id: ID do chat
            bot_token: Token do bot
            bot_id: ID do bot (para cache de mídia)

        Returns:
            Número de mensagens enviadas
        """
        sender = ActionSenderService(bot_token)
        message_ids = await sender.send_action_blocks(
            action_id=action_id, chat_id=chat_id, bot_id=bot_id
        )

        return len(message_ids)

    @staticmethod
    async def get_tracked_actions_status(
        bot_id: int, user_telegram_id: int
    ) -> Dict[str, str]:
        """
        Retorna status das ações rastreadas para incluir no prompt

        Args:
            bot_id: ID do bot
            user_telegram_id: ID do usuário

        Returns:
            Dict com nome_ação: status (INACTIVE/ACTIVATED)
        """
        # Buscar apenas ações com rastreamento ativo
        tracked_actions = await AIActionRepository.get_tracked_actions(bot_id)

        if not tracked_actions:
            return {}

        # Buscar status de cada ação
        action_ids = [a.id for a in tracked_actions]
        statuses = await UserActionStatusRepository.get_user_action_statuses(
            bot_id, user_telegram_id, action_ids
        )

        # Criar dict com nome da ação -> status
        result = {}
        for action in tracked_actions:
            status = statuses.get(action.id, "INACTIVE")
            result[action.action_name] = status

        return result

    @staticmethod
    async def validate_action_creation(
        bot_id: int,
        action_name: str,
    ) -> Dict[str, any]:
        """
        Valida criação de nova ação

        Args:
            bot_id: ID do bot
            action_name: Nome da ação (será o gatilho)

        Returns:
            Dict com resultado da validação
        """
        # Verificar se já existe
        existing = await AIActionRepository.get_action_by_name(bot_id, action_name)

        if existing:
            return {
                "valid": False,
                "error": "Já existe uma ação com este nome",
            }

        # Validar comprimento
        if len(action_name) < 2:
            return {
                "valid": False,
                "error": "Nome muito curto (mínimo 2 caracteres)",
            }

        if len(action_name) > 128:
            return {
                "valid": False,
                "error": "Nome muito longo (máximo 128 caracteres)",
            }

        # Validar caracteres especiais problemáticos
        if any(char in action_name for char in ["/", "\\", "<", ">", "|"]):
            return {
                "valid": False,
                "error": "Nome contém caracteres inválidos",
            }

        return {"valid": True}
