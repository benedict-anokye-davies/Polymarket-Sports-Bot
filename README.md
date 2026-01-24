# Polymarket Sports Trading Bot

Automated sports betting on Polymarket prediction markets. Monitors live sports events via ESPN API and executes trades when prices hit configured thresholds.

## Quick Start

### Railway Deployment (Recommended)

1. **Push to GitHub**
   ```bash
   git add .
   git commit -m "Initial deployment"
   git push origin main
   ```

2. **Deploy on Railway**
   - Visit [railway.app](https://railway.app) and sign in with GitHub
   - Click "New Project" → "Deploy from GitHub repo"
   - Select this repository

3. **Add PostgreSQL Database**
   - In Railway project, click "+ New" → "Database" → "PostgreSQL"

4. **Configure Environment Variables**
   | Variable | Value |
   |----------|-------|
   | `DATABASE_URL` | Reference from PostgreSQL service |
   | `SECRET_KEY` | Generate: `openssl rand -hex 32` |
   | `DEBUG` | `false` |

5. **Access Your Bot**
   - Railway provides a public URL
   - Default credentials created on first registration

### Local Development

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run database migrations
alembic upgrade head

# Start development server
uvicorn src.main:app --reload --port 8000
```

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d --build

# View logs
docker-compose logs -f app

# Stop
docker-compose down
```

## Architecture

```
src/
├── api/routes/     # FastAPI endpoints
├── core/           # Security, encryption, exceptions
├── db/crud/        # Database operations
├── models/         # SQLAlchemy ORM models
├── schemas/        # Pydantic validation schemas
├── services/       # External API clients (Polymarket, ESPN)
├── static/         # CSS, JavaScript assets
└── templates/      # Jinja2 HTML templates
```

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `SECRET_KEY` | Yes | JWT signing key (min 32 chars) |
| `DEBUG` | No | Enable debug mode (default: false) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | JWT expiry (default: 15) |

### Supported Sports

- NBA (Basketball)
- NFL (Football)
- MLB (Baseball)
- NHL (Hockey)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/v1/auth/register` | POST | User registration |
| `/api/v1/auth/login` | POST | User authentication |
| `/api/v1/dashboard/stats` | GET | Trading statistics |
| `/api/v1/bot/start` | POST | Start trading bot |
| `/api/v1/bot/stop` | POST | Stop trading bot |

## Security

- All credentials encrypted at rest using Fernet symmetric encryption
- JWT authentication with configurable expiration
- Password hashing with bcrypt
- HTTPS enforced in production

## License

Proprietary - All rights reserved.
