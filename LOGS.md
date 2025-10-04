# 📊 Guia de Visualização de Logs

Este documento explica como visualizar e monitorar os logs do Telegram Bot Manager.

## Opções de Visualização

### 1. Logs em Tempo Real (Recomendado para Debug)

```bash
# Seguir logs de todos os containers
docker-compose logs -f webhook worker

# Seguir apenas logs do webhook
docker-compose logs -f webhook

# Seguir apenas logs dos workers
docker-compose logs -f worker
```

### 2. Script Interativo de Logs

Use o script `view_logs.sh` para acesso rápido:

```bash
./view_logs.sh
```

**Opções disponíveis:**
1. Ver logs em tempo real (Docker containers)
2. Ver arquivo de log (logs/app.log)
3. Ver logs filtrados por "AI conversation"
4. Ver logs filtrados por "Grok API"
5. Seguir logs em tempo real do arquivo

### 3. Logs Estruturados (JSON)

Os logs são salvos em formato JSON estruturado. Para visualizar de forma legível:

```bash
# Visualizar últimos 50 logs formatados
docker-compose logs webhook worker --tail=50 | grep "timestamp" | jq '.'

# Filtrar logs de IA
docker-compose logs webhook worker | grep "AI conversation"

# Filtrar logs da API Grok
docker-compose logs webhook worker | grep "Grok API"
```

### 4. Arquivo de Log Persistente

Os logs também são salvos em `logs/app.log` (dentro do container). Para acessar:

```bash
# Copiar logs do container para host
docker cp $(docker ps -qf "name=mitski-webhook"):/app/logs/app.log ./logs/app.log

# Ver últimas 100 linhas
tail -100 logs/app.log | jq '.'
```

## Informações Logadas

### Para Conversações com IA

Cada interação com a IA Grok registra:

**Início da Conversação:**
- ✅ `bot_id`: ID do bot
- ✅ `user_telegram_id`: ID do usuário
- ✅ `has_photos`: Se mensagem contém fotos
- ✅ `user_message`: Preview da mensagem (200 caracteres)

**Configuração Carregada:**
- ✅ `model_type`: "reasoning" ou "non-reasoning"
- ✅ `temperature`: Temperatura do modelo (0.0-2.0)
- ✅ `max_tokens`: Limite de tokens
- ✅ `general_prompt_preview`: Preview do prompt geral (200 caracteres)

**Sessão e Histórico:**
- ✅ `current_phase_id`: ID da fase atual
- ✅ `current_phase_name`: Nome da fase
- ✅ `history_size`: Quantidade de mensagens no histórico

**Requisição à API Grok:**
- ✅ `model`: Modelo usado (grok-4-fast-reasoning/non-reasoning)
- ✅ `temperature`: Temperatura
- ✅ `max_tokens`: Limite de tokens
- ✅ `num_messages`: Quantidade de mensagens enviadas
- ✅ `system_prompt`: Preview do system prompt (200 caracteres)
- ✅ `last_user_message`: Preview da última mensagem do usuário (200 caracteres)

**Resposta da API Grok:**
- ✅ `usage`: Estatísticas de uso de tokens
  - `prompt_tokens`: Tokens do prompt
  - `cached_tokens`: Tokens em cache (economia!)
  - `completion_tokens`: Tokens da resposta
  - `reasoning_tokens`: Tokens de raciocínio (reasoning models)
  - `total_tokens`: Total de tokens
- ✅ `cached_tokens`: Tokens em cache (destacado)
- ✅ `concurrent_requests`: Requisições concorrentes no momento
- ✅ `response_preview`: Preview da resposta (200 caracteres)
- ✅ `has_reasoning`: Se modelo usou raciocínio interno
- ✅ `finish_reason`: Motivo de término ("stop", "length", etc)

**Transição de Fase (se houver):**
- ✅ `detected_trigger`: Trigger detectado na resposta
- ✅ `new_phase_id`: ID da nova fase
- ✅ `new_phase_name`: Nome da nova fase

**Finalização:**
- ✅ `response_length`: Tamanho da resposta em caracteres
- ✅ `total_tokens`: Total de tokens usados

## Exemplos de Uso

### Monitorar todas as conversas de IA em tempo real

```bash
docker-compose logs -f webhook worker | grep "AI conversation"
```

### Ver estatísticas de uso de tokens

```bash
docker-compose logs webhook worker | grep "cached_tokens" | jq '.cached_tokens'
```

### Filtrar por bot específico

```bash
docker-compose logs webhook worker | grep '"bot_id": 1'
```

### Ver erros apenas

```bash
docker-compose logs webhook worker | grep '"level": "ERROR"'
```

### Exportar logs para análise

```bash
docker-compose logs webhook worker --no-color > logs_export.json
```

## Troubleshooting

### Logs não aparecem

```bash
# Verificar se containers estão rodando
docker-compose ps

# Reiniciar containers
docker-compose restart webhook worker

# Ver logs de startup
docker-compose logs webhook worker --tail=100
```

### Arquivo app.log vazio no host

Isso é normal! Os logs são escritos dentro do container. Para acessá-los, use:

```bash
docker exec -it $(docker ps -qf "name=mitski-webhook") cat /app/logs/app.log
```

### Logs muito grandes

Os logs rotacionam automaticamente:
- Tamanho máximo: 10MB por arquivo
- Backups mantidos: 5 arquivos
- Total máximo: ~50MB

Para limpar logs antigos:

```bash
# Dentro do container
docker exec -it $(docker ps -qf "name=mitski-webhook") rm -f /app/logs/app.log.*
```

## Formato JSON dos Logs

Exemplo de log estruturado:

```json
{
  "timestamp": 1759553947.759412,
  "level": "INFO",
  "service": "telegram-bot-manager",
  "logger": "telegram_bot_manager",
  "message": "Grok API request successful (SDK)",
  "model": "grok-4-fast-non-reasoning",
  "usage": {
    "prompt_tokens": 1520,
    "cached_tokens": 1200,
    "completion_tokens": 180,
    "reasoning_tokens": 0,
    "total_tokens": 1700
  },
  "cached_tokens": 1200,
  "concurrent_requests": 1,
  "response_preview": "Olá! Como posso ajudar você hoje?...",
  "has_reasoning": false,
  "finish_reason": "stop"
}
```

## Dicas

1. **Use `jq` para formatar**: Instale com `brew install jq` (Mac) ou `apt install jq` (Linux)
2. **Combine filtros**: `docker-compose logs -f webhook worker | grep "AI conversation" | grep "bot_id: 1"`
3. **Salve logs importantes**: Use `docker-compose logs > backup.log` antes de reiniciar
4. **Monitore performance**: Observe `concurrent_requests` e `cached_tokens`
5. **Debug erros**: Use `--tail=1000` para ver contexto completo

## Logs de Produção

Em produção, considere integrar com:
- **Sentry** (já configurado): Captura erros automaticamente
- **ELK Stack**: Elasticsearch + Logstash + Kibana
- **Grafana Loki**: Logs + métricas
- **CloudWatch** (AWS): Logs centralizados
