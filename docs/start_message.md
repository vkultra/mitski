# Mensagem Inicial Personalizada (/start)

## Visão Geral
- Permite definir blocos de texto, mídia e efeitos enviados somente no primeiro `/start` de cada usuário.
- Configuração disponível em `IA → Ações → /start | Configurar` (somente administradores permitidos).
- Utiliza o mesmo editor modular dos blocos de Pitch, Upsell e Entregável.
- Processamento assíncrono via Celery com controle de idempotência em Redis + PostgreSQL.

## Fluxo de Configuração
1. Abra `IA → Ações` e use o botão `Configurar` ao lado de `/start`.
2. Adicione blocos usando os botões `Texto/Legenda`, `Mídia`, `Efeitos` (Delay e Auto-delete) e `Pré-visualizar`.
3. O toggle `✅ Ativar / ⏸️ Desativar` controla se o template será utilizado.
4. Cada alteração incrementa a versão do template; novos usuários receberão sempre a versão mais recente.

## Execução em Tempo Real
- O primeiro `/start` dispara `StartFlowService`, que:
  - Verifica anti-spam e estado do usuário.
  - Garante exclusividade por bot+usuário (`SETNX` em Redis, TTL 10 minutos).
  - Agenda `workers.start_tasks.send_start_message` com Celery.
- O worker recupera os blocos, envia usando `StartTemplateSenderService` (mesma pipeline de cache/stream de mídia das ações) e registra o envio em `start_message_status`.
- `/start` subsequentes pulam o template e voltam ao fluxo normal (IA ou handlers padrões).

## Segurança e Anti-SPAM
- Respeita todas as regras do `AntiSpamService` (`loop_start`, flood, etc.) antes de agendar o envio.
- Tokens de bots continuam criptografados com Fernet; envio assíncrono faz `decrypt` no worker.
- Cache de mídia por bot em `media_file_cache` evita re-upload desnecessário.

## Observabilidade
- Logs estruturados em `StartFlowService` e `workers.start_tasks` indicam agendamentos, skips e falhas.
- Métricas Prometheus:
  - `start_template_scheduled_total{result}` (`scheduled`, `inactive`, `pending`, `already_sent`).
  - `start_template_delivered_total{status}` (`success`, `skipped`, `bot_inactive`, `already_sent`, `error`).

## Estrutura de Dados
- `start_templates`: metadados (`bot_id`, `version`, `is_active`).
- `start_template_blocks`: blocos ordenados com texto, mídia, delay, auto-delete.
- `start_message_status`: marca usuários que já receberam a mensagem (`bot_id`, `user_telegram_id`, `template_version`, `sent_at`).
- Migração: `alembic/versions/20240308_01_add_start_template_tables.py`.

## Testes
- `tests/test_start_flow.py` valida agendamento idempotente e execução do worker com `FakeRedis` e mocks da API do Telegram.

## Limites e Boas Práticas
- Máximo recomendado: 10 blocos por template com mídia otimizada (<10 MB) para garantir latência baixa.
- Delay máximo por bloco: 300 s; auto-delete máximo: 86400 s.
- Sempre utilize `Pré-visualizar` para validar formato antes de ativar o template em produção.
- Métricas e logs devem ser monitorados (alerta em `error` > 0 ou `scheduled` >> `success`).
