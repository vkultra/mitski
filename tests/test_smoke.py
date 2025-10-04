"""
Smoke tests - testes b�sicos para garantir que o sistema est� funcionando
"""
import pytest
from fastapi.testclient import TestClient
from main import app


class TestSmokeAPI:
    """Testes de smoke para verificar endpoints b�sicos"""

    def test_health_endpoint(self):
        """Testa se o endpoint de health check est� respondendo"""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_webhook_without_auth(self):
        """Testa webhook sem autentica��o (deve retornar 200 mesmo assim por enquanto)"""
        client = TestClient(app)
        response = client.post("/webhook/manager", json={
            "update_id": 1,
            "message": {
                "message_id": 1,
                "from": {"id": 123, "is_bot": False},
                "chat": {"id": 123, "type": "private"},
                "text": "/start"
            }
        })
        # Como a valida��o est� desabilitada, deve retornar 200
        assert response.status_code == 200


class TestSmokeImports:
    """Testes para verificar que todos os m�dulos podem ser importados"""

    def test_import_handlers(self):
        """Testa importa��o dos handlers"""
        from handlers import manager_handlers
        assert hasattr(manager_handlers, 'handle_start')
        assert hasattr(manager_handlers, 'handle_callback_add_bot')

    def test_import_workers(self):
        """Testa importa��o dos workers"""
        from workers import tasks
        assert hasattr(tasks, 'process_manager_update')
        assert hasattr(tasks, 'process_telegram_update')

    def test_import_database(self):
        """Testa importa��o dos modelos de banco"""
        from database import models
        assert hasattr(models, 'Bot')
        assert hasattr(models, 'User')

    def test_import_core(self):
        """Testa importa��o dos m�dulos core"""
        from core import config, security, telemetry
        assert hasattr(config, 'settings')
        assert hasattr(security, 'encrypt')
        assert hasattr(telemetry, 'logger')


class TestSmokeConfig:
    """Testes de configura��o"""

    def test_settings_load(self):
        """Testa se as configura��es carregam corretamente"""
        from core.config import settings
        assert settings.APP_ENV is not None
        assert settings.REDIS_URL is not None

    def test_allowed_admin_ids(self):
        """Testa parsing de IDs de admin"""
        from core.config import settings
        admin_ids = settings.allowed_admin_ids_list
        assert isinstance(admin_ids, list)
