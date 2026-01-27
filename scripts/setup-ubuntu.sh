#!/bin/bash

# ============================================================
# Polymarket Sports Bot - Quick Setup Script for Ubuntu 22.04
# For beginners - just run: bash setup.sh
# ============================================================

set -e

clear

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                                                          ║"
echo "║     POLYMARKET SPORTS BOT - AUTOMATIC INSTALLER          ║"
echo "║                                                          ║"
echo "║     This will set up everything you need.                ║"
echo "║     Just sit back and wait for it to finish!             ║"
echo "║                                                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ ERROR: Please run this script as root."
    echo ""
    echo "   Try running: sudo bash setup.sh"
    echo ""
    exit 1
fi

echo "⏳ This will take about 5-10 minutes. Please don't close this window!"
echo ""
sleep 2

# Update system
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 STEP 1 of 6: Updating your server..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
apt update -qq && apt upgrade -y -qq
echo "✅ Server updated!"
echo ""

# Install dependencies
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 STEP 2 of 6: Installing required software..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
apt install -y -qq \
    apt-transport-https \
    ca-certificates \
    curl \
    software-properties-common \
    nginx \
    certbot \
    python3-certbot-nginx \
    git \
    ufw > /dev/null 2>&1
echo "✅ Required software installed!"
echo ""

# Install Docker
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🐳 STEP 3 of 6: Installing Docker..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg 2>/dev/null
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt update -qq
    apt install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin > /dev/null 2>&1
    systemctl enable docker > /dev/null 2>&1
    systemctl start docker
    echo "✅ Docker installed!"
else
    echo "✅ Docker was already installed!"
fi
echo ""

# Create application user
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "👤 STEP 4 of 6: Creating bot user account..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if ! id "botuser" &>/dev/null; then
    useradd -m -s /bin/bash botuser
    usermod -aG docker botuser
    usermod -aG sudo botuser
    echo "✅ User 'botuser' created!"
else
    usermod -aG docker botuser 2>/dev/null || true
    echo "✅ User 'botuser' already exists!"
fi
echo ""

# Configure firewall
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔒 STEP 5 of 6: Setting up firewall security..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ufw --force enable > /dev/null 2>&1
ufw allow 22 > /dev/null 2>&1
ufw allow 80 > /dev/null 2>&1
ufw allow 443 > /dev/null 2>&1
ufw allow 8000 > /dev/null 2>&1
echo "✅ Firewall configured!"
echo ""

# Generate secrets
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔐 STEP 6 of 6: Generating your secure passwords..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_hex(16))")
echo "✅ Passwords generated!"
echo ""

# Get server IP
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "YOUR_SERVER_IP")

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                                                          ║"
echo "║              ✅ SETUP COMPLETE! ✅                       ║"
echo "║                                                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "┌──────────────────────────────────────────────────────────┐"
echo "│  ⚠️  IMPORTANT: SAVE THESE CREDENTIALS NOW!              │"
echo "│      (Take a screenshot or write them down)              │"
echo "└──────────────────────────────────────────────────────────┘"
echo ""
echo "  SECRET_KEY=$SECRET_KEY"
echo ""
echo "  DB_PASSWORD=$DB_PASSWORD"
echo ""
echo "  Your Server IP: $SERVER_IP"
echo ""
echo "┌──────────────────────────────────────────────────────────┐"
echo "│  📋 NEXT STEPS - Copy and paste these commands:          │"
echo "└──────────────────────────────────────────────────────────┘"
echo ""
echo "  STEP 1: Switch to bot user (type this and press Enter):"
echo "  ─────────────────────────────────────────────────────────"
echo "  su - botuser"
echo ""
echo "  STEP 2: Download the bot:"
echo "  ─────────────────────────────────────────────────────────"
echo "  git clone https://github.com/benedict-anokye-davies/Polymarket-Sports-Bot.git"
echo ""
echo "  STEP 3: Go into the folder:"
echo "  ─────────────────────────────────────────────────────────"
echo "  cd Polymarket-Sports-Bot"
echo ""
echo "  STEP 4: Create config file:"
echo "  ─────────────────────────────────────────────────────────"
echo "  cp .env.example .env"
echo ""
echo "  STEP 5: Edit the config file:"
echo "  ─────────────────────────────────────────────────────────"
echo "  nano .env"
echo ""
echo "  Then change these lines in the file:"
echo "    SECRET_KEY=$SECRET_KEY"
echo "    DATABASE_URL=postgresql+asyncpg://postgres:$DB_PASSWORD@db:5432/polymarket_bot"
echo ""
echo "  Save with: Ctrl+X, then Y, then Enter"
echo ""
echo "  STEP 6: Start the bot:"
echo "  ─────────────────────────────────────────────────────────"
echo "  docker compose up -d --build"
echo ""
echo "  STEP 7: Check if it's running:"
echo "  ─────────────────────────────────────────────────────────"
echo "  docker compose ps"
echo ""
echo "┌──────────────────────────────────────────────────────────┐"
echo "│  🌐 ACCESS YOUR BOT:                                     │"
echo "│     Open your browser and go to:                         │"
echo "│     http://$SERVER_IP:8000                       │"
echo "└──────────────────────────────────────────────────────────┘"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Need help? Check BEGINNER_HOSTING_GUIDE.md in the repo"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
