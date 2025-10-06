# Sistema de Recuperação de Usuários Inativos

## Objetivo
Permitir que administradores configurem sequências de mensagens enviadas automaticamente quando usuários de bots secundários ficam inativos. A solução é event-driven, assinada e segura, para operar com dezenas de bots e milhares de chats por minuto.

## Componentes Principais

### Modelagem (PostgreSQL)
- `recovery_campaigns`: configuração global do bot (fuso horário, threshold de inatividade, versão).
- `recovery_steps`: passos ordenados da sequência, com tipo de agenda (delay relativo, amanhã HH:MM, +NdHH:MM).
- `recovery_blocks`: blocos reutilizando o editor existente (texto, mídia, efeitos de delay/auto-delete).
- `recovery_deliveries`: idempotência, status (scheduled/sent) e audit trail de cada envio.

### Persistência & Serviços
- Repositórios dedicados em `database/recovery/` (campanha, passos, blocos, entregas).
- Parser de agendamento e timezone em `core/recovery/schedule.py`.
- Estado efêmero (Redis) em `core/recovery/state.py`: `last_active`, versões de inatividade, `episode_id`, versão de campanha por usuário.
- Servidor de mídia com cache e streaming em `services/recovery/sender.py` (compartilha lógica de oferta).

### Bot Gerenciador
- Botão `🔁 Recuperação` no `/start` usando callback assinado (`handlers/manager_handlers.py`).
- Menus e edição (`handlers/recovery/`):
  - `menu.py`: listar bots, passos, configuração de horários e exclusões.
  - `editor.py`: editor de blocos (texto, mídia, efeitos) com callbacks HMAC.
  - `settings.py`: ativar/desativar, ajustar threshold/timezone e ignorar automaticamente clientes com transações pagas (opção ativa por padrão).
- `handlers/recovery/callbacks.py`: gera/valida callbacks (`recovery:<token>`), TTL 15 minutos.

### Workers Celery
- `workers/recovery_scheduler.py` (`queue=recovery`):
 1. `schedule_inactivity_check`: agenda verificação após threshold.
 2. `check_inactive`: valida versão, detecta inatividade, cria episódio e agenda primeiro passo.
- `workers/recovery_sender.py`: envia blocos, aplica delays/auto-delete, agenda próximos passos encadeados (respeitando a configuração de ignorar pagantes).
- `workers/recovery_utils.py`: utilidades (fetch passos ativos, ensure delivery).
- `workers/tasks.py`: roteia callbacks `recovery:*` para os handlers já assinados.

### Fluxo de Inatividade
1. Cada mensagem recebida chama `mark_user_activity` (Redis) e agenda `check_inactive` com o threshold configurado (padrão: 10 min).
2. `check_inactive` compara a versão atual; se o usuário continuar inativo, gera `episode_id` e agenda o primeiro passo.
3. `send_recovery_step` envia blocos (stream de mídia se necessário), registra entrega e agenda o próximo passo com base no tipo de agenda, abortando se a campanha estiver configurada para ignorar clientes com pagamento já confirmado.
4. Interação do usuário cancela automaticamente a sequência porque a versão de inatividade muda.

### Observabilidade & Segurança
- Logs estruturados informam agendamentos, envios e motivos de skip (versão divergente, episódio ativo, campanha inativa).
- Callbacks HMAC evitam replay/forge (payload amarrado ao admin/objeto + TTL).
- Sequências só são alocadas se houver blocos ativos, evitando tarefas vazias.

### Testes & Validação
- Testes de parser e callbacks (`tests/test_recovery_schedule.py`, `tests/test_recovery_callbacks.py`).
- `python3 -m compileall` usado para verificação sintática rápida.
- Documentação adicional em `docs/recovery.md` (visão detalhada).

## Checklist Operacional
1. Executar `alembic upgrade head` para criar novas tabelas de recuperação.
2. Garantir workers Celery com fila `recovery` (ex.: `celery -A workers.celery_app worker --queue=recovery,...`).
3. Configurar `REDIS_*` para TTL de estado e `ENCRYPTION_KEY` compartilhada (HMAC).
4. Verificar logs (`Recovery step scheduled` / `Recovery step sent`) ao testar.
5. Opcional: expor métricas de episódios e filas para Prometheus.
