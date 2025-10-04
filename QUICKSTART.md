# 🚀 Quick Start Guide

## Pré-requisitos

- Python 3.11+
- Docker e Docker Compose (para desenvolvimento)
- PostgreSQL 15+ (se não usar Docker)
- Redis 7+ (se não usar Docker)

## 1. Configuração Inicial

### Clone e Setup

```bash
# Navegar para o diretório
cd /Users/mateusalves/mitski

# Criar ambiente virtual
python -m venv venv

# Ativar ambiente virtual (Mac/Linux)
source venv/bin/activate

# Ativar ambiente virtual (Windows)
# venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Gerar Chave de Criptografia

```bash
python scripts/generate_key.py
```

Copie a saída e adicione ao arquivo `.env`

### Configurar Variáveis de Ambiente

```bash
# Copiar exemplo
cp .env.example .env

# Editar com suas credenciais
nano .env
```

**Configurações obrigatórias:**
- `MANAGER_BOT_TOKEN` - Token do bot gerenciador (obter do @BotFather)
- `TELEGRAM_WEBHOOK_SECRET` - Secret aleatório para validação
- `ENCRYPTION_KEY` - Chave gerada pelo script acima
- `ALLOWED_ADMIN_IDS` - Seus IDs do Telegram (separados por vírgula)

## 2. Iniciar com Docker (Recomendado)

```bash
# Iniciar toda a stack
docker-compose up -d

# Ver logs em tempo real
docker-compose logs -f webhook worker

# Status dos containers
docker-compose ps
```

### Criar Tabelas do Banco

```bash
# Criar migration inicial
docker-compose exec webhook alembic revision --autogenerate -m "Initial migration"

# Aplicar migrations
docker-compose exec webhook alembic upgrade head
```

### Acessar Serviços

- **API/Webhook**: http://localhost:8000
- **Flower (monitor Celery)**: http://localhost:5555
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

## 3. Iniciar Manualmente (Sem Docker)

### Iniciar PostgreSQL e Redis

```bash
# PostgreSQL (Mac)
brew services start postgresql@15

# Redis (Mac)
brew services start redis
```

### Criar Banco de Dados

```bash
createdb telegram_bots
```

### Aplicar Migrations

```bash
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

### Iniciar Serviços

```bash
# Terminal 1: Webhook (FastAPI)
uvicorn main:app --reload --port 8000

# Terminal 2: Worker Celery
celery -A workers.celery_app worker --concurrency=10 -l info

# Terminal 3: Flower (opcional - monitoring)
celery -A workers.celery_app flower
```

## 4. Configurar Webhook do Bot Gerenciador

### Opção A: Desenvolvimento Local (ngrok)

```bash
# Instalar ngrok
brew install ngrok

# Criar túnel
ngrok http 8000

# Copiar URL HTTPS gerada (ex: https://abc123.ngrok.io)
# Atualizar WEBHOOK_BASE_URL no .env
```

### Opção B: Produção

```bash
# Usar domínio real com HTTPS
WEBHOOK_BASE_URL=https://seu-dominio.com
```

### Registrar Webhook

```python
# Executar script (criar em scripts/setup_webhook.py)
import httpx
import os

async def setup_webhook():
    token = os.environ['MANAGER_BOT_TOKEN']
    webhook_url = f"{os.environ['WEBHOOK_BASE_URL']}/webhook/manager"
    secret = os.environ['TELEGRAM_WEBHOOK_SECRET']

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/setWebhook",
            json={
                "url": webhook_url,
                "secret_token": secret,
                "allowed_updates": ["message", "callback_query"],
                "drop_pending_updates": True
            }
        )
        print(response.json())

if __name__ == "__main__":
    import asyncio
    asyncio.run(setup_webhook())
```

```bash
python scripts/setup_webhook.py
```

## 5. Usar o Bot Gerenciador

### Comandos Disponíveis

1. **Iniciar conversa**
   ```
   /start
   ```

2. **Registrar novo bot**
   ```
   /register SEU_BOT_TOKEN
   ```

3. **Listar bots**
   ```
   /list
   ```

4. **Desativar bot**
   ```
   /deactivate BOT_ID
   ```

## 6. Testes

```bash
# Rodar todos os testes
pytest

# Com cobertura
pytest --cov=. --cov-report=html

# Abrir relatório de cobertura
open htmlcov/index.html
```

## 7. Qualidade de Código

```bash
# Formatar código
black .

# Ordenar imports
isort .

# Linting
flake8

# Type checking
mypy .
```

## 8. Monitoramento

### Logs

```bash
# Docker
docker-compose logs -f webhook
docker-compose logs -f worker

# Manual
# Logs vão para stdout (console)
```

### Métricas (Flower)

1. Acessar http://localhost:5555
2. Ver tarefas em execução
3. Monitorar workers
4. Ver histórico de tarefas

### Health Check

```bash
curl http://localhost:8000/health
```

## 9. Troubleshooting

### Erro: "Bot not found"
- Verificar se migrations foram aplicadas
- Verificar conexão com PostgreSQL
- Verificar se bot foi registrado corretamente

### Erro: "Rate limit exceeded"
- Ajustar limites em `RATE_LIMITS_JSON`
- Verificar se Redis está funcionando
- Limpar cache: `redis-cli FLUSHDB`

### Webhook não recebe mensagens
- Verificar URL no Telegram: `https://api.telegram.org/bot<TOKEN>/getWebhookInfo`
- Verificar secret token
- Verificar logs do FastAPI
- Verificar se HTTPS está ativo (obrigatório)

### Workers não processam tarefas
- Verificar se Celery está rodando
- Verificar conexão com Redis
- Ver logs do worker
- Verificar Flower para erros

## 10. Deploy em Produção

### Checklist

- [ ] Variáveis de ambiente configuradas
- [ ] HTTPS configurado (obrigatório)
- [ ] Migrations aplicadas
- [ ] Backups configurados
- [ ] Monitoring configurado
- [ ] Rate limits ajustados
- [ ] Secrets rotacionados
- [ ] Testes passando

### Comandos de Deploy

```bash
# Build da imagem
docker build -t telegram-bot-manager .

# Push para registry
docker tag telegram-bot-manager registry.com/telegram-bot-manager
docker push registry.com/telegram-bot-manager

# Deploy (exemplo Kubernetes)
kubectl apply -f k8s/
kubectl rollout status deployment/webhook
```

## 📚 Documentação Adicional

- [README.md](README.md) - Documentação completa
- [AGENTS.MD](AGENTS.MD) - Arquitetura detalhada
- [CLAUDE.md](CLAUDE.md) - Guidelines Python

## 🆘 Suporte

Para problemas ou dúvidas:
1. Verificar logs
2. Consultar documentação
3. Criar issue no repositório
