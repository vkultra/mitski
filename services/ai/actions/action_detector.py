"""
Serviço de detecção de ações em mensagens da IA
"""

import re
from typing import List, Optional

from core.telemetry import logger
from database.repos import AIActionRepository


class ActionDetectorService:
    """Detecta gatilhos de ações nas mensagens da IA"""

    @staticmethod
    async def detect_action_in_message(
        bot_id: int, message: str
    ) -> Optional["AIAction"]:
        """
        Detecta se há alguma ação no texto da mensagem

        Args:
            bot_id: ID do bot
            message: Mensagem da IA

        Returns:
            Primeira ação detectada ou None
        """
        # Buscar todas as ações ativas do bot
        actions = await AIActionRepository.get_actions_by_bot(bot_id, active_only=True)

        if not actions:
            return None

        # Normalizar mensagem para busca
        message_lower = message.lower()

        # Verificar cada ação
        for action in actions:
            # Buscar nome da ação (case insensitive)
            action_name_lower = action.action_name.lower()

            # Verificar se o nome da ação aparece na mensagem
            if action_name_lower in message_lower:
                logger.info(
                    "Action detected in message",
                    extra={
                        "bot_id": bot_id,
                        "action_id": action.id,
                        "action_name": action.action_name,
                        "track_usage": action.track_usage,
                    },
                )
                return action

        return None

    @staticmethod
    def should_replace_message(message: str, action_name: str) -> bool:
        """
        Verifica se deve substituir a mensagem completa

        Se a mensagem é APENAS o nome da ação (ou muito similar),
        substitui completamente. Caso contrário, adiciona após.

        Args:
            message: Mensagem da IA
            action_name: Nome da ação detectada

        Returns:
            True se deve substituir completamente
        """
        # Remover espaços e pontuação para comparação
        clean_message = re.sub(r"[^\w\s]", "", message.strip()).lower()
        clean_action = re.sub(r"[^\w\s]", "", action_name.strip()).lower()

        # Se a mensagem limpa é exatamente o nome da ação
        if clean_message == clean_action:
            return True

        # Se a mensagem tem menos de 50 caracteres e contém principalmente a ação
        if len(message) < 50:
            # Calcular proporção do nome da ação na mensagem
            action_ratio = len(action_name) / len(message)
            if action_ratio > 0.7:  # 70% ou mais da mensagem é o nome da ação
                return True

        return False

    @staticmethod
    async def get_all_detected_actions(bot_id: int, message: str) -> List["AIAction"]:
        """
        Retorna todas as ações detectadas na mensagem

        Args:
            bot_id: ID do bot
            message: Mensagem da IA

        Returns:
            Lista de ações detectadas
        """
        detected = []
        actions = await AIActionRepository.get_actions_by_bot(bot_id, active_only=True)

        if not actions:
            return detected

        message_lower = message.lower()

        for action in actions:
            if action.action_name.lower() in message_lower:
                detected.append(action)

        return detected
