#!/bin/bash

# Setup script for JakeySelfBot systemd services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[STATUS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root"
   exit 1
fi

# Check if we're in the right directory
if [[ ! -f "main.py" ]]; then
    print_error "main.py not found. Please run this script from the JakeySelfBot root directory."
    exit 1
fi

# Get the current user
CURRENT_USER=$(whoami)
print_status "Setting up JakeySelfBot systemd services for user: $CURRENT_USER"

# Create virtual environment if it doesn't exist
if [[ ! -d "venv" ]]; then
    print_status "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
print_status "Installing dependencies..."
pip install -r requirements.txt

# Check if .env file exists
if [[ ! -f ".env" ]]; then
    print_warning ".env file not found. Please create one with your Discord token."
    print_warning "Example: echo 'DISCORD_TOKEN=your_token_here' > .env"
fi

# Copy service files to systemd directory
print_status "Installing systemd service files..."
sudo cp jakey-mcp-server.service /etc/systemd/system/
sudo cp jakey-self-bot.service /etc/systemd/system/

# Update user in service files
sudo sed -i "s/User=chubb/User=$CURRENT_USER/g" /etc/systemd/system/jakey-mcp-server.service
sudo sed -i "s/Group=chubb/Group=$(id -gn $CURRENT_USER)/g" /etc/systemd/system/jakey-mcp-server.service
sudo sed -i "s/User=chubb/User=$CURRENT_USER/g" /etc/systemd/system/jakey-self-bot.service
sudo sed -i "s/Group=chubb/Group=$(id -gn $CURRENT_USER)/g" /etc/systemd/system/jakey-self-bot.service

# Update paths in service files
sudo sed -i "s|/home/chubb/bots/JakeySelfBot|$(pwd)|g" /etc/systemd/system/jakey-mcp-server.service
sudo sed -i "s|/home/chubb/bots/JakeySelfBot|$(pwd)|g" /etc/systemd/system/jakey-self-bot.service

# Reload systemd daemon
print_status "Reloading systemd daemon..."
sudo systemctl daemon-reload

# Enable services
print_status "Enabling systemd services..."
sudo systemctl enable jakey-mcp-server.service
sudo systemctl enable jakey-self-bot.service

# Start services
print_status "Starting Jakey MCP Server..."
sudo systemctl start jakey-mcp-server.service

# Wait a moment for MCP server to start
sleep 5

# Check if MCP server is running
if systemctl is-active --quiet jakey-mcp-server.service; then
    print_status "Jakey MCP Server started successfully"
else
    print_warning "Jakey MCP Server failed to start. Check logs with: sudo journalctl -u jakey-mcp-server.service"
fi

print_status "Starting Jakey Self-Bot..."
sudo systemctl start jakey-self-bot.service

# Check if bot is running
if systemctl is-active --quiet jakey-self-bot.service; then
    print_status "Jakey Self-Bot started successfully"
else
    print_warning "Jakey Self-Bot failed to start. Check logs with: sudo journalctl -u jakey-self-bot.service"
fi

print_status "Setup complete!"
print_status "You can check service status with:"
echo "  sudo systemctl status jakey-mcp-server.service"
echo "  sudo systemctl status jakey-self-bot.service"
print_status "You can check service logs with:"
echo "  sudo journalctl -u jakey-mcp-server.service -f"
echo "  sudo journalctl -u jakey-self-bot.service -f"
print_status "To stop services:"
echo "  sudo systemctl stop jakey-self-bot.service"
echo "  sudo systemctl stop jakey-mcp-server.service"