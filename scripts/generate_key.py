#!/usr/bin/env python3
"""
Script para gerar chave de criptografia Fernet
"""
from cryptography.fernet import Fernet

if __name__ == "__main__":
    key = Fernet.generate_key()
    print(f"ENCRYPTION_KEY=base64:{key.decode()}")
    print("\nAdicione esta linha ao seu arquivo .env")
