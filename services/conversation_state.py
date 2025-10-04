"""
Conversation State Manager
Gerencia estado conversacional isolado por usuário usando Redis
"""

import json
from typing import Any, Dict, Optional

from core.redis_client import redis_client
from core.telemetry import logger


class ConversationStateManager:
    """Gerenciador de estado conversacional com Redis"""

    TTL_SECONDS = 300  # 5 minutos

    @staticmethod
    def _get_key(user_id: int) -> str:
        """Gera chave Redis para usuário"""
        return f"conversation:{user_id}"

    @classmethod
    def set_state(
        cls, user_id: int, state: str, data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Define estado conversacional do usuário

        Args:
            user_id: ID do usuário no Telegram
            state: Estado atual (ex: "awaiting_bot_name", "awaiting_bot_token")
            data: Dados adicionais do contexto

        Returns:
            bool: True se salvou com sucesso
        """
        try:
            key = cls._get_key(user_id)
            value = {"state": state, "data": data or {}}

            redis_client.setex(key, cls.TTL_SECONDS, json.dumps(value))

            logger.info(
                "Conversation state set", extra={"user_id": user_id, "state": state}
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to set conversation state",
                extra={"user_id": user_id, "error": str(e)},
            )
            return False

    @classmethod
    def get_state(cls, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Recupera estado conversacional do usuário

        Args:
            user_id: ID do usuário no Telegram

        Returns:
            Dict com state e data, ou None se não existe
        """
        try:
            key = cls._get_key(user_id)
            value = redis_client.get(key)

            if not value:
                return None

            return json.loads(value)

        except Exception as e:
            logger.error(
                "Failed to get conversation state",
                extra={"user_id": user_id, "error": str(e)},
            )
            return None

    @classmethod
    def clear_state(cls, user_id: int) -> bool:
        """
        Limpa estado conversacional do usuário

        Args:
            user_id: ID do usuário no Telegram

        Returns:
            bool: True se limpou com sucesso
        """
        try:
            key = cls._get_key(user_id)
            redis_client.delete(key)

            logger.info("Conversation state cleared", extra={"user_id": user_id})
            return True

        except Exception as e:
            logger.error(
                "Failed to clear conversation state",
                extra={"user_id": user_id, "error": str(e)},
            )
            return False

    @classmethod
    def update_data(cls, user_id: int, key: str, value: Any) -> bool:
        """
        Atualiza campo específico nos dados do estado

        Args:
            user_id: ID do usuário no Telegram
            key: Chave do dado a atualizar
            value: Valor a ser definido

        Returns:
            bool: True se atualizou com sucesso
        """
        try:
            current_state = cls.get_state(user_id)
            if not current_state:
                return False

            current_state["data"][key] = value

            redis_key = cls._get_key(user_id)
            redis_client.setex(redis_key, cls.TTL_SECONDS, json.dumps(current_state))

            return True

        except Exception as e:
            logger.error(
                "Failed to update conversation data",
                extra={"user_id": user_id, "key": key, "error": str(e)},
            )
            return False
