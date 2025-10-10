# =� Guia de Setup - Telegram Multi-Bot Manager

## =� Pr�-requisitos

- Docker & Docker Compose
- Python 3.11+ (para desenvolvimento local)
- Git
- ngrok (para desenvolvimento local)

## � Setup R�pido

### 1. **Configurar Pre-commit Hooks** (IMPORTANTE!)

```bash
# Instalar pre-commit
pip install pre-commit

# Ativar os hooks
pre-commit install

# Testar (opcional)
pre-commit run --all-files
```

**O que isso faz?**
-  Formata c�digo automaticamente antes de cada commit
-  Verifica erros de sintaxe
-  Valida type hints
-  Detecta problemas de seguran�a
-  Remove espa�os em branco desnecess�rios

### 2. **Configurar Ambiente**

```bash
# Copiar .env de exemplo (se houver)
cp .env.example .env

# Editar .env com suas credenciais
nano .env
```

Configura��es necess�rias no `.env`:
```bash
MANAGER_BOT_TOKEN=seu_token_aqui
TELEGRAM_WEBHOOK_SECRET=seu_secret_aqui
WEBHOOK_BASE_URL=https://seu-ngrok-url.ngrok-free.dev
ENCRYPTION_KEY=base64:sua_key_aqui
ALLOWED_ADMIN_IDS=                 # opcional: deixe vazio para liberar todas as funções
```

### 3. **Iniciar Servi�os**

```bash
# Usar Makefile (recomendado)
make up

# Ou manualmente
docker-compose up -d
```

### 4. **Verificar se est� funcionando**

```bash
# Smoke tests
make smoke

# Ou manualmente
bash scripts/smoke_test.sh
```

## =� Comandos �teis (Makefile)

```bash
make help          # Ver todos os comandos
make up            # Iniciar servi�os
make down          # Parar servi�os
make restart       # Reiniciar servi�os
make logs          # Ver logs
make test          # Rodar testes
make smoke         # Smoke tests
make format        # Formatar c�digo
make lint          # Verificar c�digo
make clean         # Limpar arquivos tempor�rios
```

## = Workflow de Desenvolvimento

### **Antes de Codificar**

```bash
# 1. Atualizar branch
git pull origin main

# 2. Criar nova branch
git checkout -b feature/minha-feature

# 3. Iniciar servi�os
make up
```

### **Durante o Desenvolvimento**

```bash
# Ver logs em tempo real
make watch

# Formatar c�digo
make format

# Verificar qualidade
make lint
```

### **Antes de Commitar**

```bash
# 1. Formatar c�digo
make format

# 2. Rodar testes
make test

# 3. Smoke tests
make smoke

# 4. Commit (pre-commit hooks rodam automaticamente)
git add .
git commit -m "feat: adiciona nova funcionalidade"
```

**O que acontece no commit?**
1. Pre-commit hooks s�o executados automaticamente
2. C�digo � formatado com Black
3. Imports s�o organizados com isort
4. Erros s�o detectados com Flake8
5. Type hints s�o verificados com MyPy
6. Se algo falhar, o commit � bloqueado

## >� Rodando Testes

### **Testes Locais (sem Docker)**

```bash
# Instalar depend�ncias
pip install -r requirements-dev.txt

# Rodar testes
pytest

# Com cobertura
pytest --cov=. --cov-report=html
```

### **Testes no Docker**

```bash
# Smoke tests
make smoke

# Todos os testes
make test

# Com cobertura
make coverage
```

## = Debugging

### **Ver logs espec�ficos**

```bash
# Webhook
make logs-webhook

# Workers
make logs-worker

# Todos
make logs
```

### **Acessar containers**

```bash
# Shell no webhook
make shell-webhook

# Shell no worker
make shell-worker

# PostgreSQL
make shell-db

# Redis
make shell-redis
```

### **Verificar status**

```bash
# Status dos servi�os
make status

# Health check
curl http://localhost:8000/health
```

## = Seguran�a

### **Verificar vulnerabilidades**

```bash
# Instalar safety
pip install safety

# Verificar
make security
```

### **Boas pr�ticas**

- L NUNCA commite secrets no c�digo
-  Use vari�veis de ambiente
-  Adicione `.env` ao `.gitignore`
-  Gere ENCRYPTION_KEY forte
-  Mantenha depend�ncias atualizadas

## =� Deploy

### **Preparar para produ��o**

```bash
# 1. Rodar todos os testes
make all

# 2. Verificar seguran�a
make security

# 3. Build para produ��o
docker-compose -f docker-compose.prod.yml build

# 4. Deploy
docker-compose -f docker-compose.prod.yml up -d
```

## =� Monitoramento

### **Health checks**

```bash
# API
curl http://localhost:8000/health

# Redis
docker-compose exec redis redis-cli ping

# PostgreSQL
docker-compose exec postgres pg_isready
```

### **M�tricas**

- Logs estruturados em JSON
- Celery flower para monitorar workers
- Prometheus para m�tricas (futuro)

## <� Troubleshooting

### **Problema: Pre-commit n�o est� rodando**

```bash
# Reinstalar hooks
pre-commit uninstall
pre-commit install
```

### **Problema: Docker n�o inicia**

```bash
# Ver logs de erro
docker-compose logs

# Limpar e reiniciar
make down
make clean
make up
```

### **Problema: Testes falhando**

```bash
# Limpar cache
make clean

# Reconstruir containers
make rebuild

# Rodar testes
make test
```

### **Problema: Webhook retorna 422**

- Verifique se o webhook secret est� correto
- Confira logs: `make logs-webhook`
- Teste manualmente: `curl -X POST http://localhost:8000/health`

## =� Recursos

- [Documenta��o de Testes](TESTING.md)
- [Arquitetura](AGENTS.MD)
- [Pre-commit Hooks](.pre-commit-config.yaml)
- [Configura��o](.env)

## <� Pr�ximos Passos

1.  Configure pre-commit hooks
2.  Rode smoke tests
3.  Teste o bot no Telegram
4. =� Adicione seus primeiros testes
5. =� Configure CI/CD (GitHub Actions)
6. =� Configure monitoramento (Prometheus)

---

**D�vidas?** Consulte `make help` para ver todos os comandos dispon�veis!
