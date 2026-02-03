# Sports Trading Bot

Automated sports betting on Kalshi prediction markets. Monitors live sports events via ESPN API and executes trades when prices hit configured thresholds.

## Features

- **Platform**: Exclusive Kalshi market support
- **Live Game Monitoring**: Real-time ESPN game state tracking
- **Live Trading**: Execute real-money trades on Kalshi Production
- **Paper Trading**: Test strategies with simulation mode
- **Configurable Thresholds**: Set entry/exit prices per sport
- **Multi-Account**: Manage multiple exchange accounts
- **Position Tracking**: Monitor open positions and P&L

## Supported Sports

- NBA (Basketball)
- NFL (Football)  
- MLB (Baseball)
- NHL (Hockey)

## Deployment

### Backend (Railway)

1. Push to GitHub
2. Connect repository to Railway
3. Add PostgreSQL database (Auto-injected `DATABASE_URL`)
4. Set environment variables:
   - `SECRET_KEY` - JWT signing key
   - `ENCRYPTION_KEY` - Key for encrypting API credentials

### Frontend (Vercel)

1. Connect GitHub repository
2. Set build settings:
   - Framework Preset: Vite
   - Build command: `npm run build`
   - Output directory: `dist`
3. Set environment variable:
   - `VITE_API_URL` - Backend URL (Railway App URL)

## Local Development

```bash
# Backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn src.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## License

Proprietary - All rights reserved.
