"""
FastAPI application entry point.
Configures middleware, routes, and application lifecycle events.
Integrates production infrastructure for monitoring, security, and observability.

Build: 2026-02-02-v5
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import logging
import asyncio

from src.config import get_settings
from src.db.database import init_db, engine, async_session_factory
# Import all models so they register with Base.metadata before init_db() creates tables
from src.models.trading_account import TradingAccount
from src.models import (
    User,
    SportConfig,
    TrackedMarket,
    Position,
    Trade,
    GlobalSettings,
    ActivityLog,
    MarketConfig,
    RefreshToken,
)
from src.api.routes.auth import router as auth_router
from src.api.routes.onboarding import router as onboarding_router
from src.api.routes.dashboard import router as dashboard_router
from src.api.routes.settings import router as settings_router
from src.api.routes.bot import router as bot_router
from src.api.routes.trading import router as trading_router
from src.api.routes.logs import router as logs_router
from src.api.routes.market_config import router as market_config_router
from src.api.routes.analytics import router as analytics_router
from src.api.routes.accounts import router as accounts_router
from src.api.routes.websocket import router as websocket_router
from src.api.routes.websocket import router as websocket_router
from src.api.routes.advanced import router as advanced_router

# Production infrastructure imports
from src.core.rate_limiter import RateLimitMiddleware, RateLimitConfig
from src.core.logging_service import (
    setup_structured_logging,
    RequestLoggingMiddleware,
    get_logger,
    log_system_event,
)
from src.core.validation import RequestValidationMiddleware, create_validation_config
from src.core.health import (
    DatabaseHealthMonitor,
    ServiceHealthAggregator,
    HealthCheckScheduler,
    HealthStatus,
)
from src.core.shutdown import ShutdownHandler, BotShutdownManager, shutdown_handler
from src.core.alerts import setup_default_alerts, alert_manager, AlertSeverity
from src.core.audit import audit_logger, AuditEventType, AuditSeverity

# Advanced infrastructure imports
from src.core.prometheus import metrics, get_prometheus_metrics, get_json_metrics
from src.core.incident_management import setup_incident_management, incident_manager
from src.core.security_headers import SecurityHeadersMiddleware, create_security_headers_config

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app_settings = get_settings()

# Configure structured JSON logging for production
if not app_settings.debug:
    setup_structured_logging(level="INFO", json_output=True)
else:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

logger = logging.getLogger(__name__)

# Initialize health monitoring
health_aggregator = ServiceHealthAggregator()
health_scheduler: HealthCheckScheduler | None = None
db_health_monitor: DatabaseHealthMonitor | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle manager.
    Handles startup and shutdown events for database connections,
    health monitoring, and background tasks.
    """
    global health_scheduler, db_health_monitor
    
    startup_time = datetime.now(timezone.utc)
    logger.info("Starting Kalshi Sports Trading Bot")
    
    # Initialize database (non-blocking - app starts even if DB fails)
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}", exc_info=True)
        # We continue, but the app might be unstable without DB
    
    # Setup database health monitoring (skip if no engine)
    try:
        if engine:
            db_health_monitor = DatabaseHealthMonitor(engine)
            health_aggregator.register_service("database", db_health_monitor.run_health_check)
    except Exception as e:
        logger.warning(f"Health monitor setup skipped: {e}")
    
    # Start health check scheduler (non-blocking)
    try:
        health_scheduler = HealthCheckScheduler(health_aggregator, interval_seconds=30)
        await health_scheduler.start()
    except Exception as e:
        logger.error(f"Health scheduler setup failed: {e}", exc_info=True)
    
    # Setup alert channels (non-blocking)
    try:
        discord_webhook = getattr(app_settings, 'discord_webhook_url', None)
        setup_default_alerts(discord_webhook)
    except Exception as e:
        logger.warning(f"Alert setup skipped: {e}")
    
    # Setup incident management providers (non-blocking)
    try:
        pagerduty_key = getattr(app_settings, 'pagerduty_routing_key', None)
        opsgenie_key = getattr(app_settings, 'opsgenie_api_key', None)
        slack_webhook = getattr(app_settings, 'slack_alert_webhook', None)
        setup_incident_management(
            pagerduty_routing_key=pagerduty_key,
            opsgenie_api_key=opsgenie_key,
            slack_webhook_url=slack_webhook,
        )
    except Exception as e:
        logger.warning(f"Incident management setup skipped: {e}")
    
    # Log system startup (non-blocking)
    try:
        await audit_logger.log_system_startup(
            version="1.0.0",
            environment="debug" if app_settings.debug else "production",
        )
    except Exception as e:
        logger.debug(f"Audit log skipped: {e}")
    
    # Send startup alert (non-blocking)
    try:
        await alert_manager.info(
            "System Started",
            f"Trading bot started successfully at {startup_time.isoformat()}",
            category="system",
        )
    except Exception as e:
        logger.debug(f"Startup alert skipped: {e}")
    
    log_system_event("startup", {"environment": "debug" if app_settings.debug else "production"})
    
    # Auto-start bot runners for users who have bot_enabled=True
    try:
        from src.db.crud.global_settings import GlobalSettingsCRUD
        from src.db.crud.account import AccountCRUD
        from src.api.routes.bot import _create_bot_dependencies, get_bot_runner

        async with async_session_factory() as startup_db:
            # Find users with bot enabled
            enabled_settings = await GlobalSettingsCRUD.get_all_enabled(startup_db)
            logger.info(f"Found {len(enabled_settings)} users with bot enabled for auto-start")

            for settings in enabled_settings:
                user_id = settings.user_id
                try:
                    credentials = await AccountCRUD.get_decrypted_credentials(startup_db, user_id)
                    if not credentials:
                        logger.warning(f"Skipping auto-start for user {user_id}: No credentials")
                        continue

                    tc, te, es = await _create_bot_dependencies(startup_db, user_id, credentials)
                    runner = await get_bot_runner(user_id, tc, te, es)
                    await runner.initialize(startup_db, user_id)

                    # Start in background task with its own database session.
                    # Do NOT pass startup_db - it will be closed when the
                    # async with block exits. The runner.start() method and its
                    # background loops already create their own sessions via
                    # async_session_factory().
                    async def _auto_start_bot(bot_runner, uid):
                        """Wrapper that gives the bot its own session for the start() call."""
                        try:
                            async with async_session_factory() as bot_db:
                                await bot_runner.start(bot_db)
                        except Exception as start_err:
                            logger.error(f"Bot runner crashed for user {uid}: {start_err}")

                    asyncio.create_task(_auto_start_bot(runner, user_id))
                    logger.info(f"Auto-started bot runner for user {user_id}")

                except Exception as user_err:
                    logger.error(f"Failed to auto-start bot for user {user_id}: {user_err}")
    except Exception as e:
        logger.error(f"Bot auto-start orchestration failed: {e}")

    yield
    
    # Graceful shutdown
    logger.info("Shutting down Kalshi Sports Trading Bot")
    
    # Stop health scheduler
    if health_scheduler:
        try:
            await health_scheduler.stop()
        except Exception:
            pass
    
    # Log shutdown
    try:
        await audit_logger.log_system_shutdown("normal")
    except Exception:
        pass
    
    log_system_event("shutdown", {"reason": "normal"})
    logger.info("Shutdown complete")


app = FastAPI(
    title="Kalshi Sports Trading Bot",
    description="Automated sports betting on Kalshi prediction markets",
    version="1.0.0",
    lifespan=lifespan,
    # Disable trailing slash redirects - they cause CORS preflight failures
    redirect_slashes=False,
)

# Production middleware stack (order matters - last added = first executed)
# All middlewares use pure ASGI implementation to avoid body consumption issues

# 1. CORS (must be outermost for preflight requests)
# Use allow_origin_regex to support wildcard subdomains (e.g., *.polymarket-sports-bot.pages.dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origins_list,
    allow_origin_regex=r"https://.*\.polymarket-sports-bot\.pages\.dev|https://polymarket-sports-bot.*\.vercel\.app|https://.*\.vercel\.app|https://.*\.up\.railway\.app",
    allow_credentials=app_settings.cors_allow_credentials,
    allow_methods=app_settings.cors_allow_methods.split(","),
    allow_headers=app_settings.cors_allow_headers.split(","),
)

# 2. Security headers (OWASP recommended headers)
security_config = create_security_headers_config(
    debug=app_settings.debug,
    allowed_origins=app_settings.cors_origins_list,
)
app.add_middleware(SecurityHeadersMiddleware, config=security_config)

# 3. Rate limiting (protect against abuse)
rate_limit_config = RateLimitConfig(
    requests_per_minute=120,  # 2 requests/second average
    requests_per_hour=3000,
    burst_limit=30,
    exempt_paths=["/health", "/health/detailed", "/health/db", "/docs", "/openapi.json", "/redoc"],
)
app.add_middleware(RateLimitMiddleware, config=rate_limit_config)

# 4. Request logging (innermost - logs after processing)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(onboarding_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(bot_router, prefix="/api/v1")
app.include_router(trading_router, prefix="/api/v1")
app.include_router(logs_router, prefix="/api/v1")
app.include_router(market_config_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(accounts_router, prefix="/api/v1")
app.include_router(websocket_router, prefix="/api/v1")
app.include_router(advanced_router)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/health")
async def health_check():
    """
    Basic health check endpoint for load balancers.
    Returns simple status without detailed diagnostics.
    """
    return {
        "status": "healthy",
        "app": app_settings.app_name,
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health/detailed")
async def detailed_health_check():
    """
    Comprehensive health check with service diagnostics.
    Returns detailed status of all monitored services.
    """
    summary = health_aggregator.get_summary()
    
    # Determine HTTP status code based on health
    status_code = 200
    if summary["overall_status"] == HealthStatus.DEGRADED.value:
        status_code = 200  # Still operational
    elif summary["overall_status"] == HealthStatus.UNHEALTHY.value:
        status_code = 503  # Service unavailable
    
    return JSONResponse(
        content={
            **summary,
            "app": app_settings.app_name,
            "version": "1.0.0",
        },
        status_code=status_code,
    )


@app.get("/health/db")
async def database_health_check():
    """
    Database-specific health check.
    Returns connection pool metrics and query latency.
    """
    if db_health_monitor is None:
        return JSONResponse(
            content={"status": "unknown", "message": "Health monitor not initialized"},
            status_code=503,
        )
    
    result = await db_health_monitor.run_health_check()
    
    status_code = 200 if result.status == HealthStatus.HEALTHY else (
        200 if result.status == HealthStatus.DEGRADED else 503
    )
    
    return JSONResponse(content=result.to_dict(), status_code=status_code)


@app.get("/metrics")
async def get_metrics():
    """
    Expose internal metrics for monitoring systems.
    Returns rate limiter, cache, and alert statistics.
    """
    from src.services.price_cache import price_cache
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "alerts": alert_manager.get_stats(),
        "price_cache": price_cache.get_cache_stats(),
        "health": health_aggregator.get_summary(),
        "incidents": incident_manager.get_stats() if incident_manager else {},
    }


@app.get("/metrics/prometheus")
async def get_prometheus_metrics_endpoint():
    """
    Prometheus-compatible metrics endpoint.
    Returns metrics in Prometheus text format for scraping.
    """
    from fastapi.responses import PlainTextResponse
    
    return PlainTextResponse(
        content=get_prometheus_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/metrics/json")
async def get_json_metrics_endpoint():
    """
    JSON format metrics endpoint.
    Returns all metrics in JSON format for custom dashboards.
    """
    return get_json_metrics()


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
