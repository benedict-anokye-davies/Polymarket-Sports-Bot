#!/bin/bash

# setup_vps_keys.sh
# Helper script to securely add Kalshi credentials to the VPS and restart the bot.

KEY=$1
SECRET=$2
HOST="root@76.13.111.52"
DIR="~/Polymarket-Sports-Bot"

if [ -z "$KEY" ] || [ -z "$SECRET" ]; then
  echo "❌ Error: Missing arguments."
  echo "Usage: ./scripts/setup_vps_keys.sh <KALSHI_API_KEY> <KALSHI_API_SECRET>"
  exit 1
fi

echo "🔄 Connecting to VPS to configure Kalshi credentials..."

# SSH command to:
# 1. Go to directory
# 2. Remove existing keys if any (to avoid duplicates)
# 3. Append new keys
# 4. Restart container

ssh -o StrictHostKeyChecking=no $HOST "cd $DIR && \
  sed -i '/KALSHI_API_KEY/d' .env && \
  sed -i '/KALSHI_API_SECRET/d' .env && \
  echo 'KALSHI_API_KEY=$KEY' >> .env && \
  echo 'KALSHI_API_SECRET=$SECRET' >> .env && \
  echo '✅ Keys added to .env' && \
  docker compose -f docker-compose.vps.yml restart app && \
  echo '✅ Application restarted successfully'"

if [ $? -eq 0 ]; then
  echo "🎉 Success! The bot is now configured with your Kalshi API keys."
  echo "Verification: You should see the bot tracking games in the logs shortly."
else
  echo "❌ Error: Failed to update VPS. Please check your SSH connection."
fi
