**Notificações de Vendas — Guia de Arquitetura e Operação**

- Objetivo
  - Enviar, de forma opcional e assíncrona, uma notificação para um canal configurado pelo usuário sempre que uma venda for aprovada, sem duplicar entre detecção automática (gateway) e manual.

**Visão Geral**
- Evento de venda aprovada dispara tarefa assíncrona.
- Deduplicação com lock curto em Redis + unicidade no banco.
- Mensagem enviada pelo bot gerenciador ao canal definido (por bot ou padrão do usuário).

**Fluxo**
- Emissão: `services/sales/events.py:13` (`emit_sale_approved`) aplica lock Redis e enfileira `enqueue_sale_notification`.
- Enfileiramento: `workers/notifications/tasks.py:34` resolve canal ativo (por bot > padrão) e registra linha em `sale_notifications` (status `pending|skipped`).
- Envio: `workers/notifications/tasks.py:76` renderiza template e envia via `TelegramNotificationClient` com `MANAGER_BOT_TOKEN`; atualiza status `sent|failed`.

**Formatação da Mensagem**
- Template: `core/notifications/renderer.py:19` (HTML com sanitização básica)
- Estrutura:
  - Título: “🎉 Venda Aprovada!” em negrito
  - “💰 Valor: R$ X,YY”
  - “👤 Usuário: @username [ID: 123]”
  - “🤖 Bot: @username_do_bot”
  - Quando upsell: adiciona “🛒 Tipo: Upsell”

**Configuração (Gerenciador)**
- Menu “Notificações” em `/start` (aberto a qualquer usuário):
  - Definir/Alterar Canal (por bot específico ou padrão)
  - Ver Configuração
  - Desativar
  - Enviar Teste (envia mensagem real ao canal)
- Handlers: `handlers/notifications/manager_menu.py:24` e `handlers/notifications/validation.py:73`.
- Validação do canal: `getChat` + envio de confirmação; só persiste se sucesso.

**Idempotência e Escalabilidade**
- Chave curta em Redis: `core/notifications/dedup.py:12` (evita race de curto prazo entre origens auto/manuais).
- Unicidade forte no DB: `database/notifications/models.py:49` (unique em `transaction_id`).
- Assíncrono via Celery: `workers/celery_app.py:68` com fila dedicada do pacote `workers.notifications`.

**Dados e Persistência**
- Tabelas:
  - `notification_settings` (por `owner_user_id`, opcional por `bot_id`): canal e `enabled`.
  - `sale_notifications`: `transaction_id`, `owner_user_id`, `bot_id`, `channel_id`, `is_upsell`, `amount_cents`, `buyer_*`, `status`, `error`, `notified_at`.
- Repositórios: `database/notifications/repos.py:16` (upsert/list/disable) e `:162` (insert-on-conflict + status).

**Integrações de Pagamento**
- Automático: `workers/payment_tasks.py:60` e `services/gateway/payment_verifier.py:41` chamam `emit_sale_approved` quando status muda para “paid”.
- Manual: `services/ai/conversation.py:453` chama `emit_sale_approved` após confirmação.
- Upsell: `workers/upsell_tasks.py:224`/`:296` chama `emit_sale_approved` (man/auto).

**Observabilidade**
- Métricas: `core/notifications/metrics.py:21` expõe contadores `sale_notifications_enqueued_total{origin}` e `sale_notifications_processed_total{status}`.
- Logs: correlacionam `transaction_id`, `owner_user_id`, `bot_id`, `channel_id` e `status`.

**Configuração de Ambiente**
- Variáveis:
  - `MANAGER_BOT_TOKEN` (obrigatório para enviar ao canal)
  - `ENABLE_SALE_NOTIFICATIONS=true|false`
  - Redis/DB/Celery conforme projeto (`.env` padrão)

**Migração**
- As tabelas são criadas por `alembic upgrade head` com a revisão `c9f5b2a1d3e4` em `database/migrations/versions/c9f5b2a1d3e4_add_sale_notifications_tables.py:1`.

**Como Usar**
- No bot gerenciador, entre em “Notificações” > “Definir/Alterar Canal” > escolha escopo (padrão ou bot) > envie o ID `-100...` ou `@canal`. O sistema valida e envia uma mensagem de confirmação.
- Para testar: “Notificações” > “Enviar Teste”.

**Testes Disponíveis**
- Conjunto de testes focados nas notificações:
  - `tests/test_notifications.py:19` — Repositórios de configuração e registro; renderização; emissão de evento; menu; validação de canal.
  - `tests/test_notifications_idempotency.py:1` — Locks Redis (aquisição/soltura) para idempotência.
- Rodando apenas os testes de notificações:
  - `pytest -q tests/test_notifications.py`
  - `pytest -q tests/test_notifications_idempotency.py`
  - Ou por seleção: `pytest -q -k notifications`

**Boas Práticas e Limites**
- Não enviar tokens/segredos em logs.
- Evitar payloads grandes; manter tempo de resposta do webhook mínimo (sempre enfileirar).
- Respeitar limite do Telegram (retries com backoff já implementados).

**Perguntas Frequentes**
- “Por que o envio usa o bot gerenciador?” Para centralizar permissões no canal e evitar expor tokens de bots secundários.
- “Como separar upsell?” O campo `is_upsell` personaliza a mensagem e pode direcionar canal separado futuramente.

