#!/bin/bash

# ==============================================================
# Script de Backup Automático do PostgreSQL
# ==============================================================
# Este script faz backup do banco de dados e pode enviar para S3/Google Drive
# Executa dentro do container de backup

set -e

# Configurações
BACKUP_DIR="/backups"
DB_HOST="postgres"
DB_PORT="5432"
DB_NAME="${POSTGRES_DB:-telegram_bots}"
DB_USER="${POSTGRES_USER:-admin}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILENAME="backup_${DB_NAME}_${TIMESTAMP}.sql"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILENAME}"
MAX_BACKUPS=7  # Manter últimos 7 backups

# Cores para output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Funções de log
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

# Criar diretório de backup se não existir
mkdir -p ${BACKUP_DIR}

log "Iniciando backup do banco de dados ${DB_NAME}..."

# Aguardar banco estar disponível
until PGPASSWORD="${POSTGRES_PASSWORD}" pg_isready -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER}; do
    warning "Aguardando banco de dados ficar disponível..."
    sleep 2
done

# Executar backup
log "Criando backup em ${BACKUP_PATH}..."

PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
    -h ${DB_HOST} \
    -p ${DB_PORT} \
    -U ${DB_USER} \
    -d ${DB_NAME} \
    --verbose \
    --no-owner \
    --no-acl \
    --format=custom \
    --compress=9 \
    --file="${BACKUP_PATH}" 2>&1

if [ $? -eq 0 ]; then
    log "Backup criado com sucesso!"

    # Comprimir backup adicional
    log "Comprimindo backup..."
    gzip -c "${BACKUP_PATH}" > "${BACKUP_PATH}.gz"

    # Calcular tamanho do backup
    BACKUP_SIZE=$(ls -lh "${BACKUP_PATH}.gz" | awk '{print $5}')
    log "Tamanho do backup comprimido: ${BACKUP_SIZE}"

    # Verificar integridade do backup
    log "Verificando integridade do backup..."
    PGPASSWORD="${POSTGRES_PASSWORD}" pg_restore \
        --list \
        "${BACKUP_PATH}" > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        log "Backup verificado com sucesso!"
    else
        error "Backup corrompido! Verifique o processo."
    fi
else
    error "Falha ao criar backup!"
fi

# Limpeza de backups antigos
log "Limpando backups antigos (mantendo últimos ${MAX_BACKUPS})..."

# Listar e contar backups
BACKUP_COUNT=$(ls -1 ${BACKUP_DIR}/backup_${DB_NAME}_*.sql 2>/dev/null | wc -l)

if [ ${BACKUP_COUNT} -gt ${MAX_BACKUPS} ]; then
    # Calcular quantos remover
    REMOVE_COUNT=$((BACKUP_COUNT - MAX_BACKUPS))

    # Remover os mais antigos
    ls -1t ${BACKUP_DIR}/backup_${DB_NAME}_*.sql* | tail -n ${REMOVE_COUNT} | while read OLD_BACKUP; do
        log "Removendo backup antigo: $(basename ${OLD_BACKUP})"
        rm -f "${OLD_BACKUP}"
    done
fi

# Upload para cloud storage (opcional - descomente e configure conforme necessário)

# Para AWS S3 (requer AWS CLI configurado)
# if [ ! -z "${AWS_S3_BUCKET}" ]; then
#     log "Enviando backup para S3..."
#     aws s3 cp "${BACKUP_PATH}.gz" "s3://${AWS_S3_BUCKET}/backups/" \
#         --storage-class STANDARD_IA
#     if [ $? -eq 0 ]; then
#         log "Backup enviado para S3 com sucesso!"
#     else
#         warning "Falha ao enviar backup para S3"
#     fi
# fi

# Para Google Drive (requer rclone configurado)
# if [ ! -z "${GDRIVE_FOLDER}" ]; then
#     log "Enviando backup para Google Drive..."
#     rclone copy "${BACKUP_PATH}.gz" "gdrive:${GDRIVE_FOLDER}/backups/" \
#         --progress
#     if [ $? -eq 0 ]; then
#         log "Backup enviado para Google Drive com sucesso!"
#     else
#         warning "Falha ao enviar backup para Google Drive"
#     fi
# fi

# Para servidor remoto via SCP
# if [ ! -z "${REMOTE_BACKUP_HOST}" ]; then
#     log "Enviando backup para servidor remoto..."
#     scp -P ${REMOTE_BACKUP_PORT:-22} "${BACKUP_PATH}.gz" \
#         "${REMOTE_BACKUP_USER}@${REMOTE_BACKUP_HOST}:${REMOTE_BACKUP_PATH}/"
#     if [ $? -eq 0 ]; then
#         log "Backup enviado para servidor remoto com sucesso!"
#     else
#         warning "Falha ao enviar backup para servidor remoto"
#     fi
# fi

# Notificação (opcional - via webhook)
# if [ ! -z "${WEBHOOK_URL}" ]; then
#     curl -X POST "${WEBHOOK_URL}" \
#         -H "Content-Type: application/json" \
#         -d "{\"text\":\"Backup do banco ${DB_NAME} concluído com sucesso! Tamanho: ${BACKUP_SIZE}\"}"
# fi

# Estatísticas finais
log "========================================="
log "Backup concluído com sucesso!"
log "Arquivo: ${BACKUP_FILENAME}.gz"
log "Tamanho: ${BACKUP_SIZE}"
log "Total de backups mantidos: ${MAX_BACKUPS}"
log "========================================="

# Criar arquivo de status para monitoramento
echo "$(date +'%Y-%m-%d %H:%M:%S')|SUCCESS|${BACKUP_SIZE}" > ${BACKUP_DIR}/last_backup_status.txt
