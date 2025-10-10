# Telegram Multi-Bot Manager

Sistema de gerenciamento de múltiplos bots Telegram com arquitetura event-driven, suportando **100+ bots simultâneos**, **5000+ usuários/bot/dia**, e **múltiplas APIs externas** sem bloqueio.

## 🏗️ Arquitetura

```
FastAPI (webhook receiver)
↓
Redis/RabbitMQ (message queue)
↓
Celery (workers paralelos)
↓
PostgreSQL (estado/dados) + Redis (cache/locks)
```

## 🚀 Quick Start

### 1. Configuração

```bash
# Copiar arquivo de ambiente
cp .env.example .env

# Editar .env com suas credenciais
nano .env
```

### 2. Iniciar com Docker

```bash
# Subir toda a stack
docker-compose up -d

# Ver logs
docker-compose logs -f webhook worker

# Acessar Flower (monitor Celery)
open http://localhost:5555
```

### 3. Migrations

```bash
# Criar migrations
alembic revision --autogenerate -m "Initial migration"

# Aplicar migrations
alembic upgrade head
```

## 📋 Funcionalidades

### Bot Gerenciador
- ✅ Registro dinâmico de bots secundários
- ✅ Validação de tokens via API Telegram
- ✅ Configuração automática de webhooks
- ✅ Gerenciamento de múltiplos bots por admin
- ✅ Ativação/desativação de bots

### Segurança
- 🔒 Tokens criptografados no banco (Fernet)
- 🔒 HMAC assinado em callback_data com TTL
- 🔒 Rate limiting distribuído (Redis)
- 🔒 Cooldown para prevenir duplo clique
- 🔒 Locks distribuídos para operações críticas
- 🔒 Logs redactados (sem secrets)
- 🔒 Validação de webhook secret

### Escalabilidade
- ⚡ Webhook (não polling) para latência <100ms
- ⚡ Workers paralelos com Celery
- ⚡ Connection pooling (PostgreSQL + Redis)
- ⚡ Circuit breaker para APIs externas
- ⚡ Retry com backoff exponencial
- ⚡ Auto-scaling de workers

## 🛠️ Desenvolvimento

### Instalar Dependências

```bash
# Criar ambiente virtual
python -m venv venv

# Ativar (Linux/Mac)
source venv/bin/activate

# Ativar (Windows)
venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Comandos Úteis

```bash
# Rodar testes
pytest --cov=. --cov-report=html

# Formatar código
black .

# Ordenar imports
isort .

# Linting
flake8

# Type checking
mypy .

# Load testing
locust -f loadtest.py --users 5000 --spawn-rate 100
```

## 📊 Monitoramento

### Métricas Prometheus
- `telegram_messages_total` - Total de mensagens recebidas
- `celery_task_duration_seconds` - Tempo de processamento
- `telegram_active_bots` - Número de bots ativos
- `celery_queue_size` - Tamanho da fila
- `external_api_errors_total` - Erros em APIs externas

### Logs Estruturados
Todos os logs são em JSON com:
- `timestamp` - Timestamp do evento
- `level` - Nível do log
- `service` - Nome do serviço
- `request_id` - ID de correlação
- `user_id`, `bot_id` - Contexto

### Alertas Recomendados
- ⚠️ Queue size > 1000
- ⚠️ Error rate > 5% por 5 min
- ⚠️ API latência > 3s
- ⚠️ Worker down
- ⚠️ Disco > 80%
- ⚠️ Memória > 85%

## 🔐 Segurança

### Checklist de Produção

**Infraestrutura:**
- [ ] Webhook com secret validando header
- [ ] HTTPS obrigatório
- [ ] Connection pools configurados
- [ ] Workers com auto-scaling
- [ ] Circuit breaker configurado
- [ ] Backups diários + restore testado

**Segurança:**
- [ ] Allowlist de admins ativa
- [ ] Rate limit + cooldown + locks
- [ ] callback_data assinado com HMAC
- [ ] Tokens criptografados no DB
- [ ] Auto-delete de mensagens sensíveis
- [ ] Logs redactados
- [ ] Rotação de secrets (90 dias)

**Confiabilidade:**
- [ ] Estados finitos + idempotência
- [ ] Retry com backoff + jitter
- [ ] Dead letter queue
- [ ] Health checks

## 📁 Estrutura do Projeto

```
telegram-multi-bot-manager/
├── main.py                    # FastAPI webhook receiver
├── bot_manager.py             # Bot gerenciador
├── workers/
│   ├── celery_app.py         # Configuração Celery
│   ├── tasks.py              # Tasks assíncronas
│   └── api_clients.py        # Clientes APIs externas
├── database/
│   ├── models.py             # SQLAlchemy models
│   └── repos.py              # Repositories
├── core/
│   ├── config.py             # Settings (Pydantic)
│   ├── security.py           # HMAC, encryption
│   ├── rate_limiter.py       # Rate limit distribuído
│   ├── redis_client.py       # Redis pool
│   └── telemetry.py          # Logs estruturados
├── handlers/
│   ├── manager_handlers.py   # Handlers bot gerenciador
│   └── bot_handlers.py       # Handlers bots secundários
├── requirements.txt
├── docker-compose.yml
└── .env
```

## 🚀 Deploy em Produção

### Kubernetes (exemplo)

```bash
# Deploy webhook
kubectl apply -f k8s/webhook-deployment.yaml

# Deploy workers com auto-scaling
kubectl apply -f k8s/worker-deployment.yaml
kubectl autoscale deployment worker --min=3 --max=10 --cpu-percent=70

# Status
kubectl get pods -l app=telegram-bot-manager
kubectl logs -f deployment/webhook
```

## 📚 Documentação Adicional

- [AGENTS.MD](AGENTS.MD) - Documentação completa da arquitetura
- [CLAUDE.md](CLAUDE.md) - Guia de desenvolvimento Python
- [docs/prompt_import_export.md](docs/prompt_import_export.md) - Fluxo de importação/exportação de prompts em .txt

## 📝 Licença

MIT License
# Teste de pre-commit hook
