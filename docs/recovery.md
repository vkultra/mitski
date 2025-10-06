# Recuperação de Usuários Inativos

## Visão Geral

A funcionalidade de **Recuperação** permite que administradores programem sequências de mensagens para reconectar usuários que ficam inativos em bots secundários. O bot gerenciador oferece uma interface modular, reutilizando o editor de blocos existente (texto, mídia, efeitos) e suportando agendamentos relativos ou baseados em horário.

### Características
- Menu dedicado no `/start` do bot gerenciador (`🔁 Recuperação`).
- Seleção de bots administrados com paginação e callbacks assinados por HMAC com TTL.
- Sequências compostas por passos ordenados; cada passo possui blocos configurados com mídia, delay e autoexclusão.
- Agendamentos suportam: `10m`, `1h`, `amanhã 12:00`, `+2d18:00`, etc., aplicando fuso horário da campanha.
- Detecção de inatividade via Redis: toda mensagem do usuário atualiza `last_active` e agenda verificação com base no threshold configurado (default 10 minutos).
- Workers dedicados (`queue=recovery`) verificam inatividade, alocam episódios seguros e encadeiam envios via Celery.
- Envio resiliente com idempotência (`recovery_deliveries`), cache de mídia com streaming e auto-delete opcional.
- Logging estruturado (`Recovery step scheduled`, `Recovery step sent`, etc.) para observabilidade.
- Testes unitários cobrindo parser de horários e callbacks assinados (`tests/test_recovery_schedule.py`, `tests/test_recovery_callbacks.py`).

## Fluxo Operacional
1. **Configuração inicial**
   - Acesse o menu `🔁 Recuperação` e selecione o bot desejado.
   - Adicione mensagens de recuperação (cada linha = um passo). Utilize o editor de blocos para definir conteúdo e efeitos.
   - Configure o horário de disparo de cada passo e ajuste `Configurações` para alterar inatividade padrão, timezone, ativar/desativar a campanha ou ignorar clientes que já concluíram um pagamento (padrão: ignorar).

2. **Detecção e agendamento**
   - Ao detectar inatividade (`last_active + threshold`), a task `check_inactive` valida versão/estado, gera `episode_id` e agenda o primeiro passo.
   - Cada envio utiliza `RecoveryMessageSender`, respeitando delays, auto-delete e caching de mídia por bot.
   - Após enviar um passo, o próximo é programado com base no horário/atraso configurado; se não houver próximos passos, o episódio é encerrado.

3. **Cancelamento automático**
   - Qualquer nova mensagem do usuário incrementa a versão de inatividade, invalida o episódio atual e remove callbacks pendentes.
   - Modificações na campanha (texto, mídia, horários, status) incrementam a versão e evitam envios de configurações desatualizadas.

## Considerações Técnicas
- **Modelos**: tabelas `recovery_campaigns`, `recovery_steps`, `recovery_blocks`, `recovery_deliveries` (Alembic `02331f82b808_add_recovery_tables`).
- **Repositórios**: `database/recovery/*` fornecem operações segmentadas (<280 linhas por arquivo).
- **Tasks**:
  - `workers/recovery_scheduler.py` (`schedule_inactivity_check`, `check_inactive`).
  - `workers/recovery_sender.py` (`send_recovery_step`).
  - Helpers reutilizáveis em `workers/recovery_utils.py`.
- **Estado Redis**: `core/recovery/state.py` mantém `last_active`, versões de inatividade, episódios e snapshots de campanha com TTL de 30 dias.
- **Segurança**: callbacks usam `handlers/recovery/callbacks.py` (HMAC + TTL de 15 min); tokens inválidos retornam aviso.
- **Streaming de mídia**: reaproveita `services/recovery/sender.py` (cache multi-bot + auto delete).
- **Logs**: `core.telemetry.logger` registra cada agendamento/envio e motivos de skip (versão divergente, episódio ativo, campanha inativa).

## Execução e Testes
- **Fila Celery**: garanta workers ouvindo `recovery` (`celery -A workers.celery_app worker --queue=recovery,...`).
- **Testes executados**:
  - `pytest tests/test_recovery_schedule.py tests/test_recovery_callbacks.py`
- **Compilação**: `python3 -m compileall handlers/recovery workers` (verificação rápida de sintaxe).

## Próximos Passos
- Adicionar métricas Prometheus específicas (`tasks` agendadas, episódios ativos, skips por motivo).
- Expandir testes para cobrir tarefas com mocks de Redis/DB (ex.: `check_inactive` e `send_recovery_step`).
- Criar comandos administrativos para listar sequências e episódios ativos.
