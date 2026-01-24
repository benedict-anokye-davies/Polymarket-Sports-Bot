"""
Onboarding flow schemas.
"""

from pydantic import BaseModel, Field


class OnboardingStatus(BaseModel):
    """
    Current state of user's onboarding progress.
    """
    current_step: int
    total_steps: int = 9
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
    Request to connect Polymarket wallet credentials.
    Private key and funder address are encrypted before storage.
    """
    private_key: str = Field(..., min_length=64, max_length=66)
    funder_address: str = Field(..., min_length=42, max_length=42)


class WalletTestResponse(BaseModel):
    """
    Response from wallet connection test.
    """
    success: bool
    message: str
    balance_usdc: float | None = None
    address: str | None = None
