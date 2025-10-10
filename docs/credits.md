Créditos — Visão Geral

- Carteiras por usuário (admin) em BRL (centavos), com ledger de débitos/créditos.
- Admins em `ALLOWED_ADMIN_IDS` possuem uso ilimitado (sem débitos e sem bloqueio).
- Débito por uso real:
  - IA de texto: baseado em `usage` (prompt/completion/cached/reasoning tokens).
  - Áudio: custo por minuto (env `WHISPER_COST_PER_MINUTE_USD`).
- Pré‑cheque conservador: calcula tokens de entrada com tokenização do provedor
  quando disponível e estima saída via média móvel. Em falta de saldo, bloqueia
  silenciosamente nos bots secundários (sem mensagem ao usuário final).

Variáveis de Ambiente

- `USD_TO_BRL_RATE=5.80`
- `PRICE_TEXT_INPUT_PER_MTOK_USD=0.20`
- `PRICE_TEXT_OUTPUT_PER_MTOK_USD=0.50`
- `PRICE_TEXT_CACHED_PER_MTOK_USD=0.05`
- `WHISPER_COST_PER_MINUTE_USD=0.006`
- `ESTIMATED_CHARS_PER_TOKEN=4.0`
- `PUSHINRECARGA=` Token do PushinPay usado especificamente para gerar a chave PIX de recarga

Uso no Bot Gerenciador

- Menu “💳 Créditos” no `/start`:
  - Mostra a **Central de Créditos** com saldo (detecta admins ilimitados),
    resumo dos últimos 30 dias (total recarregado/gasto) e estatísticas do dia
    (mensagens, tokens, gasto).
  - “➕ Adicionar Créditos”: cria cobrança PIX (PushinPay) nos valores
    sugeridos (R$ 10, 25, 50, 100). Exibe chave PIX formatada em MarkdownV2
    como bloco de código (copia e cola) e botão “Verificar depósito”.
  - “🧾 Minhas recargas”: lista as últimas recargas com valor, status e horário.

Política de Bloqueio Silencioso

- Se saldo chegar a 0 para um admin não‑ilimitado, bots secundários deixam de
  responder silenciosamente (sem mensagem literal ao usuário final). O log
  registra o evento para observabilidade.

Integração Técnica

- IA de texto: `services/ai/conversation.py` chama `CreditService.precheck_text`
  antes do request e `CreditService.debit_text_usage` após a resposta.
- Áudio: `workers/audio_tasks.py` chama `CreditService.precheck_audio` antes da
  transcrição e `CreditService.debit_audio` ao concluir.
- Tokenização: `GrokAPIClient.tokenize_text()` usa o endpoint do provedor; há
  fallback para heurística quando indisponível.

Observações

- Os preços são por 1M tokens e convertidos para BRL de acordo com a taxa
  configurada. Tokens em cache possuem preço próprio.
- Ledger registra categoria: `text`, `whisper`, `topup`.
