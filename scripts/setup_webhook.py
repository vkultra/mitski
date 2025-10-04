#!/usr/bin/env python3
"""
Script para configurar webhook do bot gerenciador
"""
import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv()


async def setup_webhook():
    """Configura webhook do bot gerenciador no Telegram"""
    token = os.environ.get("MANAGER_BOT_TOKEN")
    webhook_url = f"{os.environ.get('WEBHOOK_BASE_URL')}/webhook/manager"
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET")

    if not token:
        print("❌ MANAGER_BOT_TOKEN não configurado no .env")
        return

    if not secret:
        print("❌ TELEGRAM_WEBHOOK_SECRET não configurado no .env")
        return

    print("🔧 Configurando webhook...")
    print(f"📍 URL: {webhook_url}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Define webhook
        response = await client.post(
            f"https://api.telegram.org/bot{token}/setWebhook",
            json={
                "url": webhook_url,
                "secret_token": secret,
                "allowed_updates": ["message", "callback_query"],
                "drop_pending_updates": True,
            },
        )

        result = response.json()

        if result.get("ok"):
            print("✅ Webhook configurado com sucesso!")
        else:
            print(f"❌ Erro: {result.get('description')}")

        # Verifica configuração
        info_response = await client.get(
            f"https://api.telegram.org/bot{token}/getWebhookInfo"
        )

        info = info_response.json()

        if info.get("ok"):
            webhook_info = info["result"]
            print("\n📋 Informações do Webhook:")
            print(f"  URL: {webhook_info.get('url')}")
            print(f"  Pending updates: {webhook_info.get('pending_update_count', 0)}")
            print(f"  Last error: {webhook_info.get('last_error_message', 'None')}")


if __name__ == "__main__":
    asyncio.run(setup_webhook())
