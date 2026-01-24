"""
API route module exports.
"""

from src.api.routes.auth import router as auth_router
from src.api.routes.onboarding import router as onboarding_router
from src.api.routes.dashboard import router as dashboard_router
from src.api.routes.settings import router as settings_router
from src.api.routes.bot import router as bot_router
from src.api.routes.trading import router as trading_router
from src.api.routes.logs import router as logs_router

__all__ = [
    "auth_router",
    "onboarding_router",
    "dashboard_router",
    "settings_router",
    "bot_router",
    "trading_router",
    "logs_router",
]
