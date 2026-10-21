#!/bin/bash
# One-click deployment script for DigitalOcean Ubuntu Droplet (with venv for Ubuntu 24.04/Noble)
set -e

echo "=== Deploying WEEX BTC Displacement Bot ==="

# Update package lists
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv git

# Create and use virtual environment (avoids PEP 668 externally-managed-environment error)
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment in ./venv ..."
    python3 -m venv venv
fi

# Install Python requirements inside venv
echo "Installing requirements into virtual environment..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# Create .env if not exists
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "PLEASE EDIT .env WITH YOUR WEEX API CREDENTIALS!"
fi

# Setup systemd service with venv python path
echo "Configuring systemd service..."
CURRENT_DIR=$(pwd)
sudo sed -i "s|WorkingDirectory=.*|WorkingDirectory=$CURRENT_DIR|g" weex-bot.service
sudo sed -i "s|ExecStart=.*|ExecStart=$CURRENT_DIR/venv/bin/python -u bot.py|g" weex-bot.service
sudo cp weex-bot.service /etc/systemd/system/weex-bot.service

sudo systemctl daemon-reload
sudo systemctl enable weex-bot

echo ""
echo "=== Deployment Complete ==="
echo "1. Edit your .env file: nano .env"
echo "2. Run diagnostic: ./venv/bin/python test_connection.py"
echo "3. Start the bot: sudo systemctl start weex-bot"
echo "4. View live logs: sudo journalctl -u weex-bot -f"
