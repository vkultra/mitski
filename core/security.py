"""
Módulo de segurança: criptografia, HMAC, assinaturas
"""

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict

from cryptography.fernet import Fernet

# Chave de criptografia (deve vir de variável de ambiente)
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", Fernet.generate_key())
if isinstance(ENCRYPTION_KEY, str):
    # Se vier como "base64:..." do .env
    if ENCRYPTION_KEY.startswith("base64:"):
        ENCRYPTION_KEY = ENCRYPTION_KEY[7:].encode()
    else:
        ENCRYPTION_KEY = ENCRYPTION_KEY.encode()

FERNET = Fernet(ENCRYPTION_KEY)
HMAC_SECRET = ENCRYPTION_KEY


def encrypt(data: str) -> bytes:
    """Criptografa string usando Fernet"""
    return FERNET.encrypt(data.encode())


def decrypt(encrypted_data: bytes) -> str:
    """Descriptografa dados usando Fernet"""
    return FERNET.decrypt(encrypted_data).decode()


def sign_payload(data: Dict[str, Any], ttl: int = 300) -> str:
    """
    Assina payload com HMAC e TTL

    Args:
        data: Dicionário com dados a assinar
        ttl: Time-to-live em segundos (default: 5 minutos)

    Returns:
        Token assinado em base64url
    """
    data_with_ts = {**data, "ts": int(time.time())}
    raw = json.dumps(data_with_ts, separators=(",", ":")).encode()
    mac = hmac.new(HMAC_SECRET, raw, hashlib.sha256).digest()[:8]
    return base64.urlsafe_b64encode(raw + mac).decode()


def verify_payload(token: str) -> Dict[str, Any]:
    """
    Verifica e decodifica token assinado

    Args:
        token: Token em base64url

    Returns:
        Dicionário com dados originais

    Raises:
        ValueError: Se MAC inválido ou token expirado
    """
    try:
        blob = base64.urlsafe_b64decode(token.encode())
        raw, mac = blob[:-8], blob[-8:]

        # Verifica MAC
        calc_mac = hmac.new(HMAC_SECRET, raw, hashlib.sha256).digest()[:8]
        if not hmac.compare_digest(mac, calc_mac):
            raise ValueError("Invalid MAC")

        # Decodifica e verifica TTL
        data = json.loads(raw.decode())
        if time.time() - data["ts"] > 300:  # 5 minutos
            raise ValueError("Token expired")

        return data
    except Exception as e:
        raise ValueError(f"Invalid token: {str(e)}")


def generate_secret(length: int = 32) -> str:
    """Gera string aleatória segura"""
    return os.urandom(length).hex()
