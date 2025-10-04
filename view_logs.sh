#!/bin/bash
# Script para visualizar logs do bot

echo "=== Visualizador de Logs do Telegram Bot Manager ==="
echo ""
echo "Escolha uma opção:"
echo "1) Ver logs em tempo real (Docker containers)"
echo "2) Ver arquivo de log (logs/app.log)"
echo "3) Ver logs filtrados por 'AI conversation'"
echo "4) Ver logs filtrados por 'Grok API'"
echo "5) Seguir logs em tempo real do arquivo"
echo ""
read -p "Opção: " opcao

case $opcao in
    1)
        echo "Seguindo logs dos containers (Ctrl+C para sair)..."
        docker-compose logs -f webhook worker
        ;;
    2)
        echo "Conteúdo de logs/app.log:"
        cat logs/app.log | jq -C '.' 2>/dev/null || cat logs/app.log
        ;;
    3)
        echo "Logs de conversação com IA:"
        cat logs/app.log | grep "AI conversation" | jq -C '.' 2>/dev/null || cat logs/app.log | grep "AI conversation"
        ;;
    4)
        echo "Logs da API Grok:"
        cat logs/app.log | grep "Grok API" | jq -C '.' 2>/dev/null || cat logs/app.log | grep "Grok API"
        ;;
    5)
        echo "Seguindo logs/app.log em tempo real (Ctrl+C para sair)..."
        tail -f logs/app.log | jq -C '.' 2>/dev/null || tail -f logs/app.log
        ;;
    *)
        echo "Opção inválida!"
        exit 1
        ;;
esac
