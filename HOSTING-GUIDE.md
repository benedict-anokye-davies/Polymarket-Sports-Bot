# Kalshi Sports Trading Bot - Hostinger VPS Setup Guide

This guide will walk you through setting up your trading bot on Hostinger VPS. No programming knowledge required - just follow each step exactly.

---

## Table of Contents
1. [Purchase Hostinger VPS](#step-1-purchase-hostinger-vps)
2. [Access Your Server](#step-2-access-your-server)
3. [Install Required Software](#step-3-install-required-software)
4. [Deploy the Bot](#step-4-deploy-the-bot)
5. [Configure the Bot](#step-5-configure-the-bot)
6. [Start the Bot](#step-6-start-the-bot)
7. [Access Your Dashboard](#step-7-access-your-dashboard)
8. [Maintenance Commands](#step-8-maintenance-commands)
9. [Troubleshooting](#troubleshooting)

---

## Step 1: Purchase Hostinger VPS

### 1.1 Go to Hostinger
1. Open your browser and go to: https://www.hostinger.com/vps-hosting
2. Click on **KVM 2** plan ($6.99/month) - this has 8GB RAM which is perfect

### 1.2 Complete Purchase
1. Select **24 months** for the best price
2. Create a Hostinger account or sign in
3. Complete payment

### 1.3 Setup Your VPS
After purchase, you'll be taken to the VPS setup page:

1. **Operating System**: Select **Ubuntu 22.04**
2. **Server Location**: Choose the location closest to you (US or Europe)
3. **Root Password**: Create a STRONG password and **WRITE IT DOWN** - you'll need this!
4. **Hostname**: Enter `trading-bot` (or any name you want)
5. Click **Create**

Wait 2-5 minutes for your server to be created.

### 1.4 Get Your Server IP Address
1. In your Hostinger dashboard, go to **VPS** section
2. You'll see your server with an **IP Address** (looks like: `123.45.67.89`)
3. **Write down this IP address** - you'll need it!

---

## Step 2: Access Your Server

### 2.1 Download PuTTY (Windows SSH Client)
1. Go to: https://www.putty.org/
2. Click **Download PuTTY**
3. Download the **64-bit MSI installer**
4. Run the installer and click Next through all steps

### 2.2 Connect to Your Server
1. Open **PuTTY** from your Start menu
2. In the **Host Name** field, enter your server IP address
3. Make sure **Port** is `22`
4. Click **Open**
5. If you see a security warning, click **Accept**
6. When it asks for login: type `root` and press Enter
7. When it asks for password: type your root password and press Enter
   - Note: You won't see the password as you type - this is normal!

You should now see something like:
```
root@trading-bot:~#
```

**Congratulations! You're connected to your server!**

---

## Step 3: Install Required Software

Now we need to install the software the bot needs. **Copy and paste each command exactly**, then press Enter.

### 3.1 Update the Server
Copy this entire block and paste it:
```bash
apt update && apt upgrade -y
```
Wait for it to finish (1-2 minutes). If it asks any questions, just press Enter.

### 3.2 Install Docker
Copy and paste:
```bash
curl -fsSL https://get.docker.com | sh
```
Wait for it to finish (1-2 minutes).

### 3.3 Install Docker Compose
Copy and paste:
```bash
apt install -y docker-compose-plugin
```

### 3.4 Install Other Tools
Copy and paste:
```bash
apt install -y git nginx certbot python3-certbot-nginx
```

### 3.5 Enable Docker to Start on Boot
Copy and paste:
```bash
systemctl enable docker
systemctl start docker
```

---

## Step 4: Deploy the Bot

### 4.1 Create App Directory
Copy and paste:
```bash
mkdir -p /opt/trading-bot
cd /opt/trading-bot
```

### 4.2 Download the Bot Code
Copy and paste:
```bash
git clone https://github.com/benedict-anokye-davies/Polymarket-Sports-Bot.git .
```

### 4.3 Create Environment File
Copy and paste:
```bash
cp .env.example .env
```

---

## Step 5: Configure the Bot

### 5.1 Generate Security Keys
First, let's generate the security keys you need. Copy and paste:
```bash
echo "Your SECRET_KEY:"
openssl rand -hex 32
echo ""
echo "Your ENCRYPTION_KEY:"
openssl rand -base64 32
```

**IMPORTANT: Write down both keys that appear!** You'll need them in the next step.

### 5.2 Edit Configuration
Copy and paste:
```bash
nano .env
```

This opens a text editor. Use arrow keys to navigate. Find and change these lines:

```
# Change this line - use a strong password (letters, numbers, symbols)
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_STRONG_PASSWORD_HERE@db:5432/polymarket_bot

# Paste your SECRET_KEY here (the first key you generated)
SECRET_KEY=paste-your-secret-key-here

# Paste your ENCRYPTION_KEY here (the second key you generated)
ENCRYPTION_KEY=paste-your-encryption-key-here

# Your server IP or domain
CORS_ALLOWED_ORIGINS=https://polymarket-sports-bot.pages.dev,http://YOUR_SERVER_IP:8000
```

**To save and exit:**
1. Press `Ctrl + X`
2. Press `Y` to confirm
3. Press `Enter`

### 5.3 Update Docker Compose for Production
Copy and paste:
```bash
cat > docker-compose.prod.yml << 'EOF'
version: '3.8'

services:
  app:
    build: .
    restart: always
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - SECRET_KEY=${SECRET_KEY}
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
      - CORS_ALLOWED_ORIGINS=${CORS_ALLOWED_ORIGINS}
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  db:
    image: postgres:15-alpine
    restart: always
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=${DATABASE_URL#*:*:}
      - POSTGRES_DB=polymarket_bot
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
EOF
```

---

## Step 6: Start the Bot

### 6.1 Build and Start
Copy and paste:
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

**This will take 3-5 minutes the first time.** You'll see lots of text scrolling - this is normal.

### 6.2 Check if It's Running
Copy and paste:
```bash
docker compose -f docker-compose.prod.yml ps
```

You should see both `app` and `db` with status `Up` or `running`.

### 6.3 Check the Logs
Copy and paste:
```bash
docker compose -f docker-compose.prod.yml logs app --tail 50
```

Look for a line that says something like `Uvicorn running on http://0.0.0.0:8000`

---

## Step 7: Access Your Dashboard

### 7.1 Configure Firewall
Copy and paste:
```bash
ufw allow 22
ufw allow 80
ufw allow 443
ufw allow 8000
ufw --force enable
```

### 7.2 Test the Bot
Open your web browser and go to:
```
http://YOUR_SERVER_IP:8000/health
```
(Replace YOUR_SERVER_IP with your actual server IP)

You should see:
```json
{"status":"healthy","app":"polymarket-bot"...}
```

### 7.3 Access the Dashboard
The bot's web dashboard is hosted separately on Cloudflare Pages:
- **Dashboard URL**: https://polymarket-sports-bot.pages.dev

When you log in, the dashboard connects to your server at `http://YOUR_SERVER_IP:8000`

**Note**: You may need to update the frontend to point to your new server. Contact the developer for this step.

---

## Step 8: Maintenance Commands

Save these commands - you'll use them to manage your bot.

### View Bot Status
```bash
cd /opt/trading-bot
docker compose -f docker-compose.prod.yml ps
```

### View Bot Logs (Recent)
```bash
cd /opt/trading-bot
docker compose -f docker-compose.prod.yml logs app --tail 100
```

### View Bot Logs (Live - Press Ctrl+C to stop)
```bash
cd /opt/trading-bot
docker compose -f docker-compose.prod.yml logs -f app
```

### Restart the Bot
```bash
cd /opt/trading-bot
docker compose -f docker-compose.prod.yml restart
```

### Stop the Bot
```bash
cd /opt/trading-bot
docker compose -f docker-compose.prod.yml down
```

### Start the Bot
```bash
cd /opt/trading-bot
docker compose -f docker-compose.prod.yml up -d
```

### Update the Bot (When New Version Released)
```bash
cd /opt/trading-bot
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

---

## Troubleshooting

### "Connection refused" when accessing the bot
1. Check if the bot is running:
   ```bash
   docker compose -f docker-compose.prod.yml ps
   ```
2. If not running, start it:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```
3. Check the logs for errors:
   ```bash
   docker compose -f docker-compose.prod.yml logs app --tail 100
   ```

### Bot keeps crashing/restarting
Check the logs:
```bash
docker compose -f docker-compose.prod.yml logs app --tail 200
```
Look for red error messages. Common issues:
- Database password incorrect in `.env` file
- Missing SECRET_KEY or ENCRYPTION_KEY

### Can't connect via PuTTY
1. Make sure your server is running in Hostinger dashboard
2. Double-check the IP address
3. Make sure you're using port 22

### Forgot your root password
1. Go to Hostinger dashboard
2. Find your VPS
3. Click on "Reset Root Password"
4. Set a new password
5. Wait 2-3 minutes, then try connecting again

### Database errors
If you see database-related errors, reset the database:
```bash
cd /opt/trading-bot
docker compose -f docker-compose.prod.yml down
docker volume rm trading-bot_postgres_data
docker compose -f docker-compose.prod.yml up -d
```
**Warning**: This deletes all data! Only do this if you're starting fresh.

---

## Monthly Costs

| Service | Cost |
|---------|------|
| Hostinger VPS (KVM 2) | $6.99/month |
| Cloudflare Pages (Frontend) | FREE |
| **Total** | **~$7/month** |

---

## Support

If you encounter issues:
1. Check the [Troubleshooting](#troubleshooting) section above
2. Contact the developer

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────┐
│                 TRADING BOT QUICK COMMANDS              │
├─────────────────────────────────────────────────────────┤
│ Connect to server:     Open PuTTY → Enter IP → Login   │
│ Go to bot folder:      cd /opt/trading-bot              │
│ Check status:          docker compose -f docker-compose.prod.yml ps        │
│ View logs:             docker compose -f docker-compose.prod.yml logs app  │
│ Restart bot:           docker compose -f docker-compose.prod.yml restart   │
│ Stop bot:              docker compose -f docker-compose.prod.yml down      │
│ Start bot:             docker compose -f docker-compose.prod.yml up -d     │
│ Update bot:            git pull && docker compose -f docker-compose.prod.yml up -d --build │
├─────────────────────────────────────────────────────────┤
│ Dashboard:             https://polymarket-sports-bot.pages.dev              │
│ Server Health:         http://YOUR_IP:8000/health       │
└─────────────────────────────────────────────────────────┘
```
