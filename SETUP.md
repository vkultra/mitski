# =€ Guia de Setup - Telegram Multi-Bot Manager

## =Ë Pré-requisitos

- Docker & Docker Compose
- Python 3.11+ (para desenvolvimento local)
- Git
- ngrok (para desenvolvimento local)

## ¡ Setup Rápido

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
-  Formata código automaticamente antes de cada commit
-  Verifica erros de sintaxe
-  Valida type hints
-  Detecta problemas de segurança
-  Remove espaços em branco desnecessários

### 2. **Configurar Ambiente**

```bash
# Copiar .env de exemplo (se houver)
cp .env.example .env

# Editar .env com suas credenciais
nano .env
```

Configurações necessárias no `.env`:
```bash
MANAGER_BOT_TOKEN=seu_token_aqui
TELEGRAM_WEBHOOK_SECRET=seu_secret_aqui
WEBHOOK_BASE_URL=https://seu-ngrok-url.ngrok-free.dev
ENCRYPTION_KEY=base64:sua_key_aqui
ALLOWED_ADMIN_IDS=seu_telegram_id
```

### 3. **Iniciar Serviços**

```bash
# Usar Makefile (recomendado)
make up

# Ou manualmente
docker-compose up -d
```

### 4. **Verificar se está funcionando**

```bash
# Smoke tests
make smoke

# Ou manualmente
bash scripts/smoke_test.sh
```

## =à Comandos Úteis (Makefile)

```bash
make help          # Ver todos os comandos
make up            # Iniciar serviços
make down          # Parar serviços
make restart       # Reiniciar serviços
make logs          # Ver logs
make test          # Rodar testes
make smoke         # Smoke tests
make format        # Formatar código
make lint          # Verificar código
make clean         # Limpar arquivos temporários
```

## = Workflow de Desenvolvimento

### **Antes de Codificar**

```bash
# 1. Atualizar branch
git pull origin main

# 2. Criar nova branch
git checkout -b feature/minha-feature

# 3. Iniciar serviços
make up
```

### **Durante o Desenvolvimento**

```bash
# Ver logs em tempo real
make watch

# Formatar código
make format

# Verificar qualidade
make lint
```

### **Antes de Commitar**

```bash
# 1. Formatar código
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
1. Pre-commit hooks são executados automaticamente
2. Código é formatado com Black
3. Imports são organizados com isort
4. Erros são detectados com Flake8
5. Type hints são verificados com MyPy
6. Se algo falhar, o commit é bloqueado

## >ê Rodando Testes

### **Testes Locais (sem Docker)**

```bash
# Instalar dependências
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

### **Ver logs específicos**

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
# Status dos serviços
make status

# Health check
curl http://localhost:8000/health
```

## = Segurança

### **Verificar vulnerabilidades**

```bash
# Instalar safety
pip install safety

# Verificar
make security
```

### **Boas práticas**

- L NUNCA commite secrets no código
-  Use variáveis de ambiente
-  Adicione `.env` ao `.gitignore`
-  Gere ENCRYPTION_KEY forte
-  Mantenha dependências atualizadas

## =¢ Deploy

### **Preparar para produção**

```bash
# 1. Rodar todos os testes
make all

# 2. Verificar segurança
make security

# 3. Build para produção
docker-compose -f docker-compose.prod.yml build

# 4. Deploy
docker-compose -f docker-compose.prod.yml up -d
```

## =Ê Monitoramento

### **Health checks**

```bash
# API
curl http://localhost:8000/health

# Redis
docker-compose exec redis redis-cli ping

# PostgreSQL
docker-compose exec postgres pg_isready
```

### **Métricas**

- Logs estruturados em JSON
- Celery flower para monitorar workers
- Prometheus para métricas (futuro)

## <˜ Troubleshooting

### **Problema: Pre-commit não está rodando**

```bash
# Reinstalar hooks
pre-commit uninstall
pre-commit install
```

### **Problema: Docker não inicia**

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

- Verifique se o webhook secret está correto
- Confira logs: `make logs-webhook`
- Teste manualmente: `curl -X POST http://localhost:8000/health`

## =Ú Recursos

- [Documentação de Testes](TESTING.md)
- [Arquitetura](AGENTS.MD)
- [Pre-commit Hooks](.pre-commit-config.yaml)
- [Configuração](.env)

## <“ Próximos Passos

1.  Configure pre-commit hooks
2.  Rode smoke tests
3.  Teste o bot no Telegram
4. =Ý Adicione seus primeiros testes
5. =Ý Configure CI/CD (GitHub Actions)
6. =Ý Configure monitoramento (Prometheus)

---

**Dúvidas?** Consulte `make help` para ver todos os comandos disponíveis!
