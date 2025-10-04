.PHONY: help setup install test lint format clean up down logs smoke

# Cores para output
GREEN  := \033[0;32m
YELLOW := \033[1;33m
RED    := \033[0;31m
NC     := \033[0m # No Color

help: ## Mostra esta ajuda
	@echo "$(GREEN)Comandos dispon�veis:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-15s$(NC) %s\n", $$1, $$2}'

setup: ## Configura��o inicial do projeto
	@echo "$(GREEN)=' Configurando ambiente...$(NC)"
	pip install -r requirements-dev.txt
	pre-commit install
	@echo "$(GREEN) Ambiente configurado!$(NC)"

install: ## Instala depend�ncias
	@echo "$(GREEN)=� Instalando depend�ncias...$(NC)"
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

test: ## Roda todos os testes
	@echo "$(GREEN)>� Executando testes...$(NC)"
	docker-compose exec webhook pytest tests/ -v

smoke: ## Roda smoke tests
	@echo "$(GREEN)= Executando smoke tests...$(NC)"
	bash scripts/smoke_test.sh

coverage: ## Gera relat�rio de cobertura
	@echo "$(GREEN)=� Gerando relat�rio de cobertura...$(NC)"
	docker-compose exec webhook pytest --cov=. --cov-report=html --cov-report=term
	@echo "$(GREEN)=� Abra htmlcov/index.html para ver o relat�rio$(NC)"

lint: ## Verifica qualidade do c�digo
	@echo "$(GREEN)= Verificando c�digo...$(NC)"
	black --check .
	isort --check-only .
	flake8 .
	mypy .

format: ## Formata o c�digo automaticamente
	@echo "$(GREEN)( Formatando c�digo...$(NC)"
	black .
	isort .
	@echo "$(GREEN) C�digo formatado!$(NC)"

pre-commit: ## Roda pre-commit em todos os arquivos
	@echo "$(GREEN)= Executando pre-commit hooks...$(NC)"
	pre-commit run --all-files

up: ## Inicia todos os servi�os
	@echo "$(GREEN)=� Iniciando servi�os...$(NC)"
	docker-compose up -d
	@echo "$(GREEN) Servi�os iniciados!$(NC)"

down: ## Para todos os servi�os
	@echo "$(YELLOW)�  Parando servi�os...$(NC)"
	docker-compose down

restart: down up ## Reinicia todos os servi�os

build: ## Reconstr�i as imagens Docker
	@echo "$(GREEN)=( Reconstruindo imagens...$(NC)"
	docker-compose build --no-cache

rebuild: down build up ## Para, reconstr�i e inicia

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

clean: ## Remove arquivos tempor�rios
	@echo "$(YELLOW)>� Limpando arquivos tempor�rios...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	@echo "$(GREEN) Limpeza conclu�da!$(NC)"

migrate: ## Roda migra��es do banco
	@echo "$(GREEN)=�  Executando migra��es...$(NC)"
	docker-compose exec webhook alembic upgrade head

migration: ## Cria nova migra��o (use: make migration msg="descri��o")
	@echo "$(GREEN)=� Criando migra��o...$(NC)"
	docker-compose exec webhook alembic revision --autogenerate -m "$(msg)"

check-deps: ## Verifica depend�ncias desatualizadas
	@echo "$(GREEN)=� Verificando depend�ncias...$(NC)"
	pip list --outdated

security: ## Verifica vulnerabilidades de seguran�a
	@echo "$(GREEN)= Verificando seguran�a...$(NC)"
	pip install safety
	safety check

update-deps: ## Atualiza requirements.txt
	@echo "$(GREEN)=� Atualizando depend�ncias...$(NC)"
	pip freeze > requirements.txt

watch: ## Watch mode para desenvolvimento
	@echo "$(GREEN)=@ Modo watch ativado...$(NC)"
	docker-compose logs -f webhook worker

status: ## Mostra status dos servi�os
	@echo "$(GREEN)=� Status dos servi�os:$(NC)"
	docker-compose ps

healthcheck: smoke ## Alias para smoke tests

all: clean format lint test ## Roda formata��o, lint e testes
