#!/bin/bash
# One-click deployment script for DigitalOcean Ubuntu Droplet
set -e

echo "=== Deploying WEEX BTC Displacement Bot ==="

# Update package lists
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv git

# Create and use virtual environment
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

# Setup systemd service with unique name to avoid colliding with old bots
echo "Configuring systemd service (weex-displacement.service)..."
CURRENT_DIR=$(pwd)
sudo sed -i "s|WorkingDirectory=.*|WorkingDirectory=$CURRENT_DIR|g" weex-displacement.service
sudo sed -i "s|ExecStart=.*|ExecStart=$CURRENT_DIR/venv/bin/python -u bot.py|g" weex-displacement.service
sudo cp weex-displacement.service /etc/systemd/system/weex-displacement.service

sudo systemctl daemon-reload
sudo systemctl enable weex-displacement

echo ""
echo "=== Deployment Complete ==="
echo "1. Verify .env file: nano .env"
echo "2. Run diagnostic: ./venv/bin/python test_connection.py"
echo "3. Start the bot: sudo systemctl start weex-displacement"
echo "4. View live logs: sudo journalctl -u weex-displacement -f"
