"""
FastAPI application entry point.
Configures middleware, routes, and application lifecycle events.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
import logging

from src.config import get_settings
from src.db.database import init_db
from src.api.routes.auth import router as auth_router
from src.api.routes.onboarding import router as onboarding_router
from src.api.routes.dashboard import router as dashboard_router
from src.api.routes.settings import router as settings_router
from src.api.routes.bot import router as bot_router
from src.api.routes.trading import router as trading_router
from src.api.routes.logs import router as logs_router

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app_settings = get_settings()

logging.basicConfig(
    level=logging.DEBUG if app_settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle manager.
    Handles startup and shutdown events for database connections
    and background tasks.
    """
    logger.info("Starting Polymarket Sports Trading Bot")
    await init_db()
    yield
    logger.info("Shutting down Polymarket Sports Trading Bot")


app = FastAPI(
    title="Polymarket Sports Trading Bot",
    description="Automated sports betting on Polymarket prediction markets",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(onboarding_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(bot_router, prefix="/api/v1")
app.include_router(trading_router, prefix="/api/v1")
app.include_router(logs_router, prefix="/api/v1")

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring and load balancers.
    Returns basic application status.
    """
    return {
        "status": "healthy",
        "app": app_settings.app_name,
        "version": "1.0.0"
    }


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root endpoint redirects to login page."""
    return RedirectResponse(url="/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Renders the login page."""
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Renders the registration page."""
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/onboarding", response_class=HTMLResponse)
async def onboarding_page(request: Request):
    """Renders the onboarding page."""
    return templates.TemplateResponse("onboarding.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Renders the dashboard page."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Renders the settings page."""
    return templates.TemplateResponse("settings.html", {"request": request})


@app.get("/markets", response_class=HTMLResponse)
async def markets_page(request: Request):
    """Renders the markets page."""
    return templates.TemplateResponse("markets.html", {"request": request})


@app.get("/positions", response_class=HTMLResponse)
async def positions_page(request: Request):
    """Renders the positions page."""
    return templates.TemplateResponse("positions.html", {"request": request})


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    """Renders the trade history page."""
    return templates.TemplateResponse("history.html", {"request": request})


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """Renders the activity logs page."""
    return templates.TemplateResponse("logs.html", {"request": request})
