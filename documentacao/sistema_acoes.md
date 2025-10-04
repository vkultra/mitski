# Sistema de Ações para IA

## Visão Geral

O Sistema de Ações permite configurar respostas personalizadas que a IA pode acionar quando menciona termos específicos. Cada ação é composta por blocos de conteúdo (texto, mídia, efeitos) que são enviados quando o gatilho é detectado.

## Características Principais

### 1. Gatilhos Baseados em Nome
- O **nome da ação É o gatilho**
- Quando a IA menciona o nome, a ação é acionada
- Detecção case-insensitive
- Substituição inteligente de mensagem

### 2. Sistema de Blocos
- Cada ação pode ter múltiplos blocos
- Suporte para texto, mídia e efeitos
- Configuração individual por bloco:
  - **Texto/Legenda**: Conteúdo da mensagem
  - **Mídia**: Foto, vídeo, áudio, documento, GIF
  - **Efeitos**: Delay e auto-delete
- Streaming de mídia entre bots

### 3. Rastreamento de Uso (Opcional)
- Toggle "Rastrear Uso" por ação
- Quando ativo, adiciona status ao prompt da IA:
  - **INACTIVE**: Ação ainda não foi usada na conversa
  - **ACTIVATED**: Ação já foi acionada pelo menos uma vez
- Status isolado por usuário e sessão
- Nova conversa reseta todos os status

## Arquitetura

### Banco de Dados

```sql
-- Tabela principal de ações
ai_actions:
  - id
  - bot_id (FK)
  - action_name (único por bot, usado como gatilho)
  - track_usage (boolean)
  - is_active
  - created_at
  - updated_at

-- Blocos de conteúdo
ai_action_blocks:
  - id
  - action_id (FK)
  - order
  - text
  - media_file_id
  - media_type
  - delay_seconds
  - auto_delete_seconds
  - created_at
  - updated_at

-- Rastreamento de status por usuário
user_action_status:
  - id
  - bot_id (FK)
  - user_telegram_id
  - action_id (FK)
  - status (INACTIVE/ACTIVATED)
  - last_triggered_at
  - created_at
  - updated_at
```

### Serviços

#### ActionDetectorService
- Detecta gatilhos nas mensagens da IA
- Determina se deve substituir mensagem completa
- Busca todas as ações ativas do bot

#### ActionSenderService
- Envia blocos de ação aos usuários
- Aplica efeitos (delay, auto-delete)
- Gerencia cache de mídia entre bots

#### ActionService
- Coordena detecção e envio
- Gerencia status de rastreamento
- Valida criação de ações

## Fluxo de Funcionamento

### 1. Configuração (Admin)

1. Admin acessa menu **IA → Ações**
2. Clica em **➕ Adicionar Ação**
3. Define o nome (que será o gatilho)
4. Configura blocos:
   - Adiciona texto/legenda
   - Upload de mídia (opcional)
   - Configura efeitos (opcional)
5. Ativa/desativa rastreamento
6. Salva ação

### 2. Processamento (Runtime)

1. **Antes da IA processar**:
   - Sistema busca ações com `track_usage=true`
   - Adiciona status ao system prompt:
   ```
   Status das ações disponíveis:
   - promocao: INACTIVE
   - contato: ACTIVATED
   - horarios: INACTIVE
   ```

2. **Após resposta da IA**:
   - Detecta se algum nome de ação está na mensagem
   - Se detectado:
     - Atualiza status para ACTIVATED (se rastreado)
     - Decide se substitui ou adiciona conteúdo
     - Envia blocos da ação

### 3. Substituição vs Adição

**Substituição Completa** quando:
- Mensagem é APENAS o nome da ação
- Nome ocupa >70% da mensagem (<50 chars)

**Adição Após Mensagem** quando:
- Nome é parte de uma mensagem maior
- Contexto adicional é importante

## Interface do Usuário

### Menu Principal de Ações
```
🎬 Ações Configuradas

➕ Adicionar Ação
━━━━━━━━━━━━━━━
[promocao 📊] [contato] [horarios 📊]
[suporte] [catalogo 📊] [pagamento]
━━━━━━━━━━━━━━━
🔙 Voltar

📊 = Rastreamento ativo
```

### Menu de Edição de Ação
```
⚡ Ação: promocao
📊 Rastreamento: ATIVO

Blocos:
1️⃣ [Efeitos] [Mídia] [Texto] [❌]
2️⃣ [Efeitos] [Mídia] [Texto] [❌]

[➕ Criar Bloco]
[👀 Pré-visualizar]
[Rastrear Uso: ✅]
[🗑️ Deletar] [🔙 Voltar]
```

## Exemplos de Uso

### Exemplo 1: Ação de Promoção
**Nome**: promocao
**Rastreamento**: Ativo
**Blocos**:
1. Texto: "🎉 PROMOÇÃO ESPECIAL!"
2. Foto + Legenda: "50% OFF hoje!"
3. Texto com auto-delete: "Oferta válida por 1h"

**Conversa**:
```
Usuário: Tem alguma oferta hoje?
IA: Sim! Temos uma promocao especial para você.
[Sistema detecta "promocao" e envia os 3 blocos]
```

### Exemplo 2: Ação de Contato
**Nome**: contato
**Rastreamento**: Desativo
**Blocos**:
1. Texto: "📞 Entre em contato:"
2. Documento: vCard com informações

**Conversa**:
```
Usuário: Como falo com vocês?
IA: contato
[Sistema substitui mensagem pelos blocos]
```

## Callbacks e Rotas

### Callbacks de Menu
- `action_menu:{bot_id}` - Menu principal
- `action_add:{bot_id}` - Adicionar ação
- `action_edit:{action_id}` - Editar ação
- `action_delete:{action_id}` - Deletar ação
- `action_preview:{action_id}` - Preview

### Callbacks de Blocos
- `action_block_add:{action_id}` - Criar bloco
- `action_block_text:{block_id}` - Editar texto
- `action_block_media:{block_id}` - Editar mídia
- `action_block_effects:{block_id}` - Configurar efeitos
- `action_block_delete:{block_id}` - Deletar bloco

### Estados de Conversação
- `awaiting_action_name` - Aguardando nome da ação
- `awaiting_action_block_text` - Aguardando texto do bloco
- `awaiting_action_block_media` - Aguardando mídia
- `awaiting_action_block_delay` - Aguardando delay
- `awaiting_action_block_autodel` - Aguardando auto-delete

## Considerações Técnicas

### Performance
- Cache de file_ids de mídia por bot
- Índices únicos em (bot_id, action_name)
- Busca otimizada de ações ativas

### Segurança
- Validação de nomes (2-128 chars)
- Caracteres especiais bloqueados: `/\<>|`
- Permissões verificadas em todos os handlers

### Limites
- Nome da ação: 128 caracteres
- Texto do bloco: 4096 caracteres
- Delay: 0-300 segundos
- Auto-delete: 0-300 segundos

## Integração com Sistema

### conversation.py
- Adiciona status de ações ao prompt
- Detecta e processa ações após resposta

### ai_tasks.py
- Remove sufixos de detecção
- Envia blocos após mensagem original

### tasks.py
- Processa callbacks de menu
- Gerencia estados de conversação
- Upload de mídia para blocos

## Migração

```bash
# Aplicar migration
alembic upgrade head

# Reverter se necessário
alembic downgrade -1
```

## Testes Recomendados

1. **Criar ação simples**
   - Nome: teste
   - 1 bloco de texto
   - Verificar acionamento

2. **Ação com mídia**
   - Upload foto/vídeo
   - Verificar streaming entre bots

3. **Rastreamento**
   - Ativar rastreamento
   - Verificar status no prompt
   - Confirmar mudança INACTIVE → ACTIVATED

4. **Efeitos**
   - Configurar delay 5s
   - Configurar auto-delete 10s
   - Verificar funcionamento

5. **Múltiplos usuários**
   - Verificar isolamento de status
   - Testar reset em nova conversa
