#!/bin/bash

# Service control script for JakeySelfBot

ACTION=$1

case $ACTION in
    start)
        echo "Starting JakeySelfBot services..."
        sudo systemctl start jakey-mcp-server.service
        sudo systemctl start jakey-self-bot.service
        echo "Services started."
        ;;
    stop)
        echo "Stopping JakeySelfBot services..."
        sudo systemctl stop jakey-self-bot.service
        sudo systemctl stop jakey-mcp-server.service
        echo "Services stopped."
        ;;
    restart)
        echo "Restarting JakeySelfBot services..."
        sudo systemctl restart jakey-self-bot.service
        sudo systemctl restart jakey-mcp-server.service
        echo "Services restarted."
        ;;
    status)
        echo "JakeySelfBot service status:"
        sudo systemctl status jakey-mcp-server.service --no-pager
        sudo systemctl status jakey-self-bot.service --no-pager
        ;;
    logs)
        echo "JakeySelfBot service logs:"
        sudo journalctl -u jakey-mcp-server.service -u jakey-self-bot.service -f
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo "  start   - Start all services"
        echo "  stop    - Stop all services"
        echo "  restart - Restart all services"
        echo "  status  - Show service status"
        echo "  logs    - Follow service logs"
        exit 1
        ;;
esac