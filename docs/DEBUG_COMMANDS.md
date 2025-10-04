# Comandos de Debug - Sistema de Ações e Ofertas

## Visão Geral

Os comandos de debug permitem testar o funcionamento do sistema de ações, ofertas e pagamentos sem necessidade de realizar transações reais. Eles simulam os cenários reais para validar se os conteúdos estão sendo entregues corretamente.

## Arquitetura Implementada

### Estrutura Modular (< 280 linhas por arquivo)

```
handlers/
├── debug_commands.py         # Implementação dos comandos (278 linhas)
└── debug_commands_router.py  # Roteamento e identificação (165 linhas)

workers/
└── tasks.py                  # Integração com processamento de mensagens
```

### Fluxo de Processamento

1. **Recepção**: Mensagem chega no bot secundário via webhook
2. **Roteamento**: `workers/tasks.py` detecta comando iniciado com `/`
3. **Validação**: `debug_commands_router.py` verifica se é comando de debug
4. **Execução**: `debug_commands.py` executa a lógica específica
5. **Resposta**: Conteúdo é enviado ao usuário via Telegram API

## Comandos Disponíveis

### 1. `/debug_help` ou `/debug`

Lista todos os comandos de debug disponíveis para o bot.

**Uso:**
```
/debug_help
```

**Resposta:**
- Lista de comandos fixos
- Ações personalizadas cadastradas
- Ofertas disponíveis
- Instruções de uso

### 2. `/vendaaprovada` ou `/venda_aprovada`

Simula um pagamento PIX aprovado e entrega o conteúdo da primeira oferta disponível.

**Uso:**
```
/vendaaprovada
```

**Comportamento:**
1. Busca primeira oferta ativa do bot
2. Verifica se há conteúdo de entrega configurado
3. Simula pagamento aprovado
4. Entrega todos os blocos de conteúdo
5. Envia confirmação de entrega

**Validações:**
- Oferta deve existir e estar ativa
- Deve ter blocos de entregáveis configurados

### 3. `/{nome_da_acao}`

Dispara uma ação personalizada cadastrada no sistema.

**Uso:**
```
/termo_de_uso
/bonus_especial
/conteudo_vip
```

**Comportamento:**
1. Busca ação pelo nome exato
2. Verifica se está ativa
3. Envia todos os blocos configurados
4. Confirma execução

**Validações:**
- Nome deve corresponder exatamente ao cadastrado
- Ação deve estar ativa

### 4. `/{nome_da_oferta}`

Envia o pitch completo de uma oferta específica.

**Uso:**
```
/curso_python
/mentoria_vip
/ebook_gratis
```

**Comportamento:**
1. Busca oferta pelo nome exato
2. Verifica se está ativa
3. Envia todos os blocos do pitch
4. Substitui variáveis dinâmicas ({pix}, {nome}, etc)
5. Confirma envio

**Validações:**
- Nome deve corresponder exatamente ao cadastrado
- Oferta deve estar ativa

## Implementação Técnica

### Classe DebugCommandHandler

```python
class DebugCommandHandler:
    @staticmethod
    async def handle_venda_aprovada(bot_id, chat_id, user_telegram_id, bot_token, offer_name=None)
    @staticmethod
    async def handle_trigger_action(bot_id, chat_id, action_name, bot_token)
    @staticmethod
    async def handle_offer_pitch(bot_id, chat_id, user_telegram_id, offer_name, bot_token)
```

### Classe DebugCommandRouter

```python
class DebugCommandRouter:
    @staticmethod
    async def is_debug_command(text: str) -> bool
    @staticmethod
    async def route_debug_command(bot_id, chat_id, user_telegram_id, text, bot_token)
    @staticmethod
    async def list_available_debug_commands(bot_id: int) -> dict
```

### Integração com Workers

```python
# workers/tasks.py
if text and text.startswith("/"):
    debug_result = asyncio.run(
        DebugCommandRouter.route_debug_command(
            bot_id=bot_id,
            chat_id=chat_id,
            user_telegram_id=user_id,
            text=text,
            bot_token=decrypt(bot.token)
        )
    )
    if debug_result:
        return  # Comando processado com sucesso
```

## Logs e Monitoramento

Todos os comandos de debug geram logs estruturados:

```python
logger.info(
    "Debug command processed",
    extra={
        "bot_id": bot_id,
        "command": text,
        "result": debug_result
    }
)
```

## Segurança

1. **Validação de Token**: Usa token criptografado do bot
2. **Verificação de Propriedade**: Apenas executa para bots válidos
3. **Rate Limiting**: Respeita limites configurados
4. **Logs Auditáveis**: Todos comandos são registrados

## Cenários de Teste

### Teste 1: Venda Aprovada
```
1. Cadastrar oferta com blocos de entrega
2. Executar /vendaaprovada
3. Verificar se todos os blocos foram entregues
4. Validar ordem e conteúdo
```

### Teste 2: Gatilho de Ação
```
1. Cadastrar ação "bonus_especial"
2. Executar /bonus_especial
3. Verificar se blocos foram enviados
4. Validar rastreamento se configurado
```

### Teste 3: Pitch de Oferta
```
1. Cadastrar oferta "curso_python"
2. Executar /curso_python
3. Verificar pitch completo
4. Validar substituição de variáveis
```

## Mensagens de Feedback

### Sucesso
- ✅ Simulando pagamento aprovado
- ✅ Ação executada!
- ✅ Pitch enviado!
- ✅ Entrega concluída!

### Erros
- ⚠️ Nenhuma oferta encontrada
- ⚠️ Ação não encontrada
- ⚠️ Oferta desativada
- ❌ Erro ao processar comando

## Manutenção

### Adicionar Novo Comando

1. Implementar método em `debug_commands.py`
2. Adicionar roteamento em `debug_commands_router.py`
3. Atualizar lista em `/debug_help`
4. Adicionar documentação

### Debugging

Para debug detalhado, ativar logs em nível DEBUG:

```python
logger.setLevel(logging.DEBUG)
```

## Performance

- Comandos processados assincronamente
- Delay de 0.5s entre envio de blocos
- Suporta múltiplos usuários simultâneos
- Cache de mídia para otimização

## Limitações

1. Comandos devem ser digitados exatamente
2. Não há autocompletar
3. Case-sensitive para nomes de ações/ofertas
4. Máximo 50 blocos por comando
