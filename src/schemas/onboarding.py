"""
Onboarding flow schemas.
"""

from pydantic import BaseModel, Field


class OnboardingStatus(BaseModel):
    """
    Current state of user's onboarding progress.
    """
    current_step: int
    total_steps: int = 5  # Frontend has 5 onboarding steps
    completed_steps: list[int]
    can_proceed: bool
    wallet_connected: bool


class OnboardingStepData(BaseModel):
    """
    Details for a specific onboarding step.
    """
    step_number: int
    title: str
    description: str
    is_completed: bool
    requires_input: bool
    input_fields: list[str] | None = None


class WalletConnectRequest(BaseModel):
    """
    Request to connect trading platform credentials.
    Supports both Kalshi and Polymarket platforms.
    All sensitive data is encrypted before storage.
    """
    platform: str = Field(default="kalshi", description="Platform: 'kalshi' or 'polymarket'")
    # Kalshi credentials
    api_key: str | None = Field(default=None, description="Kalshi API Key")
    api_secret: str | None = Field(default=None, description="Kalshi API Secret")
    # Polymarket credentials (optional - only needed for Polymarket)
    private_key: str | None = Field(default=None, min_length=64, max_length=66, description="Polymarket private key")
    funder_address: str | None = Field(default=None, description="Polymarket wallet address")


class WalletTestResponse(BaseModel):
    """
    Response from wallet connection test.
    """
    success: bool
    message: str
    balance_usdc: float | None = None
    address: str | None = None
