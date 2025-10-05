#!/bin/bash

# ==============================================================
# Script para Configurar SSL/HTTPS com Let's Encrypt
# ==============================================================

set -e

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

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

# Verificar se foi fornecido domínio
if [ -z "$1" ]; then
    error "Uso: $0 <seu-dominio.com>"
fi

DOMAIN=$1
EMAIL=${2:-"admin@$DOMAIN"}

log "Configurando SSL para domínio: $DOMAIN"
log "Email para notificações: $EMAIL"

# Instalar Certbot se necessário
if ! command -v certbot &> /dev/null; then
    log "Instalando Certbot..."
    sudo apt update
    sudo apt install -y certbot python3-certbot-nginx
fi

# Parar Nginx do Docker temporariamente
log "Parando Nginx do Docker..."
docker compose -f docker-compose.production.yml stop nginx

# Obter certificado
log "Obtendo certificado SSL..."
sudo certbot certonly \
    --standalone \
    --preferred-challenges http \
    --agree-tos \
    --no-eff-email \
    --email $EMAIL \
    -d $DOMAIN \
    -d www.$DOMAIN

if [ $? -eq 0 ]; then
    log "Certificado obtido com sucesso!"
else
    error "Falha ao obter certificado"
fi

# Copiar certificados para o diretório do projeto
log "Copiando certificados..."
sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem ./ssl/
sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem ./ssl/
sudo cp /etc/letsencrypt/live/$DOMAIN/chain.pem ./ssl/
sudo chown $(whoami):$(whoami) ./ssl/*
sudo chmod 644 ./ssl/*.pem

# Atualizar configuração do Nginx
log "Atualizando configuração do Nginx para HTTPS..."
cat > nginx/default.conf << 'EOF'
# Configuração Nginx com SSL

upstream app {
    server webhook:8000;
}

upstream flower {
    server flower:5555;
}

# Rate limiting
limit_req_zone $binary_remote_addr zone=telegram_webhook:10m rate=100r/s;
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=30r/s;

# Cache
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=api_cache:10m max_size=100m inactive=60m use_temp_path=off;

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name DOMAIN_PLACEHOLDER www.DOMAIN_PLACEHOLDER;
    return 301 https://$server_name$request_uri;
}

# HTTPS Server
server {
    listen 443 ssl http2;
    server_name DOMAIN_PLACEHOLDER www.DOMAIN_PLACEHOLDER;

    # SSL Configuration
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_trusted_certificate /etc/nginx/ssl/chain.pem;

    # SSL Security
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers off;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_stapling on;
    ssl_stapling_verify on;

    # Security headers
    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    client_max_body_size 50M;
    client_body_timeout 60s;

    # Webhook endpoint
    location /webhook {
        limit_req zone=telegram_webhook burst=50 nodelay;

        proxy_pass http://app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        proxy_connect_timeout 10s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        proxy_buffering off;
    }

    # API endpoints
    location /api {
        limit_req zone=api_limit burst=20 nodelay;

        proxy_pass http://app;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_cache api_cache;
        proxy_cache_valid 200 10m;
        proxy_cache_valid 404 1m;
    }

    # Health check
    location /health {
        proxy_pass http://app/health;
        access_log off;
    }

    # Flower UI
    location /flower/ {
        proxy_pass http://flower/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_redirect off;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Block sensitive files
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }

    # Logs
    access_log /var/log/nginx/access.log combined buffer=16k;
    error_log /var/log/nginx/error.log warn;
}
EOF

# Substituir placeholder pelo domínio real
sed -i "s/DOMAIN_PLACEHOLDER/$DOMAIN/g" nginx/default.conf

# Atualizar .env.production com HTTPS URL
log "Atualizando URL do webhook para HTTPS..."
sed -i "s|WEBHOOK_BASE_URL=.*|WEBHOOK_BASE_URL=https://$DOMAIN|" .env.production

# Reiniciar Nginx
log "Reiniciando Nginx com SSL..."
docker compose -f docker-compose.production.yml start nginx

# Configurar renovação automática
log "Configurando renovação automática do certificado..."

# Criar script de renovação
cat > scripts/renew-ssl.sh << 'EOF'
#!/bin/bash
certbot renew --pre-hook "docker compose -f /home/$USER/mitski/docker-compose.production.yml stop nginx" \
              --post-hook "docker compose -f /home/$USER/mitski/docker-compose.production.yml start nginx"

# Copiar certificados renovados
cp /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/fullchain.pem /home/$USER/mitski/ssl/
cp /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/privkey.pem /home/$USER/mitski/ssl/
cp /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/chain.pem /home/$USER/mitski/ssl/
EOF

sed -i "s/DOMAIN_PLACEHOLDER/$DOMAIN/g" scripts/renew-ssl.sh
chmod +x scripts/renew-ssl.sh

# Adicionar ao cron
(crontab -l 2>/dev/null; echo "0 3 * * 0 /home/$USER/mitski/scripts/renew-ssl.sh") | crontab -

log "SSL configurado com sucesso!"
log "Certificado válido por 90 dias com renovação automática configurada"
log "HTTPS está ativo em: https://$DOMAIN"
log ""
log "Não esqueça de atualizar o webhook do Telegram:"
log "docker compose -f docker-compose.production.yml exec webhook python scripts/setup_webhook.py"
