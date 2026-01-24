"""
Market configuration routes for per-market trading parameter overrides.
Allows users to set custom thresholds for specific markets.
"""

import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status, Query

from src.api.deps import DbSession, OnboardedUser
from src.db.crud.market_config import MarketConfigCRUD
from src.db.crud.sport_config import SportConfigCRUD
from src.db.crud.tracked_market import TrackedMarketCRUD
from src.schemas.trading import (
    MarketConfigCreate,
    MarketConfigUpdate,
    MarketConfigResponse,
    MarketConfigWithDefaults,
)


router = APIRouter(prefix="/market-configs", tags=["Market Configuration"])


@router.get("", response_model=list[MarketConfigResponse])
async def get_market_configs(
    db: DbSession,
    current_user: OnboardedUser,
    sport: str | None = Query(None, description="Filter by sport"),
    enabled_only: bool = Query(False, description="Return only enabled configs")
) -> list[MarketConfigResponse]:
    """
    Returns all market configurations for the user.
    Optionally filtered by sport or enabled status.
    """
    if enabled_only:
        configs = await MarketConfigCRUD.get_enabled_for_user(db, current_user.id)
    elif sport:
        configs = await MarketConfigCRUD.get_by_sport(db, current_user.id, sport)
    else:
        configs = await MarketConfigCRUD.get_all_for_user(db, current_user.id)
    
    return [MarketConfigResponse.model_validate(c) for c in configs]


@router.get("/{config_id}", response_model=MarketConfigWithDefaults)
async def get_market_config(
    config_id: uuid.UUID,
    db: DbSession,
    current_user: OnboardedUser
) -> MarketConfigWithDefaults:
    """
    Returns details for a specific market configuration.
    Includes both override values and effective values (with sport defaults).
    """
    config = await MarketConfigCRUD.get_by_id(db, config_id)
    
    if not config or config.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market configuration not found"
        )
    
    # Get sport config for defaults
    sport_config = await SportConfigCRUD.get_by_user_and_sport(
        db, current_user.id, config.sport or "nba"
    )
    
    # Calculate effective values (override or default)
    response_data = MarketConfigResponse.model_validate(config).model_dump()
    response_data.update({
        "effective_entry_threshold_drop": (
            config.entry_threshold_drop or 
            (sport_config.entry_threshold_drop if sport_config else Decimal("0.15"))
        ),
        "effective_entry_threshold_absolute": (
            config.entry_threshold_absolute or 
            (sport_config.entry_threshold_absolute if sport_config else Decimal("0.50"))
        ),
        "effective_take_profit_pct": (
            config.take_profit_pct or 
            (sport_config.take_profit_pct if sport_config else Decimal("0.20"))
        ),
        "effective_stop_loss_pct": (
            config.stop_loss_pct or 
            (sport_config.stop_loss_pct if sport_config else Decimal("0.10"))
        ),
        "effective_position_size_usdc": (
            config.position_size_usdc or 
            (sport_config.position_size_usdc if sport_config else Decimal("50.00"))
        ),
        "effective_min_time_remaining_seconds": (
            config.min_time_remaining_seconds or 
            (sport_config.min_time_remaining_seconds if sport_config else 300)
        ),
        "effective_max_positions": (
            config.max_positions or 
            (sport_config.max_positions_per_game if sport_config else 1)
        ),
    })
    
    return MarketConfigWithDefaults(**response_data)


@router.get("/by-market/{condition_id}", response_model=MarketConfigResponse | None)
async def get_config_by_market(
    condition_id: str,
    db: DbSession,
    current_user: OnboardedUser
) -> MarketConfigResponse | None:
    """
    Returns market configuration for a specific market by condition_id.
    Returns null if no custom configuration exists.
    """
    config = await MarketConfigCRUD.get_by_condition_id(db, current_user.id, condition_id)
    
    if not config:
        return None
    
    return MarketConfigResponse.model_validate(config)


@router.post("", response_model=MarketConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_market_config(
    config_data: MarketConfigCreate,
    db: DbSession,
    current_user: OnboardedUser
) -> MarketConfigResponse:
    """
    Creates a new market configuration override.
    
    This allows setting custom entry/exit thresholds and position
    sizing for a specific market, overriding the sport-level defaults.
    """
    # Check if market exists in tracked markets (optional but helpful)
    tracked = await TrackedMarketCRUD.get_by_condition_id(
        db, current_user.id, config_data.condition_id
    )
    
    # Auto-populate market info if tracked
    create_kwargs = config_data.model_dump(exclude_unset=True)
    if tracked and not config_data.market_question:
        create_kwargs.update({
            "market_question": tracked.question,
            "sport": tracked.sport,
            "home_team": tracked.home_team,
            "away_team": tracked.away_team,
        })
    
    try:
        config = await MarketConfigCRUD.create(
            db,
            user_id=current_user.id,
            **create_kwargs
        )
        return MarketConfigResponse.model_validate(config)
    except Exception as e:
        if "already exists" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Configuration for market {config_data.condition_id} already exists"
            )
        raise


@router.put("/{config_id}", response_model=MarketConfigResponse)
async def update_market_config(
    config_id: uuid.UUID,
    config_data: MarketConfigUpdate,
    db: DbSession,
    current_user: OnboardedUser
) -> MarketConfigResponse:
    """
    Updates an existing market configuration.
    Only provided fields are updated; others remain unchanged.
    """
    try:
        config = await MarketConfigCRUD.update(
            db,
            config_id=config_id,
            user_id=current_user.id,
            **config_data.model_dump(exclude_unset=True)
        )
        return MarketConfigResponse.model_validate(config)
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Market configuration not found"
            )
        raise


@router.put("/by-market/{condition_id}", response_model=MarketConfigResponse)
async def upsert_market_config(
    condition_id: str,
    config_data: MarketConfigUpdate,
    db: DbSession,
    current_user: OnboardedUser
) -> MarketConfigResponse:
    """
    Creates or updates market configuration by condition_id.
    Convenient endpoint for setting overrides from the markets page.
    """
    # Get tracked market info for auto-population
    tracked = await TrackedMarketCRUD.get_by_condition_id(db, current_user.id, condition_id)
    
    upsert_kwargs = config_data.model_dump(exclude_unset=True)
    if tracked:
        upsert_kwargs.setdefault("market_question", tracked.question)
        upsert_kwargs.setdefault("sport", tracked.sport)
        upsert_kwargs.setdefault("home_team", tracked.home_team)
        upsert_kwargs.setdefault("away_team", tracked.away_team)
    
    config = await MarketConfigCRUD.upsert(
        db,
        user_id=current_user.id,
        condition_id=condition_id,
        **upsert_kwargs
    )
    return MarketConfigResponse.model_validate(config)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_market_config(
    config_id: uuid.UUID,
    db: DbSession,
    current_user: OnboardedUser
) -> None:
    """
    Deletes a market configuration.
    The market will revert to using sport-level defaults.
    """
    deleted = await MarketConfigCRUD.delete(db, config_id, current_user.id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market configuration not found"
        )


@router.delete("/by-market/{condition_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_config_by_market(
    condition_id: str,
    db: DbSession,
    current_user: OnboardedUser
) -> None:
    """
    Deletes market configuration by condition_id.
    The market will revert to using sport-level defaults.
    """
    deleted = await MarketConfigCRUD.delete_by_condition_id(
        db, current_user.id, condition_id
    )
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market configuration not found"
        )


@router.post("/{config_id}/toggle", response_model=MarketConfigResponse)
async def toggle_market_config(
    config_id: uuid.UUID,
    db: DbSession,
    current_user: OnboardedUser
) -> MarketConfigResponse:
    """
    Toggles the enabled status of a market configuration.
    Disabled markets won't be traded by the bot.
    """
    config = await MarketConfigCRUD.get_by_id(db, config_id)
    
    if not config or config.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market configuration not found"
        )
    
    updated = await MarketConfigCRUD.update(
        db,
        config_id=config_id,
        user_id=current_user.id,
        enabled=not config.enabled
    )
    return MarketConfigResponse.model_validate(updated)
