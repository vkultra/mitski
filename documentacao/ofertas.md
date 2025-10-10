# Sistema de Ofertas

## Visão Geral

O sistema de ofertas permite que administradores configurem produtos/serviços que podem ser oferecidos automaticamente pela IA durante conversas com usuários nos bots secundários.

## Arquitetura

### Modelo de Dados

#### Offer (Oferta)
- `id`: Identificador único
- `bot_id`: Bot onde a oferta foi criada
- `name`: Nome da oferta (usado pela IA para detecção)
- `value`: Valor formatado (ex: "R$ 97,00")
- `manual_verification_trigger`: Termo que aciona verificação manual
- `is_active`: Status da oferta

#### Bot.associated_offer_id
- Campo FK opcional na tabela `bots`
- **Constraint**: Um bot pode ter apenas UMA oferta associada
- **Flexibilidade**: Uma oferta pode ser associada a múltiplos bots
- Quando `NULL`, o bot não tem oferta associada

## Componentes da Oferta

### 1. Pitch da Oferta

Sistema de blocos de mensagens apresentadas quando a IA menciona o nome da oferta.

**Características**:
- Detecção case-insensitive do nome da oferta na resposta da IA
- Blocos enviados em sequência com delays configuráveis
- Suporte a mídia (fotos, vídeos, áudio, documentos, GIFs)
- Auto-delete configurável por bloco
- Substituição automática da mensagem da IA pelo pitch

**Exemplo de fluxo**:
```
Usuário: "Me conte sobre o curso"
IA: "Temos o Curso Avançado de Python que ensina..."
Sistema detecta "Curso Avançado" → Envia pitch com 5 blocos
```

### 2. Entregável (Blocos)

Conteúdo entregue ao usuário após confirmação de pagamento.

**Características**:
- Mesmo sistema de blocos do pitch
- Suporte a mídia e efeitos (delay, auto-delete)
- Enviado automaticamente quando pagamento é confirmado
- Pode incluir links, arquivos, credenciais, etc.

**Fluxo de entrega**:
```
Pagamento PIX confirmado → Sistema envia blocos do entregável → Marca transação como entregue
```

### 3. Verificação Manual

Sistema ativado por termo específico quando a IA não encontra pagamento automaticamente.

**Componentes**:
- **Termo de Ativação**: Palavra/frase que aciona a verificação (ex: "verificar pagamento")
- **Blocos de Verificação**: Mensagens enviadas quando pagamento não é encontrado
- **Detecção no Fluxo da IA**: Sistema monitora respostas da IA

**Fluxo de verificação manual**:
```
IA envia: "Já enviou o pagamento? Digite 'verificar pagamento' para eu conferir"
Sistema detecta termo "verificar pagamento"
  → Busca transações PIX pendentes (últimos 15 min)
  → Se encontrado e pago: Entrega conteúdo
  → Se não encontrado/pendente: Envia blocos de verificação manual
```

**Blocos de Verificação Manual**:
- Instruções sobre como enviar comprovante
- Opções de contato com suporte
- Informações sobre tempo de verificação

## Associação Bot-Oferta

### Modelo de Associação

**Regras**:
- **1 Bot = 1 Oferta** (máximo)
- **1 Oferta = N Bots** (uma oferta pode ser usada em vários bots)

**Implementação**:
- Campo `Bot.associated_offer_id` (FK para `offers.id`)
- ON DELETE SET NULL (se oferta for deletada, bot.associated_offer_id vira NULL)
- Index em `associated_offer_id` para queries rápidas

### Interface de Associação

No menu de ofertas, cada oferta tem dois botões:
```
[✅ Nome da Oferta (R$ 97,00)]  [🔗 Associado]
[   Oferta 2 (R$ 47,00)      ]  [➕ Associar]
```

**Comportamento**:
- **Botão do nome**: Vai para menu de edição da oferta
- **"➕ Associar"**: Associa oferta ao bot atual (substitui associação anterior se existir)
- **"🔗 Associado"**: Desassocia oferta do bot

## Fluxo Completo de Venda

### 1. Detecção de Oferta
```python
# services/offers/offer_service.py
await OfferService.process_ai_message_for_offers(
    bot_id=bot_id,
    chat_id=user_telegram_id,
    ai_message=answer,
    bot_token=bot_token
)
```

- Sistema busca nome da oferta na resposta da IA (case-insensitive)
- Se detectado, envia pitch e gera PIX

### 2. Geração de Pagamento
```python
# services/gateway/pix_generator.py
pix_data = await PixGenerator.create_pix_payment(
    bot_id=bot_id,
    user_telegram_id=user_telegram_id,
    offer_id=offer_id,
    admin_id=admin_id
)
```

- Gera chave PIX via PushinPay API
- Salva transação no banco (status: 'created')
- Envia QR Code ao usuário

### 3. Verificação Automática
```python
# Celery task executada a cada minuto
@celery_app.task
def verify_pending_pix_payments():
    # Busca transações pendentes
    # Verifica status na API
    # Se pago: entrega conteúdo
```

### 4. Entrega de Conteúdo
```python
# services/gateway/payment_verifier.py
await PaymentVerifier.deliver_content(transaction_id)
```

- Busca blocos do entregável
- Envia cada bloco com delays
- Marca transação como entregue
- Atualiza status para 'delivered'

### 5. Verificação Manual (Opcional)
```python
# services/ai/conversation.py
await AIConversationService._check_manual_verification_trigger(
    bot_id=bot_id,
    chat_id=chat_id,
    ai_message=answer,
    bot_token=bot_token
)
```

- Detecta termo de verificação manual na resposta da IA
- Busca transações pendentes dos últimos 15 minutos
- Se não encontrou pagamento: envia blocos de verificação manual

## Menu de Edição de Ofertas

### Estrutura do Menu

```
✏️ Editando: Nome da Oferta (R$ 97,00)

Configure sua oferta:

✅ Valor definido
✅ Pitch configurado (3 blocos)
✅ Entregável configurado (2 blocos)
✅ Verificação manual configurada (Termo: verificar pagamento, 1 blocos)

[💰 Valor (R$ 97,00)]
[📋 Pitch da Oferta]  [📦 Entregável]
[🔍 Verificação Manual]
[🔙 Voltar]  [💾 SALVAR]
```

### Seções Configuráveis

#### 1. Valor
- Texto livre (ex: "R$ 97,00", "US$ 29.90", "€ 19,99")
- Exibido nos menus e informações da oferta

#### 2. Pitch da Oferta
**Estrutura**:
```
[1️⃣] [Efeitos] [Mídia] [Texto/Legenda] [❌]
[2️⃣] [Efeitos] [Mídia] [Texto/Legenda] [❌]
[➕ Criar Bloco]
[👀 Pré-visualizar]
```

**Pré-visualização**:
- Envia blocos reais ao administrador
- Aplica delays e efeitos configurados
- Retorna ao menu após envio

#### 3. Entregável (Blocos)
- Mesma estrutura do Pitch
- Blocos enviados após confirmação de pagamento

#### 4. Verificação Manual
**Estrutura**:
```
[🔑 verificar pagamento]    ← Termo configurado (ou "Configurar Termo")
[1️⃣] [Efeitos] [Mídia] [Texto/Legenda] [❌]
[2️⃣] [Efeitos] [Mídia] [Texto/Legenda] [❌]
[➕ Criar Bloco]
[👀 Pré-visualizar]
```

**Ordem dos blocos**:
- Termo de ativação no topo
- Blocos listados abaixo
- Botão "Criar Bloco" sempre acima de "Pré-visualizar"

### 4. Descontos negociados

Permite responder automaticamente quando a IA fecha um valor diferente do preço padrão.

**Fluxo**:
1. Configure o `Termo` (ex.: `fechoupack`).
2. Crie blocos personalizados (mesmo editor de Pitch/Entregável) e inclua `{pix}` onde a chave PIX deve aparecer.
3. Quando a IA enviar `{termo}{valor}` — case-insensitive e mesmo colado em outras palavras, como `testefechoupack15` ou `FECHOUPACK 19,90` — o sistema:
   - Gera um PIX com o valor negociado (aceita R$ 0,50 até R$ 10.000,00).
   - Substitui a mensagem da IA pelos blocos de Descontos.
   - Agenda a verificação automática de pagamento.
   - Entrega o mesmo entregável da oferta assim que o pagamento for confirmado (automático ou manual).

**Boas práticas**:
- O status do botão fica ✅ quando há termo configurado **e** pelo menos um bloco criado.
- Em pré-visualizações, `{pix}` é substituído por `PREVIEW_PIX_CODE` para evitar gerar transações reais.
- Se nenhum bloco contiver `{pix}`, a mensagem será enviada sem a chave (o administrador deve lembrar-se de incluí-la).
- As transações de descontos aparecem normalmente na verificação automática e manual, pois ficam vinculadas ao `offer_id` original.
- Para testes rápidos, o administrador do bot pode enviar `/{termo}{valor}` (ex.: `/fechoupack15`) no bot secundário; o fluxo gera uma chave PIX real e envia os blocos de desconto como se fosse a IA.

## Configuração de Blocos

### Propriedades Comuns

Todos os blocos (Pitch, Entregável, Verificação Manual) compartilham:

1. **Texto/Legenda**: Mensagem de texto ou legenda da mídia
2. **Mídia**: Foto, vídeo, áudio, documento ou GIF
3. **Delay**: Espera em segundos antes de enviar (0-300s)
4. **Auto-delete**: Tempo para deletar mensagem após envio (0-3600s)

### Interface de Configuração

```
Bloco #1 - Pitch

[💬 Texto/Legenda]
[📎 Mídia]
[⏱️ Efeitos]
[❌ Deletar Bloco]
[🔙 Voltar]
```

**Efeitos**:
```
⏱️ Efeitos do Bloco

Delay: 2s
Auto-deletar: 30s

[⏰ Delay]
[🗑️ Auto-deletar]
[🔙 Voltar]
```

## Mensagem de Oferta Salva

Quando o administrador clica em "SALVAR":

```
✅ Oferta Salva com Sucesso!

📋 Nome: Curso Avançado de Python (R$ 97,00)
📦 Pitch: 3 blocos
📦 Entregável: 2 blocos
🔍 Verificação manual ativa (Termo: verificar pagamento, 1 blocos)

Quando a IA mencionar Curso Avançado de Python (case-insensitive),
o pitch será automaticamente enviado ao usuário.

[🔙 Voltar ao Menu de Ofertas]
```

## Integração com IA

### Detecção de Ofertas
```python
# services/offers/offer_service.py
detected_offer = await OfferService.detect_offer_in_message(
    bot_id=bot_id,
    message=ai_response
)
```

- Busca ofertas ativas do bot
- Verifica se nome da oferta aparece na mensagem (case-insensitive)
- Se múltiplas ofertas, prioriza primeira encontrada

### Substituição de Mensagem

Quando oferta é detectada:
```python
if offer_result and offer_result.get("replaced_message"):
    # Pitch foi enviado, não enviar mensagem da IA
    return None
```

A mensagem da IA é substituída pelo pitch completo.

### Verificação Manual na IA

```python
# services/ai/conversation.py (linha 240-260)
manual_verify_result = await AIConversationService._check_manual_verification_trigger(
    bot_id=bot_id,
    chat_id=user_telegram_id,
    ai_message=answer,
    bot_token=bot_token
)
```

**Lógica**:
1. Escaneia resposta da IA por termos de verificação manual
2. Busca ofertas com termo configurado
3. Se termo encontrado:
   - Busca transações PIX pendentes (últimos 15 min)
   - Verifica status do pagamento
   - Entrega conteúdo OU envia blocos de verificação manual

## Repositórios e Métodos

### BotRepository
```python
await BotRepository.associate_offer(bot_id, offer_id)
await BotRepository.dissociate_offer(bot_id)
await BotRepository.get_associated_offer_id(bot_id)
```

### OfferRepository
```python
await OfferRepository.get_offers_by_bot(bot_id, active_only=True)
await OfferRepository.update_offer(offer_id, **kwargs)
await OfferRepository.delete_offer(offer_id)  # Soft delete
```

### OfferPitchRepository
```python
await OfferPitchRepository.create_block(offer_id, order, text, media_file_id, ...)
await OfferPitchRepository.get_blocks_by_offer(offer_id)
await OfferPitchRepository.delete_block(block_id)  # Reordena blocos restantes
```

### OfferDeliverableBlockRepository
```python
await OfferDeliverableBlockRepository.create_block(offer_id, order, ...)
await OfferDeliverableBlockRepository.get_blocks_by_offer(offer_id)
```

### OfferManualVerificationBlockRepository
```python
await OfferManualVerificationBlockRepository.create_block(offer_id, order, ...)
await OfferManualVerificationBlockRepository.get_blocks_by_offer(offer_id)
```

## Rotas (workers/tasks.py)

### Menu e Navegação
- `offer_menu:{bot_id}` - Menu principal com todas as ofertas
- `offer_create:{bot_id}` - Criar nova oferta
- `offer_edit:{offer_id}` - Menu de edição
- `offer_save_final:{offer_id}` - Salvar oferta

### Associação
- `offer_associate:{bot_id}:{offer_id}` - Associar oferta ao bot
- `offer_dissociate:{bot_id}:{offer_id}` - Desassociar oferta

### Pitch
- `offer_pitch:{offer_id}` - Menu do pitch
- `pitch_add:{offer_id}` - Criar bloco
- `pitch_preview:{offer_id}` - Pré-visualizar pitch
- `pitch_delete:{block_id}` - Deletar bloco

### Entregável
- `deliv_blocks:{offer_id}` - Menu de blocos
- `deliv_block_add:{offer_id}` - Criar bloco
- `deliv_block_preview:{offer_id}` - Pré-visualizar entregável

### Verificação Manual
- `manver_menu:{offer_id}` - Menu de verificação manual
- `manver_set_trigger:{offer_id}` - Configurar termo
- `manver_block_add:{offer_id}` - Criar bloco
- `manver_block_preview:{offer_id}` - Pré-visualizar blocos

## Estados Conversacionais

Estados usados para aguardar input do usuário:

- `awaiting_offer_name` - Aguardando nome da oferta
- `awaiting_offer_value_edit` - Aguardando valor da oferta
- `awaiting_pitch_block_text` - Aguardando texto do bloco do pitch
- `awaiting_deliv_block_text` - Aguardando texto do bloco entregável
- `awaiting_manver_trigger` - Aguardando termo de verificação manual
- `awaiting_manver_block_text` - Aguardando texto do bloco de verificação

## Exemplo Completo

### Configuração
1. Admin cria oferta "Curso Python Avançado" (R$ 497,00)
2. Configura pitch com 3 blocos (apresentação, benefícios, call-to-action)
3. Configura entregável com 2 blocos (acesso à plataforma, grupo VIP)
4. Configura verificação manual:
   - Termo: "verificar pagamento"
   - 1 bloco: "Envie print do comprovante ou aguarde até 1 hora"
5. Associa oferta ao Bot "Vendas"

### Fluxo de Venda
```
[Usuário] "Quero aprender Python"
[IA] "Perfeito! Temos o Curso Python Avançado que..."
[Sistema] Detecta "Curso Python Avançado"
[Sistema] Envia pitch (3 blocos com delays)
[Sistema] Gera PIX de R$ 497,00
[Sistema] Envia QR Code
[Usuário] Realiza pagamento
[Sistema] Verifica pagamento automaticamente (task Celery)
[Sistema] Detecta pagamento confirmado
[Sistema] Envia entregável (2 blocos)
[Sistema] Marca transação como entregue
```

### Fluxo com Verificação Manual
```
[Usuário] "Já paguei"
[IA] "Ótimo! Digite 'verificar pagamento' para eu conferir"
[Sistema] Detecta termo "verificar pagamento"
[Sistema] Busca transações pendentes
[Sistema] Não encontra pagamento confirmado
[Sistema] Envia bloco de verificação manual
[Usuário] Envia print do comprovante
[Admin] Verifica manualmente e aprova
```

## Boas Práticas

### Configuração de Ofertas
- Use nomes únicos e descritivos para ofertas
- Configure pelo menos 1 bloco no pitch
- Teste a pré-visualização antes de salvar
- Configure valores formatados claramente

### Pitch de Vendas
- Primeiro bloco: Apresentação do produto
- Blocos intermediários: Benefícios e detalhes
- Último bloco: Call-to-action com PIX

### Entregável
- Primeiro bloco: Instruções de acesso
- Blocos seguintes: Links, credenciais, arquivos
- Use auto-delete para informações sensíveis

### Verificação Manual
- Configure termo simples e claro
- Use blocos explicativos sobre o processo
- Inclua informações de contato alternativo

## Troubleshooting

### Oferta não está sendo detectada
- Verifique se oferta está ativa
- Verifique se oferta está associada ao bot
- Confira se nome está correto na resposta da IA (case-insensitive)

### PIX não está sendo gerado
- Verifique configuração do gateway no admin
- Verifique se bot tem gateway configurado
- Confira logs de erro em `core.telemetry`

### Entregável não está sendo enviado
- Verifique se transação foi marcada como paga
- Confira se blocos do entregável estão configurados
- Verifique task Celery de verificação automática

### Verificação manual não funciona
- Verifique se termo está configurado
- Confira se blocos de verificação estão criados
- Verifique se há transações pendentes nos últimos 15 minutos
