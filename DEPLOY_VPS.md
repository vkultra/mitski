# 📚 Guia Completo de Deploy para VPS Ubuntu

## 📋 Pré-requisitos

- VPS Ubuntu 20.04+ com pelo menos 2GB RAM e 20GB disco
- Acesso SSH root ou sudo
- Domínio (opcional, mas recomendado para HTTPS)
- Tokens do Telegram Bot e xAI API

## 🚀 Instalação Rápida

```bash
# 1. Conectar na VPS via SSH
ssh root@SEU_IP_VPS

# 2. Clonar o repositório
git clone https://github.com/SEU_USUARIO/SEU_REPO.git mitski
cd mitski

# 3. Configurar variáveis de ambiente
cp .env.production .env.production.backup
nano .env.production
# Configure todos os tokens e URLs necessários

# 4. Executar instalação completa
chmod +x scripts/deploy.sh
./scripts/deploy.sh install

# 5. Verificar status
./scripts/deploy.sh status
```

## 🔧 Configuração Manual Detalhada

### 1️⃣ Preparar o Servidor

```bash
# Atualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar ferramentas essenciais
sudo apt install -y git vim htop curl wget unzip

# Configurar timezone
sudo timedatectl set-timezone America/Sao_Paulo

# Criar swap (se necessário)
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 2️⃣ Instalar Docker

```bash
# Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Adicionar usuário ao grupo docker
sudo usermod -aG docker $USER

# Instalar Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verificar instalação
docker --version
docker-compose --version
```

### 3️⃣ Configurar Firewall

```bash
# Configurar UFW
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 5555/tcp  # Flower (opcional)
sudo ufw --force enable

# Verificar status
sudo ufw status
```

### 4️⃣ Configurar o Projeto

```bash
# Clonar repositório
cd /home/$USER
git clone https://github.com/SEU_USUARIO/SEU_REPO.git mitski
cd mitski

# Configurar variáveis de ambiente
nano .env.production
```

**Variáveis importantes para configurar:**

```env
MANAGER_BOT_TOKEN=seu_token_real_aqui
WEBHOOK_BASE_URL=https://seu_dominio_ou_ip
XAI_API_KEY=seu_token_xai
ALLOWED_ADMIN_IDS=seu_id_telegram
DB_PASSWORD=senha_forte_para_producao
FLOWER_PASSWORD=senha_para_flower
```

### 5️⃣ Gerar Chave de Encriptação

```bash
# Gerar chave
python3 -c "from cryptography.fernet import Fernet; import base64; print('base64:' + base64.b64encode(Fernet.generate_key()).decode())"

# Adicionar ao .env.production
nano .env.production
# Substitua ENCRYPTION_KEY pela chave gerada
```

## 🐳 Comandos Docker

### Build e Deploy

```bash
# Build das imagens
docker compose -f docker-compose.production.yml build

# Iniciar todos os serviços
docker compose -f docker-compose.production.yml up -d

# Ver logs em tempo real
docker compose -f docker-compose.production.yml logs -f

# Parar todos os serviços
docker compose -f docker-compose.production.yml down

# Reiniciar serviço específico
docker compose -f docker-compose.production.yml restart webhook
```

### Gerenciamento de Containers

```bash
# Listar containers rodando
docker ps

# Ver logs de um container
docker logs mitski-webhook-1 --tail 100 -f

# Executar comando em container
docker exec -it mitski-webhook-1 bash

# Ver uso de recursos
docker stats

# Limpar recursos não utilizados
docker system prune -a
```

## 📦 Migrações e Banco de Dados

```bash
# Executar migrações
docker compose -f docker-compose.production.yml exec webhook alembic upgrade head

# Criar nova migração
docker compose -f docker-compose.production.yml exec webhook alembic revision -m "descrição"

# Rollback de migração
docker compose -f docker-compose.production.yml exec webhook alembic downgrade -1

# Acessar PostgreSQL
docker exec -it mitski-postgres-1 psql -U admin -d telegram_bots

# Backup manual do banco
docker exec mitski-postgres-1 pg_dump -U admin telegram_bots > backup_$(date +%Y%m%d_%H%M%S).sql
```

## 🔄 Configurar Webhook do Telegram

```bash
# Configurar webhook automaticamente
docker compose -f docker-compose.production.yml exec webhook python scripts/setup_webhook.py

# Verificar webhook manualmente
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
```

## 🔐 Configurar SSL/HTTPS com Let's Encrypt

```bash
# Instalar Certbot
sudo apt install certbot python3-certbot-nginx -y

# Obter certificado (substitua pelo seu domínio)
sudo certbot --nginx -d seu-dominio.com -d www.seu-dominio.com

# Renovação automática
sudo certbot renew --dry-run

# Adicionar ao crontab para renovação automática
sudo crontab -e
# Adicionar: 0 0 * * 0 certbot renew --quiet
```

## 💾 Backup e Restore

### Backup Automático

```bash
# Configurar backup diário via cron
crontab -e
# Adicionar:
0 2 * * * cd /home/$USER/mitski && ./scripts/backup.sh

# Backup manual
./scripts/backup.sh
```

### Restore de Backup

```bash
# Listar backups disponíveis
ls -la ~/backups/

# Restore do backup
docker exec -i mitski-postgres-1 psql -U admin telegram_bots < ~/backups/backup_20240101_020000.sql
```

## 📊 Monitoramento

### Health Check

```bash
# Verificar saúde do sistema
./scripts/health-check.sh

# Adicionar ao cron para verificação automática
crontab -e
# Adicionar: */15 * * * * /home/$USER/mitski/scripts/health-check.sh
```

### Acessar Flower (Monitoramento Celery)

```bash
# Flower estará disponível em:
http://SEU_IP:5555/flower/

# Login: admin
# Senha: definida em FLOWER_PASSWORD no .env.production
```

### Logs e Debugging

```bash
# Ver todos os logs
docker compose -f docker-compose.production.yml logs

# Logs de serviço específico
docker compose -f docker-compose.production.yml logs webhook -f

# Logs do Nginx
docker exec mitski-nginx-1 tail -f /var/log/nginx/access.log
docker exec mitski-nginx-1 tail -f /var/log/nginx/error.log

# Debug de Celery
docker exec mitski-worker-1 celery -A workers.celery_app inspect active
docker exec mitski-worker-1 celery -A workers.celery_app inspect stats
```

## 🔧 Manutenção

### Atualizar Aplicação

```bash
cd /home/$USER/mitski

# Fazer backup antes
./scripts/backup.sh

# Atualizar código
git pull origin main

# Rebuild e deploy
./scripts/deploy.sh update
```

### Limpar Recursos

```bash
# Limpar logs antigos
docker compose -f docker-compose.production.yml exec webhook find /var/log -name "*.log" -mtime +30 -delete

# Limpar imagens Docker não utilizadas
docker image prune -a -f

# Limpar volumes não utilizados
docker volume prune -f

# Limpar backups antigos (manter últimos 7)
find ~/backups -name "backup_*.sql.gz" -mtime +7 -delete
```

### Reiniciar Serviços

```bash
# Reiniciar todos os serviços
./scripts/deploy.sh restart

# Reiniciar serviço específico
docker compose -f docker-compose.production.yml restart webhook

# Reiniciar Docker
sudo systemctl restart docker
```

## 🚨 Troubleshooting

### Problemas Comuns

#### 1. Container não inicia

```bash
# Ver logs detalhados
docker compose -f docker-compose.production.yml logs webhook

# Verificar variáveis de ambiente
docker compose -f docker-compose.production.yml config

# Reconstruir imagem
docker compose -f docker-compose.production.yml build --no-cache webhook
```

#### 2. Banco de dados não conecta

```bash
# Verificar se PostgreSQL está rodando
docker ps | grep postgres

# Testar conexão
docker exec mitski-postgres-1 pg_isready

# Ver logs do PostgreSQL
docker logs mitski-postgres-1
```

#### 3. Webhook não funciona

```bash
# Verificar webhook atual
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo

# Remover webhook
curl https://api.telegram.org/bot<TOKEN>/deleteWebhook

# Configurar novamente
docker compose -f docker-compose.production.yml exec webhook python scripts/setup_webhook.py
```

#### 4. Memória insuficiente

```bash
# Ver uso de memória
free -h
docker stats

# Limitar recursos no docker-compose
# Editar docker-compose.production.yml e ajustar limits
```

## 📝 Comandos Úteis Rápidos

```bash
# Status rápido
docker compose -f docker-compose.production.yml ps

# Reiniciar tudo
docker compose -f docker-compose.production.yml restart

# Parar tudo
docker compose -f docker-compose.production.yml stop

# Iniciar tudo
docker compose -f docker-compose.production.yml start

# Ver logs últimas 100 linhas
docker compose -f docker-compose.production.yml logs --tail=100

# Executar comando Python no container
docker compose -f docker-compose.production.yml exec webhook python -c "print('teste')"

# Executar shell no container
docker compose -f docker-compose.production.yml exec webhook /bin/bash
```

## 🔒 Segurança

### Checklist de Segurança

- [ ] Alterar senhas padrão no .env.production
- [ ] Configurar firewall (UFW)
- [ ] Habilitar HTTPS com SSL
- [ ] Configurar SSH keys (desabilitar senha)
- [ ] Manter sistema atualizado
- [ ] Configurar backups automáticos
- [ ] Monitorar logs regularmente
- [ ] Limitar IDs de admin no bot

### Hardening SSH

```bash
# Editar configuração SSH
sudo nano /etc/ssh/sshd_config

# Configurações recomendadas:
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
Port 2222  # Mudar porta padrão

# Reiniciar SSH
sudo systemctl restart sshd
```

## 📞 Suporte

Se encontrar problemas:

1. Verifique os logs: `docker compose logs`
2. Execute health check: `./scripts/health-check.sh`
3. Consulte a seção de Troubleshooting
4. Verifique se todas as variáveis de ambiente estão configuradas

---

**Última atualização:** Janeiro 2025
