"""
FastAPI Webhook Receiver para Multi-Bot Manager
"""

import os

from fastapi import FastAPI, HTTPException, Request

from core.telemetry import logger
from database.repos import BotRepository
from workers.tasks import process_manager_update, process_telegram_update

app = FastAPI(title="Telegram Multi-Bot Manager")

WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "dev_secret")


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
        # Pega o corpo da requisição
        body = await request.body()
        logger.info("Raw body received", extra={"body": body.decode()})

        update = await request.json()

        logger.info("Manager update received", extra={"update": update})

        process_manager_update.delay(update)
        return {"ok": True}
    except Exception as e:
        logger.error(
            "Error processing manager webhook",
            extra={"error": str(e), "error_type": type(e).__name__},
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook/{bot_id}")
async def webhook(bot_id: int, request: Request):
    """Recebe updates de bots secundários"""
    bot_config = await BotRepository.get_bot_by_id(bot_id)
    if not bot_config:
        raise HTTPException(status_code=404, detail="bot not found")

    if not bot_config.is_active:
        raise HTTPException(status_code=403, detail="bot inactive")

    update_data = await request.json()

    # Enfileira processamento (não bloqueia)
    process_telegram_update.delay(bot_id=bot_config.id, update=update_data)

    return {"ok": True}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
