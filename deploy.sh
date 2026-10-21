#!/bin/bash
# One-click deployment script for DigitalOcean Ubuntu Droplet
set -e

echo "=== Deploying WEEX BTC Displacement Bot ==="

# Update package lists
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv git

# Install Python requirements
python3 -m pip install --upgrade pip
pip3 install -r requirements.txt

# Create .env if not exists
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "PLEASE EDIT .env WITH YOUR WEEX API CREDENTIALS!"
fi

# Setup systemd service
echo "Configuring systemd service..."
CURRENT_DIR=$(pwd)
sudo sed -i "s|/root/weex-btc-displacement-bot|$CURRENT_DIR|g" weex-bot.service
sudo cp weex-bot.service /etc/systemd/system/weex-bot.service

sudo systemctl daemon-reload
sudo systemctl enable weex-bot

echo "=== Deployment Complete ==="
echo "1. Edit your .env file: nano .env"
echo "2. Run diagnostic: python3 test_connection.py"
echo "3. Start the bot: sudo systemctl start weex-bot"
echo "4. View live logs: sudo journalctl -u weex-bot -f"
