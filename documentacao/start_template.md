# Mensagem Inicial (/start)

Este documento descreve a arquitetura do editor de mensagem inicial e o fluxo de envio para cada bot secundário.

## Configuração via Bot Gerenciador

- Acesse `IA → Ações → /start → Configurar`.
- Os botões `Texto`, `Midias`, `Efeitos` etc reutilizam o editor modular de blocos (mesma abordagem dos menus de Pitch/Entregável).
- A pré-visualização é enviada pelo bot gerenciador com `cache_media=False`, evitando que file_ids do gerenciador poluam o cache dos bots secundários.
- Após a pré-visualização, o menu é reconstruído automaticamente para acelerar novas edições.

## Persistência

- Tabela `start_templates` guarda o template ativo por bot.
- Tabela `start_template_blocks` armazena cada bloco (ordem, texto, mídia, delays, auto delete).
- `MediaFileCacheRepository` salva o mapeamento `original_file_id` → `cached_file_id` por bot secundário.

## Envio para usuários finais

1. `StartFlowService` controla idempotência usando Redis (`start_template:pending:{bot_id}:{user_id}`).
2. `workers.start_tasks.send_start_message` agenda o envio assíncrono após validar se o usuário já recebeu a versão atual.
3. `StartTemplateSenderService`:
   - aplica typing effect antes de cada bloco (respeitando delays);
   - usa cache de mídia por bot;
   - dispara auto delete quando configurado.

## Tratamento de mídia (arquivo/cache)

- Primeiro tenta enviar com `cached_file_id` armazenado.
- Se o Telegram retornar `wrong file identifier` ou `file reference expired`, o serviço:
  - remove o cache inválido (`MediaFileCacheRepository.clear_cached_file_id`);
  - força novo download usando o bot gerenciador e reenvia em streaming;
  - grava o novo `cached_file_id` para reutilização.
- Em erros de parsing (`can't parse entities`) a retentativa ocorre sem `parse_mode`, garantindo entrega do bloco mesmo com caracteres especiais.
- Logs estruturados registram o `template_block_id`, ids de arquivo e descrição retornada pelo Telegram para facilitar troubleshooting.

## Proteções anti-abuso

- Flood no `/start` respeita a camada atual de antispam (ban automático conforme configurado em `menu ANTISPAM`).
- O template só dispara uma vez por usuário e versão; repetições chamam apenas a IA ou ações subsequentes.

## Métricas e testes

- Métricas Prometheus: `start_template_delivered_total` (sucesso, erro, skip) e contadores de fallback em `services/start/metrics.py`.
- Testes unitários focam na recuperação de mídia (`tests/test_start_sender_recovery.py`).
- Recomenda-se rodar `pytest`, `flake8`, `mypy` (ciente dos erros legados) e `bandit` após alterações.
