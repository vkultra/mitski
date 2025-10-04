.PHONY: help setup install test lint format clean up down logs smoke

# Cores para output
GREEN  := \033[0;32m
YELLOW := \033[1;33m
RED    := \033[0;31m
NC     := \033[0m # No Color

help: ## Mostra esta ajuda
	@echo "$(GREEN)Comandos disponíveis:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-15s$(NC) %s\n", $$1, $$2}'

setup: ## Configuração inicial do projeto
	@echo "$(GREEN)=' Configurando ambiente...$(NC)"
	pip install -r requirements-dev.txt
	pre-commit install
	@echo "$(GREEN) Ambiente configurado!$(NC)"

install: ## Instala dependências
	@echo "$(GREEN)=æ Instalando dependências...$(NC)"
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

test: ## Roda todos os testes
	@echo "$(GREEN)>ê Executando testes...$(NC)"
	docker-compose exec webhook pytest tests/ -v

smoke: ## Roda smoke tests
	@echo "$(GREEN)= Executando smoke tests...$(NC)"
	bash scripts/smoke_test.sh

coverage: ## Gera relatório de cobertura
	@echo "$(GREEN)=Ê Gerando relatório de cobertura...$(NC)"
	docker-compose exec webhook pytest --cov=. --cov-report=html --cov-report=term
	@echo "$(GREEN)=Â Abra htmlcov/index.html para ver o relatório$(NC)"

lint: ## Verifica qualidade do código
	@echo "$(GREEN)= Verificando código...$(NC)"
	black --check .
	isort --check-only .
	flake8 .
	mypy .

format: ## Formata o código automaticamente
	@echo "$(GREEN)( Formatando código...$(NC)"
	black .
	isort .
	@echo "$(GREEN) Código formatado!$(NC)"

pre-commit: ## Roda pre-commit em todos os arquivos
	@echo "$(GREEN)= Executando pre-commit hooks...$(NC)"
	pre-commit run --all-files

up: ## Inicia todos os serviços
	@echo "$(GREEN)=€ Iniciando serviços...$(NC)"
	docker-compose up -d
	@echo "$(GREEN) Serviços iniciados!$(NC)"

down: ## Para todos os serviços
	@echo "$(YELLOW)ø  Parando serviços...$(NC)"
	docker-compose down

restart: down up ## Reinicia todos os serviços

build: ## Reconstrói as imagens Docker
	@echo "$(GREEN)=( Reconstruindo imagens...$(NC)"
	docker-compose build --no-cache

rebuild: down build up ## Para, reconstrói e inicia

logs: ## Mostra logs em tempo real
	docker-compose logs -f

logs-webhook: ## Mostra logs do webhook
	docker-compose logs -f webhook

logs-worker: ## Mostra logs dos workers
	docker-compose logs -f worker

shell-webhook: ## Abre shell no container webhook
	docker-compose exec webhook bash

shell-worker: ## Abre shell no container worker
	docker-compose exec worker bash

shell-db: ## Abre psql no PostgreSQL
	docker-compose exec postgres psql -U admin -d telegram_bots

shell-redis: ## Abre redis-cli
	docker-compose exec redis redis-cli

clean: ## Remove arquivos temporários
	@echo "$(YELLOW)>ù Limpando arquivos temporários...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	@echo "$(GREEN) Limpeza concluída!$(NC)"

migrate: ## Roda migrações do banco
	@echo "$(GREEN)=Ä  Executando migrações...$(NC)"
	docker-compose exec webhook alembic upgrade head

migration: ## Cria nova migração (use: make migration msg="descrição")
	@echo "$(GREEN)=Ý Criando migração...$(NC)"
	docker-compose exec webhook alembic revision --autogenerate -m "$(msg)"

check-deps: ## Verifica dependências desatualizadas
	@echo "$(GREEN)=æ Verificando dependências...$(NC)"
	pip list --outdated

security: ## Verifica vulnerabilidades de segurança
	@echo "$(GREEN)= Verificando segurança...$(NC)"
	pip install safety
	safety check

update-deps: ## Atualiza requirements.txt
	@echo "$(GREEN)=æ Atualizando dependências...$(NC)"
	pip freeze > requirements.txt

watch: ## Watch mode para desenvolvimento
	@echo "$(GREEN)=@ Modo watch ativado...$(NC)"
	docker-compose logs -f webhook worker

status: ## Mostra status dos serviços
	@echo "$(GREEN)=Ê Status dos serviços:$(NC)"
	docker-compose ps

healthcheck: smoke ## Alias para smoke tests

all: clean format lint test ## Roda formatação, lint e testes
