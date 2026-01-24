"""
Pydantic schema exports.
"""

from src.schemas.auth import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
)
from src.schemas.common import (
    MessageResponse,
    PaginatedResponse,
    ErrorResponse,
)
from src.schemas.onboarding import (
    OnboardingStatus,
    OnboardingStepData,
    WalletConnectRequest,
    WalletTestResponse,
)
from src.schemas.dashboard import (
    DashboardStats,
    PositionSummary,
    RecentActivity,
)
from src.schemas.settings import (
    SportConfigCreate,
    SportConfigUpdate,
    SportConfigResponse,
    GlobalSettingsUpdate,
    GlobalSettingsResponse,
)
from src.schemas.trading import (
    TrackedMarketResponse,
    PositionResponse,
    TradeResponse,
    OrderRequest,
    OrderResponse,
)

__all__ = [
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "TokenResponse",
    "MessageResponse",
    "PaginatedResponse",
    "ErrorResponse",
    "OnboardingStatus",
    "OnboardingStepData",
    "WalletConnectRequest",
    "WalletTestResponse",
    "DashboardStats",
    "PositionSummary",
    "RecentActivity",
    "SportConfigCreate",
    "SportConfigUpdate",
    "SportConfigResponse",
    "GlobalSettingsUpdate",
    "GlobalSettingsResponse",
    "TrackedMarketResponse",
    "PositionResponse",
    "TradeResponse",
    "OrderRequest",
    "OrderResponse",
]
