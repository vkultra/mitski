#!/bin/bash

# ==============================================================
# Script de Health Check e Monitoramento
# ==============================================================
# Verifica a saúde de todos os serviços e pode reiniciar se necessário

set -e

# Configurações
WEBHOOK_URL="${HEALTH_CHECK_WEBHOOK_URL:-}"
MAX_RETRIES=3
RETRY_DELAY=10
PROJECT_DIR="/home/$(whoami)/mitski"
LOG_FILE="/var/log/health-check.log"

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Status tracking
TOTAL_CHECKS=0
FAILED_CHECKS=0
SERVICES_STATUS=""

# Funções de log
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a ${LOG_FILE}
}

error() {
    echo -e "${RED}[ERRO]${NC} $1" | tee -a ${LOG_FILE}
}

warning() {
    echo -e "${YELLOW}[AVISO]${NC} $1" | tee -a ${LOG_FILE}
}

# Função para enviar notificação
send_notification() {
    local message=$1
    local severity=$2

    if [ ! -z "${WEBHOOK_URL}" ]; then
        curl -X POST "${WEBHOOK_URL}" \
            -H "Content-Type: application/json" \
            -d "{\"text\":\"[${severity}] ${message}\"}" \
            -s > /dev/null 2>&1
    fi
}

# Verificar serviço Docker
check_docker() {
    log "Verificando Docker..."
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    if ! systemctl is-active --quiet docker; then
        error "Docker não está rodando!"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        SERVICES_STATUS="${SERVICES_STATUS}\n❌ Docker: OFFLINE"

        # Tentar reiniciar
        warning "Tentando reiniciar Docker..."
        sudo systemctl restart docker
        sleep 5

        if systemctl is-active --quiet docker; then
            log "Docker reiniciado com sucesso!"
            SERVICES_STATUS="${SERVICES_STATUS} (recuperado)"
        else
            error "Falha ao reiniciar Docker!"
            send_notification "Docker está offline e não pôde ser reiniciado!" "CRITICAL"
            return 1
        fi
    else
        log "Docker está OK ✓"
        SERVICES_STATUS="${SERVICES_STATUS}\n✅ Docker: OK"
    fi
}

# Verificar container específico
check_container() {
    local container_name=$1
    local service_name=$2

    log "Verificando ${service_name}..."
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    # Verificar se container existe e está rodando
    if docker ps --format "table {{.Names}}" | grep -q "${container_name}"; then
        # Container está rodando, verificar saúde
        local health=$(docker inspect --format='{{.State.Health.Status}}' "${container_name}" 2>/dev/null || echo "none")

        if [ "${health}" = "healthy" ] || [ "${health}" = "none" ]; then
            log "${service_name} está OK ✓"
            SERVICES_STATUS="${SERVICES_STATUS}\n✅ ${service_name}: OK"
        else
            warning "${service_name} está com problemas de saúde: ${health}"
            SERVICES_STATUS="${SERVICES_STATUS}\n⚠️ ${service_name}: ${health}"

            # Tentar reiniciar se unhealthy
            if [ "${health}" = "unhealthy" ]; then
                warning "Reiniciando ${service_name}..."
                docker restart "${container_name}"
                sleep 10
            fi
        fi
    else
        error "${service_name} não está rodando!"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        SERVICES_STATUS="${SERVICES_STATUS}\n❌ ${service_name}: OFFLINE"

        # Tentar iniciar container
        warning "Tentando iniciar ${service_name}..."
        cd ${PROJECT_DIR}
        docker compose -f docker-compose.production.yml up -d "${container_name}"
        sleep 10

        if docker ps --format "table {{.Names}}" | grep -q "${container_name}"; then
            log "${service_name} iniciado com sucesso!"
            SERVICES_STATUS="${SERVICES_STATUS} (recuperado)"
        else
            error "Falha ao iniciar ${service_name}!"
            send_notification "${service_name} está offline!" "HIGH"
        fi
    fi
}

# Verificar conectividade do banco de dados
check_database() {
    log "Verificando conexão com banco de dados..."
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    if docker exec mitski-postgres-1 pg_isready -U admin -d telegram_bots > /dev/null 2>&1; then
        log "Banco de dados está OK ✓"
        SERVICES_STATUS="${SERVICES_STATUS}\n✅ PostgreSQL: OK"
    else
        error "Banco de dados não está acessível!"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        SERVICES_STATUS="${SERVICES_STATUS}\n❌ PostgreSQL: INACESSÍVEL"
        send_notification "Banco de dados está inacessível!" "HIGH"
    fi
}

# Verificar Redis
check_redis() {
    log "Verificando Redis..."
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    if docker exec mitski-redis-1 redis-cli ping > /dev/null 2>&1; then
        log "Redis está OK ✓"
        SERVICES_STATUS="${SERVICES_STATUS}\n✅ Redis: OK"
    else
        error "Redis não está respondendo!"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        SERVICES_STATUS="${SERVICES_STATUS}\n❌ Redis: INACESSÍVEL"
        send_notification "Redis não está respondendo!" "HIGH"
    fi
}

# Verificar API endpoint
check_api() {
    log "Verificando API endpoint..."
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    local response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/health)

    if [ "${response}" = "200" ]; then
        log "API está OK ✓"
        SERVICES_STATUS="${SERVICES_STATUS}\n✅ API: OK"
    else
        error "API retornou código HTTP: ${response}"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        SERVICES_STATUS="${SERVICES_STATUS}\n❌ API: HTTP ${response}"
        send_notification "API está retornando erro HTTP ${response}!" "HIGH"
    fi
}

# Verificar uso de disco
check_disk_space() {
    log "Verificando espaço em disco..."
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    local disk_usage=$(df / | grep / | awk '{print $5}' | sed 's/%//g')

    if [ ${disk_usage} -gt 90 ]; then
        error "Disco está ${disk_usage}% cheio!"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        SERVICES_STATUS="${SERVICES_STATUS}\n❌ Disco: ${disk_usage}% usado"
        send_notification "Disco está ${disk_usage}% cheio!" "HIGH"
    elif [ ${disk_usage} -gt 80 ]; then
        warning "Disco está ${disk_usage}% cheio"
        SERVICES_STATUS="${SERVICES_STATUS}\n⚠️ Disco: ${disk_usage}% usado"
    else
        log "Espaço em disco OK: ${disk_usage}% usado ✓"
        SERVICES_STATUS="${SERVICES_STATUS}\n✅ Disco: ${disk_usage}% usado"
    fi
}

# Verificar memória
check_memory() {
    log "Verificando memória..."
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    local mem_total=$(free -m | grep Mem | awk '{print $2}')
    local mem_used=$(free -m | grep Mem | awk '{print $3}')
    local mem_percent=$((mem_used * 100 / mem_total))

    if [ ${mem_percent} -gt 90 ]; then
        error "Memória está ${mem_percent}% usada!"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        SERVICES_STATUS="${SERVICES_STATUS}\n❌ Memória: ${mem_percent}% usada"
        send_notification "Memória está ${mem_percent}% usada!" "HIGH"
    elif [ ${mem_percent} -gt 80 ]; then
        warning "Memória está ${mem_percent}% usada"
        SERVICES_STATUS="${SERVICES_STATUS}\n⚠️ Memória: ${mem_percent}% usada"
    else
        log "Memória OK: ${mem_percent}% usada ✓"
        SERVICES_STATUS="${SERVICES_STATUS}\n✅ Memória: ${mem_percent}% usada"
    fi
}

# Verificar Celery workers
check_celery() {
    log "Verificando Celery workers..."
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    local worker_count=$(docker exec mitski-worker-1 celery -A workers.celery_app inspect active 2>/dev/null | grep -c "empty" || echo "0")

    if [ "${worker_count}" != "0" ]; then
        log "Celery workers estão OK ✓"
        SERVICES_STATUS="${SERVICES_STATUS}\n✅ Celery: OK"
    else
        warning "Celery workers podem estar com problemas"
        SERVICES_STATUS="${SERVICES_STATUS}\n⚠️ Celery: Verificar"
    fi
}

# Verificar último backup
check_last_backup() {
    log "Verificando último backup..."
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    local backup_status_file="/home/$(whoami)/backups/last_backup_status.txt"

    if [ -f "${backup_status_file}" ]; then
        local last_backup=$(cat "${backup_status_file}")
        local backup_date=$(echo "${last_backup}" | cut -d'|' -f1)
        local backup_age=$(($(date +%s) - $(date -d "${backup_date}" +%s)))

        # Se backup tem mais de 25 horas (tolerância)
        if [ ${backup_age} -gt 90000 ]; then
            warning "Último backup tem mais de 25 horas!"
            SERVICES_STATUS="${SERVICES_STATUS}\n⚠️ Backup: Atrasado"
        else
            log "Backup está em dia ✓"
            SERVICES_STATUS="${SERVICES_STATUS}\n✅ Backup: OK"
        fi
    else
        warning "Status do backup não encontrado"
        SERVICES_STATUS="${SERVICES_STATUS}\n⚠️ Backup: Desconhecido"
    fi
}

# Função principal
main() {
    log "========================================="
    log "Iniciando Health Check do Sistema"
    log "========================================="

    # Executar todos os checks
    check_docker
    check_container "mitski-nginx-1" "Nginx"
    check_container "mitski-webhook-1" "FastAPI"
    check_container "mitski-worker-1" "Celery Worker"
    check_container "mitski-postgres-1" "PostgreSQL"
    check_container "mitski-redis-1" "Redis"
    check_database
    check_redis
    check_api
    check_celery
    check_disk_space
    check_memory
    check_last_backup

    # Resumo
    log "========================================="
    log "RESUMO DO HEALTH CHECK"
    log "Total de verificações: ${TOTAL_CHECKS}"
    log "Verificações com falha: ${FAILED_CHECKS}"

    echo -e "${SERVICES_STATUS}"

    if [ ${FAILED_CHECKS} -gt 0 ]; then
        error "Sistema com problemas detectados!"
        send_notification "Health check detectou ${FAILED_CHECKS} problemas!" "WARNING"
        exit 1
    else
        log "Sistema está saudável! ✓"
    fi

    log "========================================="
}

# Executar
main "$@"
