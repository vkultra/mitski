#!/bin/bash
# Smoke test - testa se os serviços estão rodando corretamente

set -e

echo "= Iniciando smoke tests..."

# Cores para output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Função para testar endpoint
test_endpoint() {
    local name=$1
    local url=$2
    local expected_code=$3

    echo -n "Testing $name... "
    response=$(curl -s -o /dev/null -w "%{http_code}" "$url" || echo "000")

    if [ "$response" = "$expected_code" ]; then
        echo -e "${GREEN} OK${NC} (HTTP $response)"
        return 0
    else
        echo -e "${RED} FAIL${NC} (HTTP $response, expected $expected_code)"
        return 1
    fi
}

# Testa health check
test_endpoint "Health Check" "http://localhost:8000/health" "200"

# Testa se Redis está respondendo
echo -n "Testing Redis... "
if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN} OK${NC}"
else
    echo -e "${RED} FAIL${NC}"
    exit 1
fi

# Testa se PostgreSQL está respondendo
echo -n "Testing PostgreSQL... "
if docker-compose exec -T postgres pg_isready -U admin > /dev/null 2>&1; then
    echo -e "${GREEN} OK${NC}"
else
    echo -e "${RED} FAIL${NC}"
    exit 1
fi

# Verifica se workers estão rodando
echo -n "Testing Celery Workers... "
worker_count=$(docker-compose ps worker | grep -c "Up" || echo "0")
if [ "$worker_count" -ge "1" ]; then
    echo -e "${GREEN} OK${NC} ($worker_count workers running)"
else
    echo -e "${RED} FAIL${NC} (no workers running)"
    exit 1
fi

echo ""
echo -e "${GREEN} All smoke tests passed!${NC}"
