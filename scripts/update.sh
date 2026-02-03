#!/bin/bash

# VPS Update Script
# Usage: ./scripts/update.sh

echo "=========================================="
echo "Updating Sports Trading Bot..."
echo "=========================================="

# 1. Pull latest code
echo "[1/3] Pulling latest code from GitHub..."
git pull origin master

# 2. Rebuild and restart containers
echo "[2/3] Rebuilding and restarting Docker containers..."
# Use the VPS-specific compose file
docker compose -f docker-compose.vps.yml up -d --build

# 3. Clean up unused images (optional, helps save space)
echo "[3/3] Cleaning up old images..."
docker image prune -f

echo "=========================================="
echo "Update Complete! 🚀"
echo "=========================================="
echo "Active Containers:"
docker ps
