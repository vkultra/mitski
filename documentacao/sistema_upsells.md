# Sistema de Upsells

## 📋 Visão Geral

Sistema completo de upsell pós-pagamento com dois modos de operação:

- **Upsell #1 (Pré-salvo)**: Gatilho inteligente por IA - quando a IA menciona um termo específico
- **Upsells #2+**: Envio automático baseado em agendamento (dias/horas após último pagamento)

## 🎯 Objetivo

Permitir que administradores configurem anúncios adicionais de produtos/serviços que são enviados automaticamente aos usuários que já realizaram pelo menos um pagamento, maximizando oportunidades de venda.

## 🏗️ Arquitetura

### Banco de Dados

**6 Tabelas principais:**

1. **upsells**: Configuração principal de cada upsell
   - name, value, order, is_pre_saved, upsell_trigger

2. **upsell_announcement_blocks**: Blocos do anúncio
   - text, media, delay, auto_delete, order

3. **upsell_deliverable_blocks**: Blocos da entrega
   - text, media, delay, auto_delete, order

4. **upsell_phase_configs**: Prompt de fase específico do upsell
   - phase_prompt

5. **upsell_schedules**: Agendamento de envio
   - is_immediate, days_after, hours, minutes

6. **user_upsell_history**: Histórico de envios por usuário
   - sent_at, paid_at, transaction_id

### Serviços (services/upsell/)

1. **UpsellService**: Lógica principal e validação de completude
2. **TriggerDetector**: Detecta gatilhos na resposta da IA
3. **AnnouncementSender**: Envia blocos de anúncio
4. **DeliverableSender**: Envia blocos de entrega
5. **UpsellScheduler**: Gerencia agendamentos

### Workers (workers/upsell_tasks.py)

1. **activate_upsell_flow**: Ativa após primeiro pagamento
2. **send_upsell_announcement_triggered**: Envia quando IA menciona trigger
3. **check_pending_upsells**: Verifica agendados (task periódica)
4. **send_scheduled_upsell**: Envia upsell agendado
5. **process_upsell_payment**: Processa pagamento e entrega

## 🔄 Fluxos de Funcionamento

### Fluxo do Upsell #1 (Trigger por IA)

```
1. Usuário paga oferta principal
   ↓
2. Sistema detecta primeiro pagamento
   ↓
3. Verifica se upsell #1 está 100% configurado
   ↓
4. Troca prompt da IA IMEDIATAMENTE
   ↓
5. Cria registro em histórico (sent_at=NULL)
   ↓
6. IA conversa com novo comportamento
   ↓
7. IA menciona trigger (ex: "premium")
   ↓
8. Sistema detecta termo → envia anúncio
   ↓
9. Marca como enviado (sent_at=now)
   ↓
10. Usuário paga → entrega deliverable
   ↓
11. Agenda próximo upsell (#2)
```

### Fluxo dos Upsells #2+ (Agendados)

```
1. Usuário paga upsell anterior
   ↓
2. Sistema agenda próximo upsell
   ↓
3. Cria registro com sent_at=NULL
   ↓
4. Task periódica (5min) verifica prontos
   ↓
5. Quando chega o tempo configurado:
   - Troca prompt da IA
   - Envia anúncio automaticamente
   ↓
6. Marca como enviado
   ↓
7. Usuário paga → entrega deliverable
   ↓
8. Repete para próximo upsell
```

## ✅ Validação de Completude

Um upsell só é ativado se estiver 100% preenchido:

- ✅ **Anúncio**: >= 1 bloco configurado
- ✅ **Entrega**: >= 1 bloco configurado
- ✅ **Fase**: Prompt definido
- ✅ **Valor**: Preço configurado (ex: R$ 19,90)
- ✅ **Trigger** (apenas #1): Termo definido
- ✅ **Agendar** (apenas #2+): Tempo configurado

## 🔧 Integrações Implementadas

### 1. handlers/ai_handlers.py
- Botão "🔄 Recuperação" substituído por "💎 Upsell"
- Callback: `upsell_menu:{bot_id}`

### 2. services/gateway/payment_verifier.py
- Após entregar conteúdo, chama `activate_upsell_flow.delay()`

### 3. services/bot_registration.py
- Ao criar bot, cria automaticamente upsell #1 pré-salvo
- Nome: "Upsell Imediato"
- Agendamento: is_immediate=True

## 📝 O Que Foi Implementado

### ✅ Completo
- Modelos de banco de dados (6 tabelas)
- Migration completa com índices
- Repositórios (6 classes com todas as funções)
- Serviços (5 arquivos com lógica principal)
- Workers tasks (5 tasks Celery)
- Integrações críticas (payment_verifier, bot_registration, ai_handlers)

### ⚠️ Pendente
- **Handlers completos**: Menu de upsell, edição de blocos, etc.
- **Routing de callbacks** em workers/tasks.py
- **Detecção de trigger** em conversation.py
- **Troca de fase real** (atualmente apenas loga)
- **Celery Beat schedule** para check_pending_upsells
- **Testes automatizados**
- **Mapeamento de pagamento** (PixTransaction precisa identificar se é upsell)

## 🚀 Próximos Passos

### 1. Executar Migration
```bash
cd /Users/mateusalves/mitski
source venv/bin/activate
alembic upgrade head
```

### 2. Criar Handlers de Menu (Básico)

Criar pelo menos:
- `handlers/upsell/menu_handlers.py` - Menu principal
- Adicionar routing em `workers/tasks.py`:
```python
elif callback_data.startswith("upsell_menu:"):
    bot_id = int(callback_data.split(":")[1])
    from handlers.upsell import handle_upsell_menu_click
    response = asyncio.run(handle_upsell_menu_click(user_id, bot_id))
```

### 3. Implementar Detecção de Trigger

Em `services/ai/conversation.py`, adicionar após processar resposta da IA:
```python
from services.upsell import TriggerDetector
from workers.upsell_tasks import send_upsell_announcement_triggered

# Detectar trigger
upsell_id = await TriggerDetector.detect_upsell_trigger(bot_id, ai_response.text)
if upsell_id:
    send_upsell_announcement_triggered.delay(bot_id, user_telegram_id, upsell_id)
```

### 4. Configurar Celery Beat

Em `workers/celery_app.py`:
```python
celery_app.conf.beat_schedule = {
    'check-pending-upsells': {
        'task': 'workers.upsell_tasks.check_pending_upsells',
        'schedule': 300.0,  # 5 minutos
    },
}
```

### 5. Melhorar get_pending_upsells

Implementar query SQL completa em `UpsellScheduler.get_pending_upsells_sync()` que:
1. Busca registros em user_upsell_history onde sent_at IS NULL
2. Junta com upsell_schedules
3. Calcula send_time baseado em último pagamento + schedule
4. Retorna lista de (user_id, bot_id, upsell_id) prontos

### 6. Adicionar Campo em PixTransaction

Para distinguir pagamentos de ofertas vs. upsells:
```python
# Migration nova
op.add_column('pix_transactions',
    sa.Column('upsell_id', sa.Integer(),
    sa.ForeignKey('upsells.id', ondelete='SET NULL'), nullable=True))
```

## 💡 Exemplo de Uso

### Configuração Básica

1. **Criar bot** → Upsell #1 criado automaticamente

2. **Configurar Upsell #1**:
   - Nome/Trigger: "premium-kit"
   - Valor: R$ 47,00
   - Anúncio: "Quer upgrade premium?"
   - Entrega: Link do produto premium
   - Fase: "Você está na fase premium. Seja direto."

3. **Primeiro pagamento**:
   - Cliente paga oferta principal (R$ 19,90)
   - Sistema ativa upsell
   - IA muda comportamento
   - IA menciona "premium-kit" → anúncio enviado

4. **Criar Upsell #2**:
   - Valor: R$ 27,00
   - Agendar: 3 dias após último pagamento
   - Anúncio automático após 3 dias

## 🐛 Troubleshooting

### Upsell não está sendo ativado
- Verificar se está 100% configurado (`UpsellService.is_upsell_complete()`)
- Verificar logs: `grep "Activating upsell flow" logs/`
- Verificar se é realmente o primeiro pagamento

### Trigger não está sendo detectado
- Verificar se conversation.py tem integração
- Trigger é case-sensitive
- Verificar logs da detecção

### Anúncio não está sendo enviado
- Verificar Celery worker rodando
- Verificar se task foi enfileirada
- Verificar token do bot válido

## 📊 Métricas e Logs

Todos os eventos importantes são logados:
- "Activating upsell flow"
- "Upsell flow activated"
- "Sending triggered upsell announcement"
- "Upsell announcement sent"
- "Scheduled upsell sent"

Usar `grep` para monitorar:
```bash
tail -f logs/app.log | grep -i upsell
```

## 🔒 Considerações de Segurança

- Validação de completude antes de ativar
- Lock Redis para evitar duplicação de envios
- Tokens criptografados no banco
- Rate limiting aplicado

## 📚 Referências

- Código base: Sistema de Ofertas (offers/)
- Código base: Sistema de Ações (ai_actions)
- Padrão: Sistema de Blocos reutilizável
- Worker pattern: payment_tasks.py

---

**Status**: ✅ Base implementada, pendente handlers completos e testes

**Última atualização**: 2025-10-04
