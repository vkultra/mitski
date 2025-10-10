# Importação e Exportação de Prompts

Este fluxo permite salvar e restaurar prompts longos do comportamento geral, das fases de IA e da fase de upsell em arquivos `.txt`.

## Onde encontrar os botões

- **Comportamento Geral**: menu IA → selecionar bot → *Comportamento Geral* → botões `⬆️ Enviar .txt` e `⬇️ Baixar .txt`.
- **Fases da IA**: menu IA → *Gerenciar Fases* → selecionar fase → botões `⬆️ Enviar .txt` e `⬇️ Baixar .txt`.
- **Fase do Upsell**: menu Upsell → selecionar upsell → *Fase* → botões `⬆️ Enviar .txt` e `⬇️ Baixar .txt`.

## Baixar

1. Clique em `⬇️ Baixar .txt`.
2. O bot envia um arquivo `.txt` com o conteúdo atual do prompt.
3. O preview na tela continua curto para evitar limites de 4096 caracteres do Telegram.

## Enviar

1. Clique em `⬆️ Enviar .txt`.
2. Envie o arquivo `.txt` como **documento** (ícone de clipe de papel → Arquivo).
3. O bot confirma o upload com a contagem de caracteres.

> **Limites**
> - Arquivos até **64 KB**.
> - Texto convertido para UTF-8. Caso use outro encoding, utilize ANSI/Latin-1.
> - Prompts maiores que 4096 caracteres devem ser enviados via `.txt` para evitar erros do Telegram.

## Boas práticas

- Versões do prompt podem ser versionadas em git (commit do `.txt` baixado).
- Revise o preview antes de baixar para garantir que está enviando o prompt correto.
- Para restaurar rapidamente um ambiente, basta reaplicar os arquivos `.txt` após registrar o bot.
