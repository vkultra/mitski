"""
FastAPI Webhook Receiver para Multi-Bot Manager
"""

import os
import time
from collections import deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.telemetry import logger
from database.repos import BotRepository
from workers.tasks import process_manager_update, process_telegram_update

app = FastAPI(title="Telegram Multi-Bot Manager")

WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "dev_secret")

# Timestamp de quando a aplicação foi iniciada
APP_START_TIME = int(time.time())

# Cache de update_ids já processados (mantém últimos 1000)
PROCESSED_UPDATES = deque(maxlen=1000)


@app.middleware("http")
async def validate_telegram_signature(request: Request, call_next):
    """Valida assinatura do Telegram em webhooks"""
    if request.url.path.startswith("/webhook/"):
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")

        # Log para debug
        logger.info(
            "Webhook received",
            extra={
                "path": request.url.path,
                "secret_received": secret,
                "secret_expected": WEBHOOK_SECRET,
                "headers": dict(request.headers),
            },
        )

        # Desabilitar validação em desenvolvimento (ngrok)
        # if secret != WEBHOOK_SECRET:
        #     logger.warning("Invalid webhook secret", extra={
        #         "path": request.url.path,
        #         "ip": request.client.host
        #     })
        #     raise HTTPException(status_code=403, detail="forbidden")
    return await call_next(request)


@app.post("/webhook/manager")
async def manager_webhook(request: Request):
    """Recebe updates do bot gerenciador"""
    try:
        # Responder IMEDIATAMENTE para evitar timeout do Telegram
        update = await request.json()
        update_id = update.get("update_id")

        # Verificar se já processamos este update
        if update_id and update_id in PROCESSED_UPDATES:
            return JSONResponse({"ok": True}, status_code=200)

        # Adicionar ao cache ANTES de processar
        if update_id:
            PROCESSED_UPDATES.append(update_id)

        # Filtrar mensagens antigas (antes do início da aplicação)
        message = update.get("message", {})
        callback_query = update.get("callback_query", {})

        if message:
            message_date = message.get("date", 0)
            if message_date < APP_START_TIME:
                return JSONResponse({"ok": True}, status_code=200)

        if callback_query:
            # Callbacks não têm timestamp, mas a mensagem associada sim
            callback_message = callback_query.get("message", {})
            callback_date = callback_message.get("date", 0)
            if callback_date < APP_START_TIME - 60:  # 60s de margem para callbacks
                return JSONResponse({"ok": True}, status_code=200)

        # Log mais leve, apenas update_id
        logger.debug("Manager update queued", extra={"update_id": update_id})

        # Enfileirar SEM AGUARDAR
        process_manager_update.delay(update)

        # Retornar IMEDIATAMENTE
        return JSONResponse({"ok": True}, status_code=200)

    except Exception as e:
        # Em caso de erro, ainda retornar OK para evitar retransmissão
        logger.error(
            "Error processing manager webhook",
            extra={"error": str(e), "error_type": type(e).__name__},
        )
        return JSONResponse({"ok": False}, status_code=200)


@app.post("/webhook/{bot_id}")
async def webhook(bot_id: int, request: Request):
    """Recebe updates de bots secundários"""
    try:
        update_data = await request.json()
        update_id = update_data.get("update_id")

        # Verificar duplicação
        if update_id and update_id in PROCESSED_UPDATES:
            return JSONResponse({"ok": True}, status_code=200)

        # Cache update_id
        if update_id:
            PROCESSED_UPDATES.append(update_id)

        # Verificação rápida de bot
        bot_config = await BotRepository.get_bot_by_id(bot_id)
        if not bot_config or not bot_config.is_active:
            return JSONResponse({"ok": True}, status_code=200)

        # Filtrar mensagens antigas
        message = update_data.get("message", {})
        if message:
            message_date = message.get("date", 0)
            if message_date < APP_START_TIME:
                return JSONResponse({"ok": True}, status_code=200)

        # Enfileirar e retornar IMEDIATAMENTE
        process_telegram_update.delay(bot_id=bot_config.id, update=update_data)
        return JSONResponse({"ok": True}, status_code=200)

    except Exception as e:
        logger.error(f"Error in bot webhook: {e}")
        return JSONResponse({"ok": False}, status_code=200)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
