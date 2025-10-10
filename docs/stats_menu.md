# Estatísticas do Bot Gerenciador

## Visão geral
- Botão `📈 Estatísticas` disponível no `/start` do gerenciador (somente admins).
- Consolida vendas, faturamento bruto, upsells, /starts e ROI por dia ou período customizado.
- Dados refrescados on-demand com caching rápido em Redis (TTL curto).

## Navegação diária
- Cabeçalho informa o dia ou período selecionado.
- Teclado com `◀️ Dia anterior`, `📍 Hoje`, `▶️ Próximo dia`.
- Opção `🔄 Atualizar` recria o painel com dados mais recentes.

## Resumos disponíveis
- **Resumo**: vendas e faturamento totais, upsells, starts, conversão, ROI/custos.
- **🏆 Top bots**: ranking por faturamento com conversão e ROI atribuídos (custos gerais distribuídos proporcionalmente).
- **⏰ Horários**: horas com maior volume de vendas.
- **📉 Abandono**: taxa por fase de IA (entra vs. avança) para bots com IA ativa.
- **🧾 Custos**: lançamento/edição de custos gerais ou por bot; ROI recalculado instantaneamente.

## Gráfico de vendas
- Sempre que o admin abre o menu ou troca de período, o bot edita a mesma mensagem para anexar um PNG com as vendas dos últimos 7 dias (tema dark, barras).
- O gráfico é gerado uma vez por dia (ou novamente ao clicar em `🔄 Atualizar`) e fica em cache por admin+período. Isso evita atrasos para outros usuários e impede vazamento entre contas.
- Enquanto o gráfico carrega, o texto aparece primeiro; assim que o arquivo fica pronto o worker substitui a mensagem mantendo o mesmo teclado inline.

## Filtros e períodos
- Botão `🔎 Filtros` abre um seletor de datas inline (calendário das últimas semanas).
- Primeiro escolha a data inicial; em seguida, a data final. Um botão `↩️ Cancelar` retorna ao painel atual.
- Resultado destaca o período escolhido (ex.: `06/10/2025 → 09/10/2025`).
- Indicação de filtro ativo permanece visível para facilitar o retorno ao dia atual.

## Custos e ROI
- Custos gerais são rateados proporcionalmente ao faturamento; se todo mundo estiver zerado, o valor é dividido igualmente entre os bots ativos.
- Custos por bot são somados ao rateio e exibidos no ranking.
- ROI é exibido sempre que houver custo (mesmo negativo): sem vendas, por exemplo, o painel mostra `-100%`.
- Atualizações ilimitadas no dia atual suportadas; cada registro recalcula o ROI instantaneamente.

## Segurança e limites
- Callbacks assinados com HMAC + TTL (5 min) amarrados ao usuário.
- Rate limit de 10 ações / 30s por admin para evitar abuso.
- Entradas de texto validadas (`R$` e datas), erros retornam instruções claras.

## Operação interna
- Métricas consolidadas diretamente a partir de `pix_transactions`, `start_events`, `phase_transition_events` e `daily_cost_entries`.
- Eventos `/start` registrados no processamento padrão de bots secundários.
- Transições de fase registradas no fluxo da IA (quando detectado trigger).
- Consultas SQL otimizadas com índices (owner, bot, dia, hora).

## Testes e qualidade
- `tests/test_stats_parser.py`, `tests/test_stats_roi.py`, `tests/test_stats_service.py` cobrem parsing, ROI e pipeline principal.
- Ferramentas executadas: `black`, `isort`, `flake8` (módulos novos), `bandit`, `mypy` (com observação sobre alertas herdados).
