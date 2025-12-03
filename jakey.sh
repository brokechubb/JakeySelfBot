#!/bin/bash
# Jakey Startup Script
# Standard startup with MCP memory server
#
# Usage: ./jakey.sh [OPTIONS]
# Options:
#   --skip-mcp             Skip MCP memory server startup
#   --help                 Show help message
#
# Examples:
#   ./jakey.sh                                    # Start with MCP memory server
#   ./jakey.sh --skip-mcp                         # Start without MCP memory server

# Jakey Startup Script
# Basic startup with MCP memory server support

# Exit on any error
set -e

# PID file for ensuring only one instance runs
PID_FILE="/tmp/jakey.pid"

# Default configuration

# Define colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[STATUS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Parse command line arguments
SKIP_MCP="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-mcp)
            SKIP_MCP="true"
            shift
            ;;
        --help)
            echo "Jakey Startup Script"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-mcp             Skip MCP memory server startup"
            echo "  --help                 Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                                    # Start with MCP memory server"
            echo "  $0 --skip-mcp                         # Start without MCP memory server"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if another instance is already running
if [[ -f "$PID_FILE" ]]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        print_error "Jakey is already running with PID $OLD_PID"
        exit 1
    else
        # Remove stale PID file
        rm -f "$PID_FILE"
    fi
fi

# Check if venv exists
if [[ ! -d "venv" ]]; then
    print_warning "Virtual environment not found. Creating one..."
    python -m venv venv
    print_status "Virtual environment created."
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate

# Check if requirements need to be installed
if [[ -f "requirements.txt" ]]; then
    print_status "Checking dependencies..."
    pip install -r requirements.txt --quiet
fi

# Check if .env file exists
if [[ ! -f ".env" ]]; then
    print_warning ".env file not found. Please create one with your Discord token."
    print_warning "Example: echo 'DISCORD_TOKEN=your_token_here' > .env"
fi



# Function to monitor the bot during runtime
monitor_bot() {
    local check_interval=30
    local counter=0

    while true; do
        sleep $check_interval
        counter=$((counter + 1))

        # Check if bot is still running
        if ! kill -0 "$BOT_PID" 2>/dev/null; then
            break
        fi

        # Log metrics
        {
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] Status Check #$counter"
            echo "Bot PID: $BOT_PID - Running: $(kill -0 "$BOT_PID" 2>/dev/null && echo "Yes" || echo "No")"

            # Check memory usage if available
            if command -v ps >/dev/null 2>&1; then
                local memory_usage=$(ps -o rss= -p "$BOT_PID" 2>/dev/null | awk '{print $1/1024 " MB"}')
                if [[ -n "$memory_usage" ]]; then
                    echo "Memory Usage: $memory_usage"
                fi
            fi

            echo "---"
        } >> "logs/bot_monitoring.log"

    done &

    MONITOR_PID=$!
    print_info "Bot monitoring started (PID: $MONITOR_PID)"
}

# Create PID file
echo $$ > "$PID_FILE"

# Start MCP Memory Server in background (unless skipped)
if [[ "$SKIP_MCP" != "true" ]]; then
    print_status "Starting MCP Memory Server..."
    nohup python tools/mcp_memory_server.py > logs/mcp_server.log 2>&1 &
    MCP_PID=$!
    echo "MCP Memory Server started with PID: $MCP_PID"

    # Wait a moment for MCP server to start
    sleep 3

    # Check if MCP server is running by reading the port file
    if [[ -f ".mcp_port" ]]; then
        MCP_PORT=$(cat .mcp_port)
        if curl -s http://localhost:$MCP_PORT/health > /dev/null; then
            print_status "MCP Memory Server is healthy on port $MCP_PORT"
        else
            print_warning "MCP Memory Server health check failed on port $MCP_PORT, continuing anyway..."
        fi
    else
        print_warning "MCP port file not found, server may not have started properly"
    fi
else
    print_warning "Skipping MCP Memory Server startup (--skip-mcp flag used)"
    MCP_PID=""
fi

# Display startup configuration
print_info "Startup Configuration:"
print_info "  MCP Server: $([ "$SKIP_MCP" == "true" ] && echo "Skipped" || echo "Enabled")"

# Start the bot
print_status "Starting Jakey (PID: $)..."

# Standard startup
python main.py &
BOT_PID=$!

print_status "Jakey started with PID: $BOT_PID"

# Start bot monitoring
monitor_bot



# Function to cleanup on exit
cleanup() {
    print_status "Shutting down Jakey..."

    # Kill bot process
    if [[ -n "$BOT_PID" ]] && kill -0 "$BOT_PID" 2>/dev/null; then
        kill "$BOT_PID" 2>/dev/null || true
        wait "$BOT_PID" 2>/dev/null || true
    fi

    # Kill MCP server if running
    if [[ -n "$MCP_PID" ]] && kill -0 "$MCP_PID" 2>/dev/null; then
        print_status "Shutting down MCP Memory Server..."
        kill "$MCP_PID" 2>/dev/null || true
        wait "$MCP_PID" 2>/dev/null || true
    fi

    # Remove PID file
    rm -f "$PID_FILE"

    # Deactivate virtual environment
    deactivate 2>/dev/null || true

    print_status "Cleanup completed"
    }

    # Set up cleanup trap
    trap cleanup EXIT INT TERM

    # Wait for bot process
    if [[ -n "$BOT_PID" ]]; then
        wait "$BOT_PID"
        BOT_EXIT_CODE=$?

        if [[ $BOT_EXIT_CODE -eq 0 ]]; then
            print_status "Jakey exited normally"
        else
            print_error "Jakey exited with code $BOT_EXIT_CODE"
        fi
    fi

    # Final cleanup message
    print_status "Jakey shutdown complete"
