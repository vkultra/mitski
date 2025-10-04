# Sistema de Ofertas - Documentação

## Visão Geral

O Sistema de Ofertas permite que administradores criem ofertas de produtos/serviços que são automaticamente detectadas e substituídas por pitches de vendas quando mencionadas pela IA durante conversas com usuários.

## Como Funciona

### Fluxo Principal

1. **Criação da Oferta**
   - Admin acessa menu `Configuração de IA → Ofertas`
   - Define nome único da oferta (ex: "Curso Premium")
   - Define valor (ex: "R$ 97,00")
   - Configura pitch de vendas com múltiplos blocos

2. **Configuração do Pitch**
   - Cada bloco representa uma mensagem separada
   - Blocos podem conter:
     - Texto/legenda
     - Mídia (foto, vídeo, áudio, gif, documento)
     - Efeitos (delay e auto-exclusão)

3. **Detecção Automática**
   - IA responde ao usuário normalmente
   - Sistema detecta nome da oferta na resposta (case-insensitive)
   - Se detectado, substitui mensagem pelo pitch completo

4. **Envio do Pitch**
   - Blocos enviados em sequência
   - Delays aplicados entre mensagens
   - Auto-exclusão executada após tempo configurado
   - File IDs de mídia reutilizados (economia de banda)

## Arquitetura

### Estrutura de Dados

```sql
offers
├── id (PK)
├── bot_id (FK)
├── name (unique per bot)
├── value
├── is_active
└── timestamps

offer_pitch_blocks
├── id (PK)
├── offer_id (FK)
├── order (sequência)
├── text
├── media_file_id
├── media_type
├── delay_seconds
├── auto_delete_seconds
└── timestamps

offer_deliverables (futuro)
├── id (PK)
├── offer_id (FK)
├── content
├── type
└── timestamps
```

### Componentes

#### 1. **Models** (`database/models.py`)
- `Offer`: Dados básicos da oferta
- `OfferPitchBlock`: Blocos de mensagem do pitch
- `OfferDeliverable`: Conteúdo entregável (preparado para futuro)

#### 2. **Repositories** (`database/repos.py`)
- `OfferRepository`: CRUD de ofertas
- `OfferPitchRepository`: Gerenciamento de blocos

#### 3. **Handlers** (`handlers/offer_handlers.py`)
- Interface de usuário via Telegram
- Processamento de callbacks e inputs
- Validações de entrada

#### 4. **Services** (`services/offers/`)
- `offer_detector.py`: Detecta ofertas em mensagens
- `pitch_sender.py`: Envia pitch formatado
- `offer_service.py`: Coordena operações

#### 5. **Integração com IA** (`services/ai/conversation.py`)
- Intercepta respostas da IA
- Aplica substituição quando necessário

## Configuração de Ofertas

### Criar Oferta

1. Acesse: `IA → Selecionar Bot → 💰 Ofertas`
2. Clique em `➕ Criar Oferta`
3. Digite o nome (mínimo 2 caracteres)
4. Digite o valor (formato: R$ XX,XX)

### Configurar Pitch

1. Após criar, você verá o menu do pitch
2. Clique em `➕ Criar Bloco` para adicionar mensagens
3. Para cada bloco, configure:
   - **Texto/Legenda**: Conteúdo da mensagem
   - **Mídia**: Anexe foto, vídeo, áudio, etc
   - **Efeitos**:
     - Delay: 0-300 segundos antes de enviar
     - Auto-deletar: 0-3600 segundos após envio

### Exemplo de Pitch

```
Bloco 1: [Foto] "🎯 Oferta Especial!"
         Delay: 0s, Auto-del: 0s

Bloco 2: [Texto] "Por apenas R$ 97,00..."
         Delay: 2s, Auto-del: 0s

Bloco 3: [Vídeo] "Veja os benefícios"
         Delay: 3s, Auto-del: 30s
```

## Detecção de Ofertas

### Como a Detecção Funciona

1. **Case-Insensitive**: Detecta variações de maiúsculas/minúsculas
   - "curso premium" = "Curso Premium" = "CURSO PREMIUM"

2. **Detecção Parcial**: Encontra oferta dentro de texto
   - "Confira nosso **Curso Premium**" ✓
   - "O **curso premium** está disponível" ✓

3. **Substituição Completa**: Quando IA envia apenas o nome
   - IA: "Curso Premium" → Substitui por pitch
   - IA: "Confira o Curso Premium" → Mantém mensagem + pitch

### Priorização

- Primeira oferta detectada é processada
- Múltiplas ofertas na mesma mensagem: apenas primeira é ativada

## Melhores Práticas

### Nomes de Ofertas

✅ **Recomendado:**
- Nomes únicos e específicos
- 2-50 caracteres
- Fácil de lembrar

❌ **Evitar:**
- Nomes genéricos ("produto", "serviço")
- Caracteres especiais excessivos
- Nomes muito longos

### Configuração de Pitch

✅ **Recomendado:**
- 3-7 blocos por pitch
- Delays de 1-5 segundos
- Mídia otimizada (<5MB)
- Texto conciso e direto

❌ **Evitar:**
- Mais de 10 blocos
- Delays muito longos (>10s)
- Mídia pesada
- Textos muito longos

### Auto-Exclusão

**Use quando:**
- Ofertas temporárias/urgentes
- Conteúdo sensível ao tempo
- Manter chat limpo

**Configure:**
- 30-60s para urgência
- 5-10min para ofertas normais
- 0 para manter permanente

## Teste do Sistema

### Teste Manual

1. Crie oferta teste: "Teste123"
2. Configure pitch simples (1-2 blocos)
3. Inicie conversa com bot
4. IA responde: "Teste123"
5. Verifique substituição pelo pitch

### Teste Automatizado

```bash
# Executar testes
python -m pytest tests/test_offers.py -v

# Testes incluem:
- Detecção case-insensitive
- Detecção parcial
- Envio de blocos
- Aplicação de delays
- Validações
```

## Troubleshooting

### Oferta Não Detectada

**Possíveis causas:**
1. Oferta inativa (`is_active = False`)
2. Nome escrito incorretamente
3. Bot sem IA habilitada

**Solução:**
- Verificar status da oferta
- Conferir nome exato
- Habilitar IA no bot

### Pitch Não Enviado

**Possíveis causas:**
1. Nenhum bloco criado
2. Erro no file_id da mídia
3. Token do bot inválido

**Solução:**
- Criar pelo menos 1 bloco
- Re-enviar mídia
- Verificar token do bot

### Delays Não Funcionando

**Possíveis causas:**
1. Preview mode ativo
2. Valor de delay = 0

**Solução:**
- Testar em produção (não preview)
- Configurar delay > 0

## Performance

### Otimizações Implementadas

1. **Cache de Ofertas**: Reduz consultas ao banco
2. **Reutilização de file_id**: Economia de banda
3. **Detecção Eficiente**: Regex compilado
4. **Envio Assíncrono**: Não bloqueia conversa

### Limites Recomendados

- Máximo 50 ofertas por bot
- Máximo 20 blocos por pitch
- Mídia até 20MB (limite Telegram)
- Delays totais < 60 segundos

## Segurança

### Validações

- Nome único por bot
- Valores sanitizados
- file_ids verificados
- Permissões de admin

### Proteções

- Soft delete de ofertas
- Rate limiting no envio
- Logs de todas operações
- Tokens criptografados

## Roadmap Futuro

### Próximas Features

1. **Analytics de Ofertas**
   - Quantas vezes foi acionada
   - Taxa de conversão
   - Tempo de visualização

2. **Entregáveis Automáticos**
   - Envio de links após compra
   - Códigos de desconto
   - Arquivos digitais

3. **A/B Testing**
   - Múltiplos pitches por oferta
   - Rotação automática
   - Métricas comparativas

4. **Gatilhos Avançados**
   - Por horário
   - Por localização
   - Por comportamento

## Suporte

Para problemas ou sugestões:
1. Verificar logs em `logs/offers.log`
2. Consultar testes em `tests/test_offers.py`
3. Reportar issues no repositório

---

**Versão:** 1.0.0
**Última Atualização:** Janeiro 2025
