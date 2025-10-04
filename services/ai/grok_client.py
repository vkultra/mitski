"""
Cliente para API Grok (xAI)
"""

import asyncio
from typing import Any, Dict, List

import httpx

from core.redis_client import redis_client
from core.telemetry import logger


class GrokAPIClient:
    """Cliente HTTP para Grok API (xAI)"""

    BASE_URL = "https://api.x.ai/v1"
    RATE_LIMIT_KEY = "grok_api_requests:{minute}"
    MAX_REQUESTS_PER_MINUTE = 480

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def _check_rate_limit(self) -> bool:
        """
        Verifica rate limit de 480 req/min (limite da API Grok)

        Returns:
            True se pode fazer request, False se atingiu limite
        """
        from datetime import datetime

        current_minute = datetime.utcnow().strftime("%Y%m%d%H%M")
        key = self.RATE_LIMIT_KEY.format(minute=current_minute)

        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, 60)  # Expira em 60 segundos

        if count > self.MAX_REQUESTS_PER_MINUTE:
            logger.warning("Grok API rate limit reached", extra={"count": count})
            return False

        return True

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: str = "grok-4-fast-reasoning",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Envia requisição para POST /v1/chat/completions

        Args:
            messages: Lista de mensagens [{"role": "user", "content": "..."}]
            model: "grok-4-fast-reasoning" ou "grok-4-fast-non-reasoning"
            temperature: 0.0 a 2.0 (controla aleatoriedade)
            max_tokens: Máximo de tokens na resposta
            stream: Se True, retorna streaming (SSE)

        Returns:
            {
                "id": "chatcmpl-abc123",
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "resposta",
                        "reasoning_content": "pensamento" (opcional)
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": 50,
                    "cached_tokens": 20,
                    "completion_tokens": 100,
                    "reasoning_tokens": 30
                }
            }
        """
        # Rate limiting
        if not await self._check_rate_limit():
            await asyncio.sleep(1)  # Aguarda 1s
            if not await self._check_rate_limit():
                raise Exception("Rate limit exceeded: 480 req/min")

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        try:
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()

            data = response.json()

            logger.info(
                "Grok API request successful",
                extra={
                    "model": model,
                    "usage": data.get("usage", {}),
                    "cached_tokens": data.get("usage", {}).get("cached_tokens", 0),
                },
            )

            return data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.error("Grok API rate limit (429)")
                raise Exception("Rate limit exceeded by API")

            logger.error(
                "Grok API HTTP error",
                extra={"status": e.response.status_code, "body": e.response.text},
            )
            raise

        except Exception as e:
            logger.error("Grok API client error", extra={"error": str(e)})
            raise

    async def extract_response(self, api_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrai resposta da API Grok

        Args:
            api_response: Response completo da API

        Returns:
            {
                "content": "resposta final" (SEMPRE retorna, SEM reasoning),
                "reasoning_content": "pensamento interno" (opcional, NÃO MOSTRAR),
                "usage": {...},
                "finish_reason": "stop"
            }
        """
        if not api_response.get("choices"):
            raise ValueError("No choices in response")

        choice = api_response["choices"][0]
        message = choice.get("message", {})

        return {
            "content": message.get("content", ""),
            "reasoning_content": message.get("reasoning_content"),  # Pode ser None
            "usage": api_response.get("usage", {}),
            "finish_reason": choice.get("finish_reason"),
        }

    async def close(self):
        """Fecha cliente HTTP"""
        await self.client.aclose()
