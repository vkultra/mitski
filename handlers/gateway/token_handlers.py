"""
Handlers para gerenciamento de tokens de gateway
"""

from typing import Any, Dict

from core.config import settings
from core.telemetry import logger
from services.conversation_state import ConversationStateManager
from services.gateway.gateway_service import GatewayService


async def handle_request_token(user_id: int) -> Dict[str, Any]:
    """
    Inicia fluxo para adicionar token

    Args:
        user_id: ID do usuário

    Returns:
        Dict com mensagem
    """
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    # Inicia estado conversacional
    ConversationStateManager.set_state(user_id, "awaiting_gateway_token")

    return {
        "text": "🔑 *Configurar Token PushinPay*\n\n"
        "Por favor, envie seu token de autenticação PushinPay:\n\n"
        "_O token será validado e armazenado de forma segura (criptografado)._",
        "keyboard": None,
    }


async def handle_token_input(user_id: int, token: str) -> Dict[str, Any]:
    """
    Processa token enviado pelo usuário

    Args:
        user_id: ID do usuário
        token: Token enviado

    Returns:
        Dict com mensagem de confirmação ou erro
    """
    token = token.strip()

    if len(token) < 20:
        return {
            "text": "❌ Token inválido. Por favor, envie um token válido:",
            "keyboard": None,
        }

    try:
        # Valida e salva token
        success = await GatewayService.validate_and_save_token(
            user_id, token, "pushinpay"
        )

        if success:
            # Limpa estado
            ConversationStateManager.clear_state(user_id)

            logger.info(
                "Gateway token configured",
                extra={"user_id": user_id},
            )

            return {
                "text": "✅ *Token configurado com sucesso!*\n\n"
                "Seu token PushinPay foi validado e salvo de forma segura.\n\n"
                "Agora você pode usar a tag `{pix}` em suas ofertas para gerar "
                "pagamentos PIX automaticamente.",
                "keyboard": None,
            }
        else:
            return {
                "text": "❌ Não foi possível validar o token. Tente novamente:",
                "keyboard": None,
            }

    except ValueError as e:
        logger.warning(
            "Token validation failed",
            extra={"user_id": user_id, "error": str(e)},
        )
        return {
            "text": f"❌ {str(e)}\n\nPor favor, verifique seu token e tente novamente:",
            "keyboard": None,
        }
    except Exception as e:
        logger.error(
            "Error saving gateway token",
            extra={"user_id": user_id, "error": str(e)},
        )
        return {
            "text": f"❌ Erro ao salvar token: {str(e)}\n\nTente novamente mais tarde.",
            "keyboard": None,
        }


async def handle_edit_token(user_id: int) -> Dict[str, Any]:
    """
    Menu para editar token

    Args:
        user_id: ID do usuário

    Returns:
        Dict com opções
    """
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    keyboard = {
        "inline_keyboard": [
            [{"text": "🔄 Atualizar Token", "callback_data": "gateway_update_token"}],
            [{"text": "🗑️ Remover Token", "callback_data": "gateway_delete_token"}],
            [{"text": "🔙 Voltar", "callback_data": "gateway_pushinpay"}],
        ]
    }

    return {
        "text": "🔑 *Gerenciar Token PushinPay*\n\nEscolha uma opção:",
        "keyboard": keyboard,
    }


async def handle_update_token(user_id: int) -> Dict[str, Any]:
    """
    Inicia fluxo para atualizar token existente

    Args:
        user_id: ID do usuário

    Returns:
        Dict com mensagem
    """
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    # Inicia estado conversacional
    ConversationStateManager.set_state(user_id, "awaiting_gateway_token")

    return {
        "text": "🔄 *Atualizar Token PushinPay*\n\n"
        "Por favor, envie o novo token de autenticação PushinPay:\n\n"
        "_O token será validado e substituirá o token atual._",
        "keyboard": None,
    }


async def handle_delete_token(user_id: int) -> Dict[str, Any]:
    """
    Remove token do gateway

    Args:
        user_id: ID do usuário

    Returns:
        Dict com mensagem de confirmação
    """
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    try:
        success = await GatewayService.delete_token(user_id, "pushinpay")

        if success:
            logger.info(
                "Gateway token deleted",
                extra={"user_id": user_id},
            )

            return {
                "text": "✅ *Token removido com sucesso!*\n\n"
                "Seu token PushinPay foi deletado.\n\n"
                "Configure um novo token para voltar a aceitar pagamentos PIX.",
                "keyboard": None,
            }
        else:
            return {
                "text": "❌ Token não encontrado ou já foi removido.",
                "keyboard": None,
            }

    except Exception as e:
        logger.error(
            "Error deleting gateway token",
            extra={"user_id": user_id, "error": str(e)},
        )
        return {
            "text": f"❌ Erro ao remover token: {str(e)}\n\nTente novamente mais tarde.",
            "keyboard": None,
        }
