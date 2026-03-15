#!/usr/bin/env bash
# ============================================
# AI Content Machine — Server Setup Script
# Run this on a fresh Ubuntu 22.04+ DigitalOcean droplet
# Usage: bash deploy/setup_server.sh
# ============================================

set -euo pipefail

echo "========================================"
echo " AI Content Machine — Server Setup"
echo "========================================"

# 1. System update
echo "[1/6] Updating system..."
sudo apt-get update && sudo apt-get upgrade -y

# 2. Install Docker
echo "[2/6] Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo "Docker installed. You may need to re-login for group changes."
else
    echo "Docker already installed."
fi

# 3. Install Docker Compose
echo "[3/6] Installing Docker Compose..."
if ! command -v docker compose &> /dev/null; then
    sudo apt-get install -y docker-compose-plugin
else
    echo "Docker Compose already installed."
fi

# 4. Install useful tools
echo "[4/6] Installing utilities..."
sudo apt-get install -y git htop curl ufw fail2ban

# 5. Configure firewall
echo "[5/6] Configuring firewall..."
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP
sudo ufw allow 443/tcp     # HTTPS
sudo ufw allow 8000/tcp    # API
sudo ufw allow 5678/tcp    # n8n
sudo ufw --force enable

# 6. Create project directory
echo "[6/6] Creating project directory..."
mkdir -p ~/content-machine
cd ~/content-machine

echo ""
echo "========================================"
echo " Setup complete!"
echo " Next steps:"
echo "   1. git clone your-repo ~/content-machine"
echo "   2. cp .env.example .env && nano .env"
echo "   3. docker compose up -d"
echo "========================================"
