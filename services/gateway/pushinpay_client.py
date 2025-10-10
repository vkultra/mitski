"""
Cliente para API do PushinPay
"""

import time
from typing import Any, Dict, Optional

import httpx

from core.redis_client import redis_client
from core.telemetry import logger


class PushinPayClient:
    """Cliente para API do PushinPay"""

    BASE_URL = "https://api.pushinpay.com.br"

    @staticmethod
    async def create_pix(
        token: str, value_cents: int, webhook_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cria uma cobrança PIX

        Args:
            token: Token de autenticação PushinPay
            value_cents: Valor em centavos (mínimo 50)
            webhook_url: URL opcional para receber notificações

        Returns:
            Dict com dados da transação (id, qr_code, qr_code_base64, status, ...)

        Raises:
            ValueError: Se valor < 50 centavos
            httpx.HTTPError: Se erro na requisição
        """
        if value_cents < 50:
            raise ValueError("Valor mínimo é 50 centavos")

        payload = {"value": value_cents}

        if webhook_url:
            payload["webhook_url"] = webhook_url

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{PushinPayClient.BASE_URL}/api/pix/cashIn",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                result = response.json()

                logger.info(
                    "PIX created successfully",
                    extra={
                        "transaction_id": result.get("id"),
                        "value_cents": value_cents,
                    },
                )

                return result

        except httpx.HTTPError as e:
            logger.error(
                "Error creating PIX",
                extra={"error": str(e), "value_cents": value_cents},
            )
            raise

    @staticmethod
    def create_pix_sync(
        token: str, value_cents: int, webhook_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Versão síncrona para criar uma cobrança PIX (para uso em handlers sync/async).
        """
        if value_cents < 50:
            raise ValueError("Valor mínimo é 50 centavos")

        payload: Dict[str, Any] = {"value": int(value_cents)}
        if webhook_url:
            payload["webhook_url"] = webhook_url

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{PushinPayClient.BASE_URL}/api/pix/cashIn",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                result = response.json()
                logger.info(
                    "PIX created successfully (sync)",
                    extra={
                        "transaction_id": result.get("id"),
                        "value_cents": value_cents,
                    },
                )
                return result
        except httpx.HTTPError as e:
            logger.error(
                "Error creating PIX (sync)",
                extra={"error": str(e), "value_cents": value_cents},
            )
            raise

    @staticmethod
    async def check_payment_status(token: str, transaction_id: str) -> Dict[str, Any]:
        """
        Verifica status de um pagamento PIX

        Args:
            token: Token de autenticação
            transaction_id: ID da transação no PushinPay

        Returns:
            Dict com status da transação

        Note:
            Rate limit: 1 requisição por minuto
            Deve ser usado com Redis lock
        """
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{PushinPayClient.BASE_URL}/api/transactions/{transaction_id}",
                    headers=headers,
                )
                response.raise_for_status()
                result = response.json()

                logger.info(
                    "Payment status checked",
                    extra={
                        "transaction_id": transaction_id,
                        "status": result.get("status"),
                    },
                )

                return result

        except httpx.HTTPError as e:
            logger.error(
                "Error checking payment status",
                extra={"error": str(e), "transaction_id": transaction_id},
            )
            raise

    @staticmethod
    def check_payment_status_sync(token: str, transaction_id: str) -> Dict[str, Any]:
        """
        Versão síncrona para workers Celery

        Args:
            token: Token de autenticação
            transaction_id: ID da transação

        Returns:
            Dict com status da transação
        """
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=30.0) as client:
                    response = client.get(
                        f"{PushinPayClient.BASE_URL}/api/transactions/{transaction_id}",
                        headers=headers,
                    )
                    response.raise_for_status()
                    result = response.json()

                    logger.info(
                        "Payment status checked (sync)",
                        extra={
                            "transaction_id": transaction_id,
                            "status": result.get("status"),
                        },
                    )

                    return result

            except (httpx.ConnectError, httpx.ReadTimeout) as e:
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)  # Exponential backoff
                    continue
                logger.error(
                    "Error checking payment status (sync)",
                    extra={"error": str(e), "transaction_id": transaction_id},
                )
                raise

    @staticmethod
    async def validate_token(token: str) -> bool:
        """
        Valida token criando uma transação de teste

        Args:
            token: Token a ser validado

        Returns:
            True se token é válido
        """
        try:
            # Cria PIX de 50 centavos para validar
            result = await PushinPayClient.create_pix(token, 50)
            return "id" in result and "qr_code" in result

        except httpx.HTTPError:
            return False

    @staticmethod
    def acquire_rate_limit_lock(admin_id: int, ttl_seconds: int = 60) -> bool:
        """
        Adquire lock de rate limit para API PushinPay

        Args:
            admin_id: ID do admin (para lock por usuário)
            ttl_seconds: Tempo de vida do lock (padrão 60s = 1 minuto)

        Returns:
            True se conseguiu lock, False se já existe
        """
        lock_key = f"pushinpay:ratelimit:{admin_id}"
        return redis_client.set(lock_key, "1", nx=True, ex=ttl_seconds) is not None

    @staticmethod
    def release_rate_limit_lock(admin_id: int):
        """
        Libera lock de rate limit manualmente

        Args:
            admin_id: ID do admin
        """
        lock_key = f"pushinpay:ratelimit:{admin_id}"
        redis_client.delete(lock_key)
