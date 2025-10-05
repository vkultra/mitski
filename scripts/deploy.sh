#!/bin/bash

# ==============================================================
# Script de Deploy Completo para VPS Ubuntu
# ==============================================================
# Este script automatiza todo o processo de deploy do bot Telegram
# Uso: ./scripts/deploy.sh [install|update|restart|backup|status]

set -e  # Para em caso de erro

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Diretório do projeto
PROJECT_DIR="/home/$(whoami)/mitski"
BACKUP_DIR="/home/$(whoami)/backups"

# Função de log
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERRO]${NC} $1"
    exit 1
}

warning() {
    echo -e "${YELLOW}[AVISO]${NC} $1"
}

# Função para instalar Docker e Docker Compose
install_docker() {
    log "Instalando Docker e Docker Compose..."

    # Atualizar sistema
    sudo apt-get update
    sudo apt-get upgrade -y

    # Instalar dependências
    sudo apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        git \
        vim \
        htop \
        ufw

    # Adicionar chave GPG do Docker
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

    # Adicionar repositório Docker
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
        $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Instalar Docker
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

    # Adicionar usuário ao grupo docker
    sudo usermod -aG docker $USER

    # Habilitar Docker no boot
    sudo systemctl enable docker
    sudo systemctl start docker

    log "Docker instalado com sucesso!"
}

# Função para configurar firewall
setup_firewall() {
    log "Configurando firewall UFW..."

    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    sudo ufw allow ssh
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    sudo ufw allow 5555/tcp  # Flower (opcional)

    # Habilitar UFW
    sudo ufw --force enable

    log "Firewall configurado!"
}

# Função para configurar swap
setup_swap() {
    log "Configurando swap..."

    # Verificar se swap já existe
    if [ -f /swapfile ]; then
        warning "Swap já existe. Pulando configuração."
        return
    fi

    # Criar arquivo swap de 4GB
    sudo fallocate -l 4G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile

    # Tornar permanente
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

    # Otimizar swappiness
    sudo sysctl vm.swappiness=10
    echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf

    log "Swap configurado!"
}

# Função para clonar/atualizar repositório
setup_repository() {
    log "Configurando repositório..."

    if [ ! -d "$PROJECT_DIR" ]; then
        log "Clonando repositório..."
        git clone https://github.com/SEU_USUARIO/SEU_REPO.git $PROJECT_DIR
    else
        log "Atualizando repositório..."
        cd $PROJECT_DIR
        git pull origin main
    fi

    cd $PROJECT_DIR
}

# Função para configurar ambiente
setup_environment() {
    log "Configurando variáveis de ambiente..."

    cd $PROJECT_DIR

    # Verificar se .env.production existe
    if [ ! -f .env.production ]; then
        error "Arquivo .env.production não encontrado! Configure-o primeiro."
    fi

    # Gerar chave de encriptação se necessário
    if grep -q "COLE_AQUI_A_CHAVE_GERADA" .env.production; then
        log "Gerando chave de encriptação..."
        ENCRYPTION_KEY=$(docker run --rm python:3.11-slim python -c "from cryptography.fernet import Fernet; import base64; print('base64:' + base64.b64encode(Fernet.generate_key()).decode())")
        sed -i "s|ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$ENCRYPTION_KEY|" .env.production
        log "Chave de encriptação gerada e salva!"
    fi

    # Criar diretório de backups
    mkdir -p $BACKUP_DIR
}

# Função para build e deploy
deploy_application() {
    log "Iniciando deploy da aplicação..."

    cd $PROJECT_DIR

    # Build das imagens
    log "Construindo imagens Docker..."
    docker compose -f docker-compose.production.yml build

    # Parar containers antigos
    log "Parando containers antigos..."
    docker compose -f docker-compose.production.yml down

    # Iniciar novos containers
    log "Iniciando containers..."
    docker compose -f docker-compose.production.yml up -d

    # Aguardar serviços subirem
    log "Aguardando serviços iniciarem..."
    sleep 10

    # Executar migrações
    log "Executando migrações do banco de dados..."
    docker compose -f docker-compose.production.yml exec -T webhook alembic upgrade head

    # Configurar webhook do Telegram
    log "Configurando webhook do Telegram..."
    docker compose -f docker-compose.production.yml exec -T webhook python scripts/setup_webhook.py

    log "Deploy concluído com sucesso!"
}

# Função para verificar status
check_status() {
    log "Status dos serviços:"
    docker compose -f docker-compose.production.yml ps

    log "\nUso de recursos:"
    docker stats --no-stream

    log "\nHealth check:"
    curl -s http://localhost/health || warning "Health check falhou"
}

# Função para backup
backup_database() {
    log "Realizando backup do banco de dados..."

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$BACKUP_DIR/backup_$TIMESTAMP.sql"

    docker compose -f docker-compose.production.yml exec -T postgres \
        pg_dump -U admin telegram_bots > $BACKUP_FILE

    # Comprimir backup
    gzip $BACKUP_FILE

    # Remover backups antigos (manter últimos 7 dias)
    find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +7 -delete

    log "Backup salvo em: ${BACKUP_FILE}.gz"
}

# Função para restart
restart_services() {
    log "Reiniciando serviços..."
    cd $PROJECT_DIR
    docker compose -f docker-compose.production.yml restart
    log "Serviços reiniciados!"
}

# Função para logs
show_logs() {
    cd $PROJECT_DIR
    docker compose -f docker-compose.production.yml logs -f --tail=100
}

# Função para instalação completa
full_install() {
    log "Iniciando instalação completa..."

    install_docker
    setup_firewall
    setup_swap
    setup_repository
    setup_environment
    deploy_application
    check_status

    log "Instalação completa finalizada!"
    log "Não esqueça de:"
    log "  1. Configurar seu domínio/IP no arquivo .env.production"
    log "  2. Adicionar seus tokens reais no .env.production"
    log "  3. Configurar SSL/TLS com certbot se usar domínio"
    log "  4. Fazer logout e login para aplicar permissões do Docker"
}

# Menu principal
case "$1" in
    install)
        full_install
        ;;
    update)
        setup_repository
        deploy_application
        ;;
    restart)
        restart_services
        ;;
    backup)
        backup_database
        ;;
    status)
        check_status
        ;;
    logs)
        show_logs
        ;;
    *)
        echo "Uso: $0 {install|update|restart|backup|status|logs}"
        echo ""
        echo "Comandos:"
        echo "  install  - Instalação completa (primeira vez)"
        echo "  update   - Atualizar código e fazer deploy"
        echo "  restart  - Reiniciar todos os serviços"
        echo "  backup   - Fazer backup do banco de dados"
        echo "  status   - Verificar status dos serviços"
        echo "  logs     - Mostrar logs em tempo real"
        exit 1
esac
