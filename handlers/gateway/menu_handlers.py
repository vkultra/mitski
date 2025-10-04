"""
Handlers de menu de gateway
"""

from typing import Any, Dict

from core.config import settings
from services.gateway.gateway_service import GatewayService


async def handle_gateway_menu(user_id: int) -> Dict[str, Any]:
    """
    Menu principal de gateway

    Args:
        user_id: ID do usuário

    Returns:
        Dict com texto e teclado
    """
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    keyboard = {
        "inline_keyboard": [
            [{"text": "💳 PushinPay", "callback_data": "gateway_pushinpay"}],
            [{"text": "🔙 Voltar", "callback_data": "start"}],
        ]
    }

    return {
        "text": "💳 *Gateway de Pagamento*\n\nSelecione um gateway:",
        "keyboard": keyboard,
    }


async def handle_pushinpay_menu(user_id: int) -> Dict[str, Any]:
    """
    Menu do PushinPay

    Args:
        user_id: ID do usuário

    Returns:
        Dict com texto e teclado
    """
    if user_id not in settings.allowed_admin_ids_list:
        return {"text": "⛔ Acesso negado.", "keyboard": None}

    # Verifica se tem token configurado
    has_token = await GatewayService.get_config_status(user_id, "pushinpay")

    status_text = "✅ Configurado" if has_token else "❌ Não configurado"

    buttons = []

    if has_token:
        buttons.append(
            [{"text": "🔑 Editar Token", "callback_data": "gateway_edit_token"}]
        )
        buttons.append(
            [
                {
                    "text": "🤖 Tokens por Bot",
                    "callback_data": "gateway_bot_tokens",
                }
            ]
        )
    else:
        buttons.append(
            [{"text": "➕ Configurar Token", "callback_data": "gateway_add_token"}]
        )

    buttons.append([{"text": "🔙 Voltar", "callback_data": "gateway_menu"}])

    keyboard = {"inline_keyboard": buttons}

    return {
        "text": f"💳 *PushinPay*\n\n"
        f"Status: {status_text}\n\n"
        f"Configure seu token para começar a aceitar pagamentos PIX.",
        "keyboard": keyboard,
    }
