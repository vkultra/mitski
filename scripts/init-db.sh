#!/bin/bash
set -e

# Script de inicialização do banco de dados PostgreSQL
# Este script é executado automaticamente quando o container PostgreSQL inicia pela primeira vez

echo "Inicializando banco de dados telegram_bots..."

# Configurações de performance para produção
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Configurações de performance
    ALTER SYSTEM SET shared_buffers = '256MB';
    ALTER SYSTEM SET effective_cache_size = '1GB';
    ALTER SYSTEM SET maintenance_work_mem = '64MB';
    ALTER SYSTEM SET checkpoint_completion_target = 0.9;
    ALTER SYSTEM SET wal_buffers = '16MB';
    ALTER SYSTEM SET default_statistics_target = 100;
    ALTER SYSTEM SET random_page_cost = 1.1;
    ALTER SYSTEM SET effective_io_concurrency = 200;
    ALTER SYSTEM SET work_mem = '4MB';
    ALTER SYSTEM SET min_wal_size = '1GB';
    ALTER SYSTEM SET max_wal_size = '4GB';
    ALTER SYSTEM SET max_worker_processes = 8;
    ALTER SYSTEM SET max_parallel_workers_per_gather = 4;
    ALTER SYSTEM SET max_parallel_workers = 8;
    ALTER SYSTEM SET max_parallel_maintenance_workers = 4;

    -- Criar schema se não existir
    CREATE SCHEMA IF NOT EXISTS public;

    -- Configurar timezone
    SET timezone = 'America/Sao_Paulo';

    -- Criar extensões úteis
    CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
    CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- Para buscas com LIKE otimizadas
    CREATE EXTENSION IF NOT EXISTS unaccent; -- Para remover acentos em buscas

    -- Criar usuário de aplicação com permissões limitadas (opcional)
    -- CREATE USER app_user WITH PASSWORD 'senha_app';
    -- GRANT CONNECT ON DATABASE telegram_bots TO app_user;
    -- GRANT USAGE ON SCHEMA public TO app_user;
    -- GRANT CREATE ON SCHEMA public TO app_user;
    -- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_user;
    -- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO app_user;
    -- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO app_user;
    -- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO app_user;

    -- Criar tabela de auditoria (opcional)
    CREATE TABLE IF NOT EXISTS audit_log (
        id SERIAL PRIMARY KEY,
        table_name VARCHAR(100),
        action VARCHAR(10),
        user_id INTEGER,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        data JSONB
    );

    -- Criar índice para performance na tabela de auditoria
    CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp DESC);
    CREATE INDEX IF NOT EXISTS idx_audit_table_action ON audit_log(table_name, action);

    -- Função para limpeza automática de logs antigos
    CREATE OR REPLACE FUNCTION cleanup_old_logs()
    RETURNS void AS \$$
    BEGIN
        DELETE FROM audit_log WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '30 days';
    END;
    \$$ LANGUAGE plpgsql;

    -- Configurar vacuum automático para tabelas grandes
    ALTER TABLE audit_log SET (autovacuum_vacuum_scale_factor = 0.01);
    ALTER TABLE audit_log SET (autovacuum_analyze_scale_factor = 0.005);

EOSQL

# Criar diretório de backup se não existir
mkdir -p /backups

echo "Banco de dados inicializado com sucesso!"
