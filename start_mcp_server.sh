#!/bin/bash
# Start MCP Memory Server if not already running

# Check if MCP server is already running by checking port file
if [[ -f ".mcp_port" ]]; then
    MCP_PORT=$(cat .mcp_port)
    if curl -s http://localhost:$MCP_PORT/health > /dev/null 2>&1; then
        echo "MCP Memory Server is already running on port $MCP_PORT"
        exit 0
    fi
fi

echo "Starting MCP Memory Server..."
nohup python tools/mcp_memory_server.py > mcp_server.log 2>&1 &
MCP_PID=$!

# Wait for server to start
sleep 3

# Check if server started successfully
if [[ -f ".mcp_port" ]]; then
    MCP_PORT=$(cat .mcp_port)
    if curl -s http://localhost:$MCP_PORT/health > /dev/null; then
        echo "MCP Memory Server started successfully on port $MCP_PORT (PID: $MCP_PID)"
    else
        echo "Failed to start MCP Memory Server on port $MCP_PORT"
        exit 1
    fi
else
    echo "Failed to start MCP Memory Server - port file not created"
    exit 1
fi