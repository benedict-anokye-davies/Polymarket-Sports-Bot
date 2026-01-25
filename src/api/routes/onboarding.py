"""
Onboarding routes for guiding users through initial setup.
"""

from fastapi import APIRouter, HTTPException, status

from src.api.deps import DbSession, CurrentUser
from src.db.crud.user import UserCRUD
from src.db.crud.polymarket_account import PolymarketAccountCRUD
from src.db.crud.activity_log import ActivityLogCRUD
from src.schemas.onboarding import (
    OnboardingStatus,
    OnboardingStepData,
    WalletConnectRequest,
    WalletTestResponse,
)
from src.schemas.common import MessageResponse


router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


TOTAL_ONBOARDING_STEPS = 3

ONBOARDING_STEPS = [
    OnboardingStepData(
        step_number=1,
        title="Welcome",
        description="Introduction to the Polymarket trading bot",
        is_completed=False,
        requires_input=False
    ),
    OnboardingStepData(
        step_number=2,
        title="Connect Wallet",
        description="Enter your Polymarket API credentials",
        is_completed=False,
        requires_input=True,
        input_fields=["api_key", "api_secret", "api_passphrase", "funder_address"]
    ),
    OnboardingStepData(
        step_number=3,
        title="Risk Management",
        description="Set daily loss limits and max exposure",
        is_completed=False,
        requires_input=True,
        input_fields=["max_daily_loss", "max_exposure"]
    ),
]


@router.get("/status", response_model=OnboardingStatus)
async def get_onboarding_status(db: DbSession, current_user: CurrentUser) -> OnboardingStatus:
    """
    Returns the current state of user's onboarding progress.
    """
    wallet_connected = await PolymarketAccountCRUD.get_by_user_id(db, current_user.id) is not None
    
    completed_steps = list(range(1, current_user.onboarding_step))
    
    return OnboardingStatus(
        current_step=current_user.onboarding_step,
        completed_steps=completed_steps,
        can_proceed=True,
        wallet_connected=wallet_connected
    )


@router.get("/step/{step_number}", response_model=OnboardingStepData)
async def get_step_details(step_number: int, current_user: CurrentUser) -> OnboardingStepData:
    """
    Returns details for a specific onboarding step.
    """
    if step_number < 1 or step_number > TOTAL_ONBOARDING_STEPS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid step number"
        )
    
    step = ONBOARDING_STEPS[step_number - 1].model_copy()
    step.is_completed = step_number < current_user.onboarding_step
    
    return step


@router.post("/step/{step_number}/complete", response_model=MessageResponse)
async def complete_step(
    step_number: int,
    db: DbSession,
    current_user: CurrentUser
) -> MessageResponse:
    """
    Marks an onboarding step as complete and advances to the next step.
    Allows completing any step to support flexible onboarding flows.
    """
    if step_number < 1 or step_number > TOTAL_ONBOARDING_STEPS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid step number. Must be between 1 and {TOTAL_ONBOARDING_STEPS}"
        )
    
    next_step = step_number + 1
    completed = next_step > TOTAL_ONBOARDING_STEPS
    
    await UserCRUD.update_onboarding_step(db, current_user.id, next_step, completed)
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "ONBOARDING",
        f"Completed onboarding step {step_number}"
    )
    
    if completed:
        return MessageResponse(message="Onboarding complete! You can now use the trading bot.")
    
    return MessageResponse(message=f"Step {step_number} complete. Proceed to step {next_step}.")


@router.post("/wallet/connect", response_model=MessageResponse)
async def connect_wallet(
    wallet_data: WalletConnectRequest,
    db: DbSession,
    current_user: CurrentUser
) -> MessageResponse:
    """
    Stores encrypted wallet credentials.
    """
    existing = await PolymarketAccountCRUD.get_by_user_id(db, current_user.id)
    
    if existing:
        await PolymarketAccountCRUD.delete(db, current_user.id)
    
    await PolymarketAccountCRUD.create(
        db,
        user_id=current_user.id,
        private_key=wallet_data.private_key,
        funder_address=wallet_data.funder_address
    )
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "WALLET",
        "Wallet credentials stored successfully"
    )
    
    return MessageResponse(message="Wallet credentials stored successfully")


@router.post("/wallet/test", response_model=WalletTestResponse)
async def test_wallet_connection(
    db: DbSession,
    current_user: CurrentUser
) -> WalletTestResponse:
    """
    Tests connection to Polymarket using stored credentials.
    Verifies credentials are valid and returns balance.
    """
    credentials = await PolymarketAccountCRUD.get_decrypted_credentials(db, current_user.id)
    
    if not credentials:
        return WalletTestResponse(
            success=False,
            message="No wallet credentials found. Please connect wallet first."
        )
    
    try:
        from src.services.polymarket_client import PolymarketClient
        
        client = PolymarketClient(
            private_key=credentials["private_key"],
            funder_address=credentials["funder_address"]
        )
        
        balance = await client.get_balance()
        
        await PolymarketAccountCRUD.update_connection_status(db, current_user.id, True)
        
        await ActivityLogCRUD.info(
            db,
            current_user.id,
            "WALLET",
            f"Wallet connection test successful. Balance: {balance} USDC"
        )
        
        return WalletTestResponse(
            success=True,
            message="Connection successful",
            balance_usdc=float(balance),
            address=credentials["funder_address"]
        )
        
    except Exception as e:
        await PolymarketAccountCRUD.update_connection_status(
            db, current_user.id, False, str(e)
        )
        
        await ActivityLogCRUD.error(
            db,
            current_user.id,
            "WALLET",
            f"Wallet connection test failed: {str(e)}"
        )
        
        return WalletTestResponse(
            success=False,
            message=f"Connection failed: {str(e)}"
        )


@router.post("/complete", response_model=MessageResponse)
async def complete_onboarding(
    db: DbSession,
    current_user: CurrentUser
) -> MessageResponse:
    """
    Completes the onboarding process manually.
    """
    await UserCRUD.update_onboarding_step(db, current_user.id, 10, True)
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "ONBOARDING",
        "User completed onboarding"
    )
    
    return MessageResponse(
        message="Onboarding completed successfully",
        success=True
    )


@router.post("/skip", response_model=MessageResponse)
async def skip_onboarding(
    db: DbSession,
    current_user: CurrentUser
) -> MessageResponse:
    """
    Allows user to skip onboarding. Not recommended.
    Bot will not function without wallet credentials.
    """
    await UserCRUD.update_onboarding_step(db, current_user.id, 10, True)
    
    await ActivityLogCRUD.warning(
        db,
        current_user.id,
        "ONBOARDING",
        "User skipped onboarding"
    )
    
    return MessageResponse(
        message="Onboarding skipped. Please configure settings before enabling the bot.",
        success=True
    )
