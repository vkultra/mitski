"""
Testes para módulo de segurança
"""

import time

import pytest

from core.security import (
    decrypt,
    encrypt,
    generate_secret,
    sign_payload,
    verify_payload,
)


def test_encrypt_decrypt():
    """Deve criptografar e descriptografar corretamente"""
    original = "token_secreto_123"
    encrypted = encrypt(original)
    decrypted = decrypt(encrypted)

    assert isinstance(encrypted, bytes)
    assert decrypted == original


def test_sign_payload_and_verify():
    """Deve assinar e verificar payload corretamente"""
    payload = {"user_id": 123, "action": "payment"}
    token = sign_payload(payload, ttl=300)

    verified = verify_payload(token)

    assert verified["user_id"] == 123
    assert verified["action"] == "payment"
    assert "ts" in verified


def test_verify_invalid_token():
    """Deve rejeitar token inválido"""
    with pytest.raises(ValueError):
        verify_payload("token_invalido")


def test_verify_expired_token():
    """Deve rejeitar token expirado"""
    payload = {"user_id": 123}
    token = sign_payload(payload, ttl=1)

    # Aguarda expiração
    time.sleep(2)

    with pytest.raises(ValueError, match="expired"):
        verify_payload(token)


def test_verify_tampered_token():
    """Deve rejeitar token adulterado"""
    payload = {"user_id": 123}
    token = sign_payload(payload)

    # Adultera o token
    tampered = token[:-1] + ("X" if token[-1] != "X" else "Y")

    with pytest.raises(ValueError):
        verify_payload(tampered)


def test_generate_secret():
    """Deve gerar secrets aleatórios únicos"""
    secret1 = generate_secret()
    secret2 = generate_secret()

    assert len(secret1) == 64  # 32 bytes = 64 hex chars
    assert len(secret2) == 64
    assert secret1 != secret2
