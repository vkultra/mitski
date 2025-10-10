# Rastreamento de /start

Este módulo permite que administradores criem links de rastreio por bot, acompanhem starts/vendas e controlem a aceitação de /start sem códigos.

## Fluxo do Bot Gerenciador
- O /start exibe o botão **Rastreio** para qualquer usuário. Admins têm acesso completo; não admins recebem aviso de acesso negado.
- Menu principal mostra destaques do dia, com opções: **Novo**, **Meus Rastreios**, **Bloquear /start sem rastreio**, **Atualizar**.
- Criação de rastreio:
  - Seleção de bot (lista se houver mais de um).
  - Solicitação de nome (3-48 caracteres, normalização automática).
  - Resposta inclui deep link (`https://t.me/<bot>?start=<code>`) e atalhos para link, métricas e exclusão.
- Listagem exibe 5 rastreios por página com estatísticas do dia, navegação por página/dia e atalhos para link (alert), detalhamento e exclusão.
- Detalhe mostra métricas do dia e timeline de 7 dias (starts, vendas, faturamento) com navegação de datas.
- Exclusão é soft delete (`is_active=False`); links deixam de funcionar imediatamente.

## Toggle de Bloqueio
- Configuração por bot, padrão desativado (texto "desligado" no botão).
- Quando ativado (texto "ativo"), qualquer `/start` sem código válido é ignorado (sem resposta, nem IA).
- Bots sem rastreios ativos não são afetados, mesmo com toggle ligado.
- Mudança registra `last_forced_at` e atualiza cache (`trk:cfg:<bot_id>`).

## Lógica do Webhook
- `services.tracking.runtime.handle_start` analisa `/start`:
  - Extrai código, valida e registra start (`TrackerAttribution`, `TrackerDailyStat`).
  - Cache de códigos (`trk:code:<bot_id>:<code>`) e atribuições (`trk:attr:<bot_id>:<user_id>`) em Redis (TTL 7d e 30d).
  - Retorna estados `tracked`, `pass` ou `ignored`; worker encerra processamento em caso de `ignored`.
- Vendas aprovadas (`emit_sale_approved`) atribuem rastreio automaticamente usando a última atribuição do usuário (TTL/DB) e incrementam métricas diárias (vendas + faturamento).

## Modelagem & Migração
- Tabelas novas (`tracker_links`, `tracker_daily_stats`, `tracker_attributions`, `bot_tracking_configs`) com índices para bot/usuário/tracker.
- `pix_transactions` ganha coluna `tracker_id` (FK com `SET NULL`).
- Migração gera índices e FK; compatível com Alembic.

## Métricas
- `TrackerDailyStat` consolidado por dia (starts, vendas, `revenue_cents`).
- Atualizações via `upsert` atômico (`ON CONFLICT`).
- Top 3 diários carregados por `load_daily_summary_for_admin`.

## Segurança
- Tokens compactos (`trk:`) usam HMAC (SHA-256, TTL 5 min) e payload curto `action:user:bot:tracker:extra:ts`.
- Rate limit reutiliza mecanismos globais existentes; operações críticas mantêm idempotência.
- Códigos de rastreio base62 (8 chars) únicos por bot.

## Testes
- `tests/test_tracking.py` cobre extração de códigos, fluxo de start (tracked/ignored) e agregação de vendas.
- Utiliza SQLite in-memory + FakeRedis, garantindo independência de Postgres/Redis reais.

## Scripts Relevantes
- `alembic upgrade a23da2f2695c`
- `pytest tests/test_tracking.py`
- `black`, `isort`, `flake8`, `mypy`, `bandit`

## Limitações & Próximos Passos
- Timeline fixa em 7 dias; avaliar filtros customizados se necessário.
- Toggle não bloqueia usuários previamente atribuídos sem código adicional (design atual).
- Considerar UI adicional para exportar dados (CSV) ou gráficos.
