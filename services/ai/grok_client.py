"""
Cliente para API Grok (xAI) usando SDK oficial
"""

import asyncio
from typing import Any, Dict, List

from xai_sdk import AsyncClient
from xai_sdk.chat import Response, assistant, image, system, user

from core.redis_client import redis_client
from core.telemetry import logger

# Semaphore global compartilhado entre todas as instâncias
# Garante limite de concorrência global, não por instância
_GLOBAL_SEMAPHORE = None


class GrokAPIClient:
    """Cliente HTTP para Grok API (xAI) usando SDK oficial"""

    RATE_LIMIT_KEY = "grok_api_requests:{minute}"
    MAX_REQUESTS_PER_MINUTE = 480

    def __init__(self, api_key: str, max_concurrent: int = 100):
        """
        Inicializa cliente Grok API com SDK oficial

        Args:
            api_key: Token de autenticação xAI
            max_concurrent: Máximo de requisições simultâneas globalmente (default: 100)
                           Recomendado pela xAI para alto volume
        """
        self.api_key = api_key
        self.max_concurrent = max_concurrent

        # SDK oficial da xAI
        self.client = AsyncClient(
            api_key=api_key,
            timeout=3600,  # 1 hora para reasoning models (recomendação xAI)
        )

        # Semaphore global compartilhado
        self.semaphore = self._get_global_semaphore(max_concurrent)

    @classmethod
    def _get_global_semaphore(cls, max_concurrent: int) -> asyncio.Semaphore:
        """
        Retorna semaphore global compartilhado

        Garante que apenas 1 semaphore existe para TODAS as instâncias,
        seguindo exatamente a recomendação da xAI
        """
        global _GLOBAL_SEMAPHORE
        if _GLOBAL_SEMAPHORE is None:
            _GLOBAL_SEMAPHORE = asyncio.Semaphore(max_concurrent)
            logger.info(
                "Global semaphore created",
                extra={"max_concurrent": max_concurrent},
            )
        return _GLOBAL_SEMAPHORE

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
    ) -> Dict[str, Any]:
        """
        Envia requisição para Grok API usando SDK oficial

        Args:
            messages: Lista de mensagens [{"role": "user", "content": "..."}]
            model: "grok-4-fast-reasoning" ou "grok-4-fast-non-reasoning"
            temperature: 0.0 a 2.0 (controla aleatoriedade)
            max_tokens: Máximo de tokens na resposta

        Returns:
            {
                "content": "resposta",
                "reasoning_content": "pensamento" (opcional),
                "usage": {...},
                "finish_reason": "stop"
            }
        """
        # Rate limiting
        if not await self._check_rate_limit():
            await asyncio.sleep(1)
            if not await self._check_rate_limit():
                raise Exception("Rate limit exceeded: 480 req/min")

        def _build_user_preview(message: Dict[str, Any]) -> str:
            """Cria preview seguro sem despejar base64 gigante nos logs."""

            content = message.get("content")
            if not content:
                return ""

            if isinstance(content, list):
                preview_parts: List[str] = []
                for item in content:
                    item_type = item.get("type")
                    if item_type == "text":
                        preview_parts.append((item.get("text") or "")[:60])
                    elif item_type == "image_url":
                        url = item.get("image_url", {}).get("url", "")
                        if url.startswith("data:image"):
                            preview_parts.append("[image:data-url]")
                        elif url:
                            preview_parts.append(f"[image:{url[:30]}…]")
                        else:
                            preview_parts.append("[image]")
                combined = " ".join(filter(None, preview_parts))
                return combined[:200]

            text_content = str(content)
            if text_content.startswith("data:image"):
                return "[image:data-url]"
            return text_content[:200]

        # Log detalhado da requisição com preview seguro
        logger.info(
            "Grok API request started",
            extra={
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "num_messages": len(messages),
                "system_prompt": (
                    messages[0].get("content", "")[:200]
                    if messages and messages[0].get("role") == "system"
                    else None
                ),
                "last_user_message": next(
                    (
                        _build_user_preview(m)
                        for m in reversed(messages)
                        if m.get("role") == "user"
                    ),
                    None,
                ),
            },
        )

        try:
            # Controla concorrência com semaphore global (recomendação xAI)
            async with self.semaphore:
                # Cria chat usando SDK oficial
                chat = self.client.chat.create(
                    model=model, temperature=temperature, max_tokens=max_tokens
                )

                # Adiciona mensagens ao chat convertendo multimodal corretamente
                for msg in messages:
                    role = msg.get("role")

                    if role == "system":
                        chat.append(system(msg.get("content") or ""))
                        continue

                    if role == "assistant":
                        chat.append(assistant(msg.get("content") or ""))
                        continue

                    if role == "user":
                        content = msg.get("content")

                        if isinstance(content, list):
                            parts: List[Any] = []
                            for item in content:
                                item_type = item.get("type")
                                if item_type == "text":
                                    parts.append(item.get("text") or "")
                                elif item_type == "image_url":
                                    image_payload = item.get("image_url") or {}
                                    image_url = image_payload.get("url")
                                    if not image_url:
                                        continue

                                    detail = image_payload.get("detail")
                                    try:
                                        parts.append(
                                            image(image_url, detail=detail)
                                            if detail
                                            else image(image_url)
                                        )
                                    except TypeError:
                                        # detail pode ser inválido; tenta sem
                                        parts.append(image(image_url))

                            if parts:
                                chat.append(user(*parts))
                            else:
                                chat.append(user(""))
                        else:
                            chat.append(user(content or ""))
                        continue

                    logger.warning(
                        "Unsupported message role for Grok client",
                        extra={"role": role},
                    )

                # Executa request
                response: Response = await chat.sample()

                # Extrai dados (Response já tem os atributos diretamente)
                result = {
                    "content": getattr(response, "content", "") or "",
                    "reasoning_content": getattr(response, "reasoning_content", None),
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "cached_tokens": getattr(response.usage, "cached_tokens", 0),
                        "completion_tokens": response.usage.completion_tokens,
                        "reasoning_tokens": getattr(
                            response.usage, "reasoning_tokens", 0
                        ),
                        "total_tokens": response.usage.total_tokens,
                    },
                    "finish_reason": getattr(response, "finish_reason", "stop"),
                }

                logger.info(
                    "Grok API request successful (SDK)",
                    extra={
                        "model": model,
                        "usage": result["usage"],
                        "cached_tokens": result["usage"]["cached_tokens"],
                        "concurrent_requests": self.max_concurrent
                        - self.semaphore._value,
                        "response_preview": (
                            result["content"][:200] if result["content"] else None
                        ),
                        "has_reasoning": bool(result["reasoning_content"]),
                        "finish_reason": result["finish_reason"],
                    },
                )

                return result

        except Exception as e:
            logger.error(
                "Grok API client error (SDK)",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            raise

    async def extract_response(self, api_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrai resposta (já formatada pelo SDK)

        Args:
            api_response: Response já processado do SDK

        Returns:
            {
                "content": "resposta final" (SEMPRE retorna, SEM reasoning),
                "reasoning_content": "pensamento interno" (opcional, NÃO MOSTRAR),
                "usage": {...},
                "finish_reason": "stop"
            }
        """
        # SDK já retorna formatado
        return api_response

    async def close(self):
        """Fecha cliente (SDK gerencia automaticamente)"""
        # xai_sdk gerencia conexões automaticamente
        pass

    async def tokenize_text(self, text: str) -> int:
        """Calls tokenization endpoint to get prompt token count if available.

        Returns integer token count; raises on HTTP failures.
        """
        import httpx

        from core.config import settings as _settings

        base = getattr(_settings, "GROK_API_BASE_URL", "https://api.x.ai/v1").rstrip(
            "/"
        )
        api_key = getattr(_settings, "XAI_API_KEY", None)
        if not api_key:
            raise RuntimeError("XAI_API_KEY não configurada")
        url = f"{base}/tokenize-text"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json={"text": text or ""}, headers=headers)
            resp.raise_for_status()
            body = resp.json()
            tokens = body.get("tokens")
            if isinstance(tokens, list):
                return int(len(tokens))
            # Some implementations might return count
            count = body.get("token_count")
            return int(count) if isinstance(count, int) else 0


# Alias para compatibilidade
GrokClient = GrokAPIClient
