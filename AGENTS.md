# AGENTS.md

## Project Overview

This is a Python project optimized for modern Python development. The project uses industry-standard tools and follows best practices for scalable application development.

## Development Commands

### Environment Management
- python -m venv venv - Create virtual environment
- source venv/bin/activate (Linux/Mac) or venv\Scripts\activate (Windows) - Activate virtual environment
- deactivate - Deactivate virtual environment
- pip install -r requirements.txt - Install dependencies
- pip install -r requirements-dev.txt - Install development dependencies

### Package Management
- pip install <package> - Install a package
- pip install -e . - Install project in development mode
- pip freeze > requirements.txt - Generate requirements file
- pip-tools compile requirements.in - Compile requirements with pip-tools

### Testing Commands
- pytest - Run all tests
- pytest -v - Run tests with verbose output
- pytest --cov - Run tests with coverage report
- pytest --cov-report=html - Generate HTML coverage report
- pytest -x - Stop on first failure
- pytest -k "test_name" - Run specific test by name
- python -m unittest - Run tests with unittest

### Code Quality Commands
- black . - Format code with Black
- black --check . - Check code formatting without changes
- isort . - Sort imports
- isort --check-only . - Check import sorting
- flake8 - Run linting with Flake8
- pylint src/ - Run linting with Pylint
- mypy src/ - Run type checking with MyPy

### Development Tools
- python -m pip install --upgrade pip - Upgrade pip
- python -c "import sys; print(sys.version)" - Check Python version
- python -m site - Show Python site information
- python -m pdb script.py - Debug with pdb

## Technology Stack

### Core Technologies
- *Python* - Primary programming language (3.8+)
- *pip* - Package management
- *venv* - Virtual environment management

### Common Frameworks
- *Django* - High-level web framework
- *Flask* - Micro web framework
- *FastAPI* - Modern API framework with automatic documentation
- *SQLAlchemy* - SQL toolkit and ORM
- *Pydantic* - Data validation using Python type hints

### Data Science & ML
- *NumPy* - Numerical computing
- *Pandas* - Data manipulation and analysis
- *Matplotlib/Seaborn* - Data visualization
- *Scikit-learn* - Machine learning library
- *TensorFlow/PyTorch* - Deep learning frameworks

### Testing Frameworks
- *pytest* - Testing framework
- *unittest* - Built-in testing framework
- *pytest-cov* - Coverage plugin for pytest
- *factory-boy* - Test fixtures
- *responses* - Mock HTTP requests

### Code Quality Tools
- *Black* - Code formatter
- *isort* - Import sorter
- *flake8* - Style guide enforcement
- *pylint* - Code analysis
- *mypy* - Static type checker
- *pre-commit* - Git hooks framework

## Project Structure Guidelines

### File Organization

```
src/
├── package_name/
│   ├── __init__.py
│   ├── main.py          # Application entry point
│   ├── models/          # Data models
│   ├── views/           # Web views (Django/Flask)
│   ├── api/             # API endpoints
│   ├── services/        # Business logic
│   ├── utils/           # Utility functions
│   └── config/          # Configuration files
tests/
├── __init__.py
├── conftest.py          # pytest configuration
├── test_models.py
├── test_views.py
└── test_utils.py
requirements/
├── base.txt             # Base requirements
├── dev.txt              # Development requirements
└── prod.txt             # Production requirements
```

### Naming Conventions
- *Files/Modules*: Use snake_case (user_profile.py)
- *Classes*: Use PascalCase (UserProfile)
- *Functions/Variables*: Use snake_case (get_user_data)
- *Constants*: Use UPPER_SNAKE_CASE (API_BASE_URL)
- *Private methods*: Prefix with underscore (_private_method)

## Python Guidelines

### Type Hints
- Use type hints for function parameters and return values
- Import types from typing module when needed
- Use Optional for nullable values
- Use Union for multiple possible types
- Document complex types with comments

### Code Style
- Follow PEP 8 style guide
- Use meaningful variable and function names
- Keep functions focused and single-purpose
- Use docstrings for modules, classes, and functions
- Limit line length to 88 characters (Black default)

### Best Practices
- Use list comprehensions for simple transformations
- Prefer pathlib over os.path for file operations
- Use context managers (with statements) for resource management
- Handle exceptions appropriately with try/except blocks
- Use logging module instead of print statements

## Testing Standards

### Test Structure
- Organize tests to mirror source code structure
- Use descriptive test names that explain the behavior
- Follow AAA pattern (Arrange, Act, Assert)
- Use fixtures for common test data
- Group related tests in classes

### Coverage Goals
- Aim for 90%+ test coverage
- Write unit tests for business logic
- Use integration tests for external dependencies
- Mock external services in tests
- Test error conditions and edge cases

### pytest Configuration
```ini
# pytest.ini or pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "--cov=src --cov-report=term-missing"
```

## Virtual Environment Setup

### Creation and Activation
```bash
# Create virtual environment
python -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Requirements Management
- Use requirements.txt for production dependencies
- Use requirements-dev.txt for development dependencies
- Consider using pip-tools for dependency resolution
- Pin versions for reproducible builds

## Django-Specific Guidelines

### Project Structure
```
project_name/
├── manage.py
├── project_name/
│   ├── __init__.py
│   ├── settings/
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── users/
│   ├── products/
│   └── orders/
└── requirements/
```

### Common Commands
- python manage.py runserver - Start development server
- python manage.py migrate - Apply database migrations
- python manage.py makemigrations - Create new migrations
- python manage.py createsuperuser - Create admin user
- python manage.py collectstatic - Collect static files
- python manage.py test - Run Django tests

## FastAPI-Specific Guidelines

### Project Structure
```
src/
├── main.py              # FastAPI application
├── api/
│   ├── __init__.py
│   ├── dependencies.py  # Dependency injection
│   └── v1/
│       ├── __init__.py
│       └── endpoints/
├── core/
│   ├── __init__.py
│   ├── config.py        # Settings
│   └── security.py      # Authentication
├── models/
├── schemas/             # Pydantic models
└── services/
```

### Common Commands
- uvicorn main:app --reload - Start development server
- uvicorn main:app --host 0.0.0.0 --port 8000 - Start production server

## Security Guidelines

### Dependencies
- Regularly update dependencies with pip list --outdated
- Use safety package to check for known vulnerabilities
- Pin dependency versions in requirements files
- Use virtual environments to isolate dependencies

### Code Security
- Validate input data with Pydantic or similar
- Use environment variables for sensitive configuration
- Implement proper authentication and authorization
- Sanitize data before database operations
- Use HTTPS for production deployments

---

## Telegram Multi-Bot Manager — Architecture & Security

> Sistema de gerenciamento de múltiplos bots Telegram com arquitetura event-driven, suportando **100+ bots simultâneos**, **5000+ usuários/bot/dia**, e **múltiplas APIs externas** sem bloqueio.

### Visão Geral da Arquitetura

**Cenário:**
- 1 **Bot Gerenciador** (coordena tudo)
- N **Bots Secundários** (cada admin cadastra os seus via bot gerenciador)
- **5000+ usuários/bot/dia** interagindo simultaneamente
- **Múltiplas APIs** externas sendo consumidas

**Stack Tecnológica:**
```
FastAPI (webhook receiver)
↓
Redis/RabbitMQ (message queue)
↓
Celery/Dramatiq (workers paralelos)
↓
PostgreSQL (estado/dados) + Redis (cache/locks)
```

### Core Principles
- **Webhook > Polling** (obrigatório para escala com múltiplos bots)
- **Event-driven** (processamento assíncrono via fila)
- **Menor privilégio** (tokens, DB, comandos administrativos)
- **Não confiar no cliente** (IDs, callbacks, mensagens)
- **Idempotência** nas operações repetíveis
- **Logs sem segredos** (redação/máscara)
- **Observabilidade** com correlação de eventos
- **Fail-safe**: timeouts curtos, retries com backoff + jitter, circuit breaker
- **Horizontal scaling** (adicionar workers conforme demanda)

### Required Environment
```dotenv
APP_ENV=prod|staging|dev

# Bot Gerenciador
MANAGER_BOT_TOKEN=...
TELEGRAM_WEBHOOK_SECRET=...        # valida X-Telegram-Bot-Api-Secret-Token
WEBHOOK_BASE_URL=https://seu-dominio.com

# Database & Queue
DB_URL=postgresql+psycopg://...
REDIS_URL=redis://...
CELERY_BROKER_URL=redis://...
CELERY_RESULT_BACKEND=redis://...

# Security
ENCRYPTION_KEY=base64:...          # Fernet/HMAC (32 bytes)
ALLOWED_ADMIN_IDS=                 # legado: deixe em branco para liberar todas as funções

# Monitoring
LOG_LEVEL=INFO
SENTRY_DSN=...                     # error tracking (opcional)

# Rate Limits (por bot+usuário)
RATE_LIMITS_JSON={"cmd:/start":{"limit":30,"window":60},"cb:action":{"limit":20,"window":30}}

# Connection Pools
REDIS_MAX_CONNECTIONS=100
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40

# Circuit Breaker (APIs externas)
CIRCUIT_BREAKER_FAIL_MAX=5
CIRCUIT_BREAKER_TIMEOUT=60
```

**Regras:**
- Rotacionar segredos a cada **90 dias**
- Ambientes **isolados** (dev/staging/prod) com bancos/Redis distintos
- Ao cadastrar bot, configurar webhook com `drop_pending_updates=true`
- **Webhook obrigatório** (polling não escala para múltiplos bots)

### Webhook Architecture (FastAPI)

**Por que Webhook:**
- Polling: ~300 requests/min para 5 bots (inviável)
- Webhook: Telegram envia eventos diretamente (latência <100ms)
- Escala para 100+ bots sem overhead

**Webhook Receiver (main.py):**
```python
from fastapi import FastAPI, Request, HTTPException
import os
from workers.tasks import process_telegram_update

app = FastAPI()
WEBHOOK_SECRET = os.environ["TELEGRAM_WEBHOOK_SECRET"]

@app.middleware("http")
async def validate_telegram_signature(request: Request, call_next):
    if request.url.path.startswith("/webhook/"):
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret != WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="forbidden")
    return await call_next(request)

@app.post("/webhook/{bot_token}")
async def webhook(bot_token: str, request: Request):
    # 1. Identifica bot secundário
    bot_config = await get_bot_by_token(bot_token)
    if not bot_config:
        raise HTTPException(status_code=404, detail="bot not found")

    # 2. Enfileira processamento (NÃO bloqueia)
    update_data = await request.json()
    process_telegram_update.delay(
        bot_id=bot_config.id,
        update=update_data
    )

    # 3. Responde imediatamente
    return {"ok": True}

# Webhook do bot gerenciador
@app.post("/webhook/manager")
async def manager_webhook(request: Request):
    update = await request.json()
    process_manager_update.delay(update)
    return {"ok": True}
```

**Registro Dinâmico de Bots:**
```python
async def register_bot(admin_id: int, bot_token: str):
    # 1. Valida token
    bot_info = await telegram_api.get_me(bot_token)

    # 2. Salva no DB
    bot = await db.bots.create({
        'admin_id': admin_id,
        'token': encrypt(bot_token),  # criptografa token
        'username': bot_info.username,
        'webhook_secret': generate_secret()
    })

    # 3. Configura webhook no Telegram
    webhook_url = f"{WEBHOOK_BASE_URL}/webhook/{bot.id}"
    await telegram_api.set_webhook(
        token=bot_token,
        url=webhook_url,
        secret_token=bot.webhook_secret,
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True
    )

    return bot
```

### Secrets Handling
- Ao receber um segredo via chat:
  - **Criptografar** (Fernet) antes de persistir.
  - **Apagar** a mensagem imediatamente.
  - Confirmar: `✅ Dado sensível salvo com segurança.`
- Nunca logar segredos crus; aplicar redator de logs.
- (Evolução) entrada via **WebApp** com campo oculto.

**Criptografia (exemplo)**
```python
from cryptography.fernet import Fernet
import os
FERNET = Fernet(os.environ["ENCRYPTION_KEY"].encode())
def enc(s: str) -> bytes: return FERNET.encrypt(s.encode())
def dec(b: bytes) -> str:  return FERNET.decrypt(b).decode()
```

### Worker Layer (Celery/Dramatiq)

**Processamento Paralelo:**
```python
# workers/celery_app.py
from celery import Celery
import os

celery_app = Celery(
    'telegram_workers',
    broker=os.environ['CELERY_BROKER_URL'],
    backend=os.environ['CELERY_RESULT_BACKEND']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_acks_late=True,           # confirma após processar
    worker_prefetch_multiplier=1,  # pega 1 tarefa por vez
    task_track_started=True
)

# workers/tasks.py
from .celery_app import celery_app
from pybreaker import CircuitBreaker

api_breaker = CircuitBreaker(fail_max=5, timeout_duration=60)

@celery_app.task(bind=True, max_retries=3)
def process_telegram_update(self, bot_id: int, update: dict):
    """Processa update de bot secundário"""
    bot = get_bot(bot_id)
    user_id = update.get('message', {}).get('from', {}).get('id')

    # Rate limit por bot+usuário
    if not check_rate_limit(bot_id, user_id):
        send_rate_limit_message.delay(bot.token, user_id)
        return

    # Roteamento de comandos
    text = update.get('message', {}).get('text', '')

    if text == '/start':
        send_welcome.delay(bot.token, user_id)
    elif text.startswith('/api'):
        call_external_api.delay(bot_id, user_id, text)

@celery_app.task(bind=True, max_retries=3)
def call_external_api(self, bot_id: int, user_id: int, query: str):
    """Chama API externa com circuit breaker e retry"""
    try:
        # Circuit breaker protege contra APIs instáveis
        @api_breaker
        def fetch_data():
            return requests.post(
                'https://api.externa.com/endpoint',
                json={'query': query},
                timeout=5
            )

        result = fetch_data()
        send_message.delay(bot_id, user_id, result.json())

    except Exception as exc:
        # Retry com backoff exponencial
        raise self.retry(
            exc=exc,
            countdown=2 ** self.request.retries,  # 2s, 4s, 8s
            max_retries=3
        )

@celery_app.task
def send_message(bot_id: int, user_id: int, text: str):
    """Envia mensagem pelo bot correto"""
    bot = get_bot(bot_id)
    telegram_api.send_message(
        token=decrypt(bot.token),
        chat_id=user_id,
        text=text
    )
```

**Escalabilidade:**
```bash
# Iniciar múltiplos workers (1 worker = 10 threads concorrentes)
celery -A workers.celery_app worker --concurrency=10 --hostname=worker1@%h
celery -A workers.celery_app worker --concurrency=10 --hostname=worker2@%h
celery -A workers.celery_app worker --concurrency=10 --hostname=worker3@%h

# Total: 30 threads processando em paralelo
# Capacidade: ~1000 mensagens/minuto
```

### Anti-Abuse (Rate Limit, Cooldown, Locks)

**Rate Limit Distribuído (por bot + usuário):**
```python
import time, json, redis, os

redis_pool = redis.ConnectionPool(
    host=os.environ.get('REDIS_HOST', 'localhost'),
    max_connections=int(os.environ.get('REDIS_MAX_CONNECTIONS', 100)),
    decode_responses=True
)
r = redis.Redis(connection_pool=redis_pool)

LIMITS = json.loads(os.environ.get("RATE_LIMITS_JSON", "{}"))

def check_rate_limit(bot_id: int, user_id: int,
                     action: str = "default",
                     limit: int = 30,
                     window: int = 60) -> bool:
    """Janela deslizante por bot+usuário+ação"""
    now = int(time.time())
    key = f"rl:{bot_id}:{user_id}:{action}:{now//window}"

    with r.pipeline() as p:
        p.incr(key, 1)
        p.expire(key, window + 5)
        val, _ = p.execute()

    return val <= limit

def with_cooldown(bot_id: int, user_id: int, action: str, seconds: int = 3):
    """Cooldown para prevenir duplo clique"""
    key = f"cd:{bot_id}:{user_id}:{action}"
    if r.exists(key):
        return False
    r.setex(key, seconds, "1")
    return True
```

**Redis Lock para Operações Críticas:**
```python
def with_lock(key: str, ttl: int = 5):
    """Lock distribuído para operações sensíveis"""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            lock_key = f"lock:{key}"
            if not r.setnx(lock_key, "1"):
                return {"error": "operation in progress"}
            r.expire(lock_key, ttl)
            try:
                return fn(*args, **kwargs)
            finally:
                r.delete(lock_key)
        return wrapper
    return decorator

# Uso
@with_lock("payment:{user_id}", ttl=10)
def process_payment(user_id: int, amount: float):
    # Apenas 1 processamento por vez
    ...
```

**Respostas ao Usuário:**
- Rate limit: `⏳ Muitos comandos em pouco tempo. Aguarde {X} segundos.`
- Cooldown: `⏸️ Processando sua solicitação anterior...`
- Lock ativo: `🔒 Operação em andamento. Aguarde.`

### Secure `callback_data`
- **Não** enviar payload rico no `callback_data`.
- Usar **token assinado (HMAC)** + **TTL** + **amarrado a `user_id`** (e `chat_id` se fizer sentido).
- Alternativa: `callback_data` contém **id curto** → payload está em Redis/DB.
- Rejeitar MAC inválido/expirado ou usuário divergente: `⚠️ Essa ação não é válida mais.`

**Assinatura compacta (exemplo)**
```python
import base64, hmac, hashlib, time, json, os
SECRET = os.environ["ENCRYPTION_KEY"].encode()

def sign_payload(d: dict, ttl=300) -> str:
    d = {**d, "ts": int(time.time())}
    raw = json.dumps(d, separators=(',',':')).encode()
    mac = hmac.new(SECRET, raw, hashlib.sha256).digest()[:8]
    return base64.urlsafe_b64encode(raw+mac).decode()

def verify_payload(tok: str):
    blob = base64.urlsafe_b64decode(tok.encode())
    raw, mac = blob[:-8], blob[-8:]
    calc = hmac.new(SECRET, raw, hashlib.sha256).digest()[:8]
    if not hmac.compare_digest(mac, calc): raise ValueError("bad mac")
    d = json.loads(raw.decode())
    if time.time() - d["ts"] > 300: raise ValueError("expired")
    return d
```

### Input Validation
- Modelos **Pydantic** com limites de tamanho e **regex whitelist**.
- Números com tipos estritos (`int`, `Decimal`) e faixas mín/máx.
- Sanitizar **Markdown/HTML** e proibir `javascript:` em URLs.
- Rejeitar payloads excessivos; evitar regex pesada.

### State & Idempotency
- Operações repetíveis usam `idempotency_key` (UUIDv4).
- Estados **finitos e atômicos** (ex.: `created → active → completed|failed|expired`).
- Nunca basear transição de estado apenas em dados do cliente.


### Database Policy (PostgreSQL recomendado)
- Usuário **sem SUPERUSER**; privilégios mínimos.
- **Migrations** (Alembic) obrigatórias.
- Constraints: UNIQUEs por contexto, FKs, CHECKs de faixas.
- Colunas sensíveis **criptografadas**.
- **Backups diários** + teste de restore **mensal**.
- Retenção de logs/eventos **≥ 180 dias**.
- Índices típicos: chaves de associação/lookup e trilha de eventos por `ts`.

### Observability
- Logs **estruturados (JSON)** com `request_id`, `user_id` e correlação.
- Redator de logs que mascara cadeias “tipo segredo”.
- Métricas mínimas: latência por ação, taxa de erro, rate-limit hits, retries, funil do domínio.
- Alertas: queda anômala, fila crescendo, erro ≥ 1% por 5 min.

### Admin Surface
- Comandos sensíveis disponíveis para todos os usuários do bot gerenciador (allowlist apenas para legados).
- Sessão de admin com **TTL** (ex.: 30 min) e confirmação de identidade.
- Desativar **web page preview** em respostas administrativas.

### Files & Media
- Limitar MIME/tamanho; rejeitar executáveis.
- Nomear arquivos aleatoriamente; normalizar paths (sem `..`).
- (Opcional) Antivírus (ClamAV) para uploads de terceiros.

### Resilience Recipes
- **Circuit breaker** para provedores externos (abrir após N falhas; meia-vida; fallback).
- **Retry** com backoff exponencial + jitter em I/O.
- Timeouts e cancelamento cooperativo em todas as chamadas externas.

### Markdown/HTML Sanitization
- Escapar `_ * [ ] ( ) ~ ` > # + - = | { } . !` ao interpolar dados do usuário.
- Habilitar apenas o subset necessário de formatação.

### Production Checklist

**Infraestrutura:**
- [ ] Webhook configurado com secret validando header `X-Telegram-Bot-Api-Secret-Token`
- [ ] HTTPS obrigatório (Telegram rejeita HTTP)
- [ ] Connection pools configurados (Redis, PostgreSQL)
- [ ] Workers Celery com auto-scaling (min 3, max 10)
- [ ] Circuit breaker configurado para APIs externas
- [ ] Backups PostgreSQL diários + restore testado mensalmente

**Segurança:**
- [ ] (Opcional) Allowlist de admins (`ALLOWED_ADMIN_IDS`) somente se precisar restringir acesso
- [ ] Rate limit + cooldown + locks implementados
- [ ] `callback_data` assinado com HMAC + TTL
- [ ] Tokens de bots criptografados no DB (Fernet)
- [ ] Auto-delete de mensagens com dados sensíveis
- [ ] Logs redactados (sem tokens/secrets)
- [ ] Rotação de secrets configurada (90 dias)

**Confiabilidade:**
- [ ] Estados finitos + idempotência (UUIDv4 em operações críticas)
- [ ] Retry com backoff exponencial + jitter
- [ ] Dead letter queue para tasks falhadas
- [ ] Health checks (webhook, workers, DB, Redis)

**Observabilidade:**
- [ ] Logs estruturados (JSON) com `request_id` e correlação
- [ ] Métricas exportadas (Prometheus/Grafana)
- [ ] Alertas configurados (queue > 1000, error rate > 5%, API > 3s)
- [ ] Tracing distribuído (opcional: Jaeger/Zipkin)

**Testes:**
- [ ] Unit tests (rate limit, HMAC, idempotência) > 80% coverage
- [ ] Integration tests (webhook → worker → DB)
- [ ] Load testing com Locust (5000 usuários simultâneos)
- [ ] Staging isolado validado antes de deploy

### Deployment Commands

**Desenvolvimento:**
```bash
# Iniciar stack completo
docker-compose up -d

# Ver logs
docker-compose logs -f webhook worker

# Acessar Flower (monitor Celery)
open http://localhost:5555

# Migrations
alembic revision --autogenerate -m "Add bots table"
alembic upgrade head

# Tests
pytest --cov=. --cov-report=html
```

**Produção (Kubernetes - exemplo):**
```bash
# Deploy webhook
kubectl apply -f k8s/webhook-deployment.yaml
kubectl apply -f k8s/webhook-service.yaml

# Deploy workers (auto-scaling)
kubectl apply -f k8s/worker-deployment.yaml
kubectl autoscale deployment worker --min=3 --max=10 --cpu-percent=70

# Verificar status
kubectl get pods -l app=telegram-bot-manager
kubectl logs -f deployment/webhook

# Metrics
kubectl port-forward svc/prometheus 9090:9090
```

### Reference Snippets (compactos)

**Redis lock curto**
```python
import redis, os
r = redis.from_url(os.environ["REDIS_URL"])

def with_lock(key: str, ttl: int = 5):
    def deco(fn):
        def wrapper(*a, **kw):
            if not r.setnx(key, "1"):
                return False
            r.expire(key, ttl)
            try:
                return fn(*a, **kw)
            finally:
                r.delete(key)
        return wrapper
    return deco
```

**Redator de logs**
```python
import logging, re
SECRET_RE = re.compile(r'([A-Za-z0-9_\-]{24,})')
class RedactSecrets(logging.Filter):
    def filter(self, record):
        if isinstance(record.msg, str):
            record.msg = SECRET_RE.sub("[REDACTED]", record.msg)
        return True
```

---

### Database & Connection Pooling

**PostgreSQL (SQLAlchemy):**
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

engine = create_engine(
    os.environ['DB_URL'],
    pool_size=20,              # conexões base
    max_overflow=40,           # conexões extras sob carga
    pool_pre_ping=True,        # verifica conexão antes de usar
    pool_recycle=3600,         # recicla conexão após 1h
    echo=False
)

SessionLocal = sessionmaker(bind=engine)

# Models
class Bot(Base):
    __tablename__ = 'bots'

    id = Column(Integer, primary_key=True)
    admin_id = Column(BigInteger, nullable=False, index=True)
    token = Column(LargeBinary, nullable=False)  # criptografado
    username = Column(String(64), unique=True)
    webhook_secret = Column(String(128))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index('idx_admin_active', 'admin_id', 'is_active'),
    )

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    bot_id = Column(Integer, ForeignKey('bots.id'), nullable=False)
    username = Column(String(64))
    first_interaction = Column(DateTime, server_default=func.now())
    last_interaction = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        Index('idx_bot_user', 'bot_id', 'telegram_id'),
    )
```

**Redis Connection Pool:**
```python
import redis
import os

redis_pool = redis.ConnectionPool(
    host=os.environ.get('REDIS_HOST', 'localhost'),
    port=int(os.environ.get('REDIS_PORT', 6379)),
    db=0,
    max_connections=100,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True
)

redis_client = redis.Redis(connection_pool=redis_pool)
```

### Project Structure (Multi-Bot Architecture)

```
telegram-multi-bot-manager/
├── main.py                     # FastAPI app (webhook receiver)
├── bot_manager.py              # Bot gerenciador (comandos admin)
│
├── workers/
│   ├── __init__.py
│   ├── celery_app.py          # Configuração Celery
│   ├── tasks.py               # Tasks assíncronas
│   └── api_clients.py         # Clientes APIs externas
│
├── database/
│   ├── __init__.py
│   ├── models.py              # SQLAlchemy models
│   ├── repos.py               # Repositories pattern
│   └── migrations/            # Alembic migrations
│
├── core/
│   ├── __init__.py
│   ├── config.py              # Settings (Pydantic)
│   ├── security.py            # HMAC, encryption
│   ├── rate_limiter.py        # Rate limit distribuído
│   ├── redis_client.py        # Redis connection pool
│   └── telemetry.py           # Logs estruturados
│
├── handlers/
│   ├── __init__.py
│   ├── manager_handlers.py    # Comandos bot gerenciador
│   └── bot_handlers.py        # Handlers bots secundários
│
├── requirements.txt
├── docker-compose.yml
└── .env
```

**docker-compose.yml (desenvolvimento):**
```yaml
version: '3.8'

services:
  webhook:
    build: .
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - postgres
      - redis

  worker:
    build: .
    command: celery -A workers.celery_app worker --concurrency=10 -l info
    env_file: .env
    depends_on:
      - redis
      - postgres
    deploy:
      replicas: 3  # 3 workers = 30 threads

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: telegram_bots
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: senha_segura
    ports:
      - "5432:5432"
    volumes:
      - pg_data:/var/lib/postgresql/data

  flower:  # Monitoring Celery
    build: .
    command: celery -A workers.celery_app flower
    ports:
      - "5555:5555"
    env_file: .env
    depends_on:
      - redis

volumes:
  pg_data:
```

### Monitoring & Observability

**Métricas Críticas (Prometheus/Grafana):**
```python
from prometheus_client import Counter, Histogram, Gauge

# Métricas
messages_received = Counter(
    'telegram_messages_total',
    'Total de mensagens recebidas',
    ['bot_id', 'message_type']
)

task_processing_time = Histogram(
    'celery_task_duration_seconds',
    'Tempo de processamento de tasks',
    ['task_name']
)

active_bots = Gauge(
    'telegram_active_bots',
    'Número de bots ativos'
)

queue_size = Gauge(
    'celery_queue_size',
    'Tamanho da fila de tarefas'
)

api_errors = Counter(
    'external_api_errors_total',
    'Erros em APIs externas',
    ['api_name', 'status_code']
)

# Uso
@celery_app.task
def process_update(bot_id, update):
    with task_processing_time.labels('process_update').time():
        messages_received.labels(bot_id=bot_id, message_type='text').inc()
        # ... processamento
```

**Logs Estruturados (JSON):**
```python
import logging
import json
from pythonjsonlogger import jsonlogger

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record['timestamp'] = record.created
        log_record['level'] = record.levelname
        log_record['service'] = 'telegram-bot-manager'

handler = logging.StreamHandler()
handler.setFormatter(CustomJsonFormatter())

logger = logging.getLogger()
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Uso
logger.info('Bot registered', extra={
    'bot_id': 123,
    'admin_id': 456,
    'username': '@meubot'
})
```

**Redator de Logs (previne vazamento de tokens):**
```python
import logging
import re

SECRET_PATTERNS = [
    re.compile(r'\d{10}:[A-Za-z0-9_-]{35}'),  # Telegram token
    re.compile(r'[A-Za-z0-9_\-]{32,}'),       # Chaves genéricas
]

class RedactSecrets(logging.Filter):
    def filter(self, record):
        if isinstance(record.msg, str):
            for pattern in SECRET_PATTERNS:
                record.msg = pattern.sub('[REDACTED]', record.msg)
        return True

logger.addFilter(RedactSecrets())
```

**Alertas Recomendados:**
- Queue size > 1000 (fila crescendo)
- Error rate > 5% por 5 minutos
- API externa latência > 3s
- Worker down (health check)
- Disco > 80%
- Memória > 85%

### Operations Runbook

**P0 - Indisponibilidade Externa (API fora):**
1. Circuit breaker abre automaticamente
2. Tasks ficam em retry com backoff
3. Alertar DevOps
4. Revisar timeouts e aumentar retry_max se necessário
5. Considerar fallback/cache se possível

**P1 - Replay de Callbacks/Spam:**
1. Checar idempotência (tokens HMAC com TTL)
2. Verificar rate limit por bot+user
3. Bloquear usuário temporariamente se necessário
4. Adicionar CAPTCHA no /start se ataque massivo

**P2 - Flood Attack:**
1. Apertar limites no `RATE_LIMITS_JSON`
2. Aumentar cooldown (5-10s)
3. Ativar modo manutenção no bot afetado
4. Verificar IP origem (se via webhook)
5. Considerar allowlist temporária

**P3 - Worker Overload:**
1. Checar métricas: `queue_size`, `task_processing_time`
2. Escalar workers horizontalmente (adicionar replicas)
3. Verificar DB connection pool (pode estar esgotado)
4. Revisar queries N+1 ou operações pesadas

### Testing Strategy

**Unit Tests:**
```python
def test_rate_limit():
    bot_id, user_id = 1, 12345
    # Deve permitir até 30 requests em 60s
    for i in range(30):
        assert check_rate_limit(bot_id, user_id) == True
    # 31º deve bloquear
    assert check_rate_limit(bot_id, user_id) == False

def test_hmac_signature():
    payload = {'user_id': 123, 'action': 'payment'}
    token = sign_payload(payload, ttl=300)
    # Deve validar
    assert verify_payload(token) == {**payload, 'ts': ...}
    # Token expirado deve falhar
    time.sleep(301)
    with pytest.raises(ValueError):
        verify_payload(token)
```

**Load Testing (Locust):**
```python
from locust import HttpUser, task, between

class TelegramWebhookUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def send_message(self):
        self.client.post(
            "/webhook/bot123",
            json={
                "update_id": 123456,
                "message": {
                    "from": {"id": random.randint(1, 10000)},
                    "text": "/start"
                }
            },
            headers={"X-Telegram-Bot-Api-Secret-Token": "SECRET"}
        )

# Teste: 5000 usuários simultâneos
# locust -f loadtest.py --users 5000 --spawn-rate 100
```

---

**FIM — Documento unificado.**
