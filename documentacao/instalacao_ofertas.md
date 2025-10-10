# Instalação do Sistema de Ofertas

## Passo a Passo

### 1. Aplicar Migrations

```bash
# Ativar ambiente virtual (se existir)
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Aplicar migration
python -m alembic upgrade head

# Verificar se foi aplicada
python -m alembic current
```

### 2. Executar Testes

```bash
# Instalar pytest se necessário
pip install pytest pytest-asyncio

# Executar testes
python -m pytest tests/test_offers.py -v

# Com coverage
python -m pytest tests/test_offers.py --cov=services.offers --cov-report=html
```

### 3. Verificar Instalação

Para verificar se tudo está funcionando:

1. **Verificar tabelas no banco:**
```sql
-- PostgreSQL
\dt offers
\dt offer_pitch_blocks
\dt offer_deliverables

-- Ou via query
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name LIKE 'offer%';
```

2. **Testar no Bot Gerenciador:**
   - Envie `/start` ao bot gerenciador
   - Navegue até: `IA → Selecionar Bot → 💰 Ofertas`
   - Crie uma oferta teste

3. **Testar Detecção:**
   - Configure uma oferta simples (ex: "TesteOferta")
   - Converse com o bot secundário
   - Quando IA responder "TesteOferta", deve substituir pelo pitch

## Configurações Necessárias

### Variáveis de Ambiente

Certifique-se que estas variáveis estão configuradas:

```bash
# .env
MANAGER_BOT_TOKEN=seu_token_aqui
ALLOWED_ADMIN_IDS=                 # opcional: deixe vazio para liberar todas as funções
DB_URL=postgresql://usuario:senha@localhost/banco
REDIS_URL=redis://localhost:6379
```

### Dependências

Adicione ao `requirements.txt` se necessário:

```txt
# Já devem estar presentes
sqlalchemy>=2.0
alembic>=1.14
redis>=4.0
celery>=5.3
pytest>=7.4
pytest-asyncio>=0.21
```

## Troubleshooting Comum

### Erro: "Table 'offers' doesn't exist"

**Solução:**
```bash
python -m alembic upgrade head
```

### Erro: "Module 'services.offers' not found"

**Solução:**
```bash
# Certificar que está no diretório raiz do projeto
cd /Users/mateusalves/mitski

# Adicionar ao PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Erro: "Permission denied" ao criar oferta

**Solução:**
- (Opcional) Usar `ALLOWED_ADMIN_IDS` apenas se precisar restringir funções
- Reiniciar workers após mudanças no .env

### Mídia não enviando

**Solução:**
1. Verificar token do bot
2. Testar com imagem pequena (<1MB)
3. Verificar logs para erros de API

## Comandos Úteis

### Limpar Cache Redis
```bash
redis-cli FLUSHDB
```

### Verificar Workers Celery
```bash
celery -A workers.celery_app status
```

### Logs em Tempo Real
```bash
# Webhook
tail -f logs/webhook.log

# Workers
tail -f logs/celery.log

# Geral
docker-compose logs -f
```

## Checklist de Deploy

- [ ] Migrations aplicadas
- [ ] Testes passando
- [ ] Variáveis de ambiente configuradas
- [ ] Redis rodando
- [ ] PostgreSQL rodando
- [ ] Workers Celery ativos
- [ ] Webhook configurado
- [ ] Bot gerenciador respondendo
- [ ] IDs de admin configurados

## Próximos Passos

Após instalação bem-sucedida:

1. Criar primeira oferta de teste
2. Configurar pitch com 2-3 blocos
3. Testar detecção com bot secundário
4. Ajustar delays e efeitos
5. Criar ofertas reais

---

**Suporte:** Consulte `documentacao/sistema_ofertas.md` para mais detalhes
