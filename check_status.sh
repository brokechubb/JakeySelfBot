#!/bin/bash

# Check status of JakeySelfBot services

echo "=== JakeySelfBot Service Status ==="
echo

echo "MCP Memory Server:"
sudo systemctl status jakey-mcp-server.service --no-pager -l | head -10
echo

echo "Self-Bot:"
sudo systemctl status jakey-self-bot.service --no-pager -l | head -10
echo

echo "=== Service Logs (last 10 lines) ==="
echo

echo "MCP Memory Server Logs:"
sudo journalctl -u jakey-mcp-server.service --no-pager -n 10
echo

echo "Self-Bot Logs:"
sudo journalctl -u jakey-self-bot.service --no-pager -n 10
echo