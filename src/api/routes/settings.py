"""
Settings routes for sport configs and global settings.
"""

import uuid

from fastapi import APIRouter, HTTPException, status

from src.api.deps import DbSession, CurrentUser
from src.db.crud.sport_config import SportConfigCRUD
from src.db.crud.global_settings import GlobalSettingsCRUD
from src.db.crud.activity_log import ActivityLogCRUD
from src.schemas.settings import (
    SportConfigCreate,
    SportConfigUpdate,
    SportConfigResponse,
    GlobalSettingsUpdate,
    GlobalSettingsResponse,
)
from src.schemas.common import MessageResponse


router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("/sports", response_model=list[SportConfigResponse])
async def get_all_sport_configs(
    db: DbSession,
    current_user: CurrentUser
) -> list[SportConfigResponse]:
    """
    Returns all sport configurations for the user.
    """
    configs = await SportConfigCRUD.get_all_for_user(db, current_user.id)
    return [SportConfigResponse.model_validate(c) for c in configs]


@router.get("/sports/{sport}", response_model=SportConfigResponse)
async def get_sport_config(
    sport: str,
    db: DbSession,
    current_user: CurrentUser
) -> SportConfigResponse:
    """
    Returns configuration for a specific sport.
    """
    config = await SportConfigCRUD.get_by_user_and_sport(db, current_user.id, sport)
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration for {sport} not found"
        )
    
    return SportConfigResponse.model_validate(config)


@router.put("/sports/{sport}", response_model=SportConfigResponse)
async def update_sport_config(
    sport: str,
    config_data: SportConfigUpdate,
    db: DbSession,
    current_user: CurrentUser
) -> SportConfigResponse:
    """
    Updates configuration for a specific sport.
    """
    config = await SportConfigCRUD.get_by_user_and_sport(db, current_user.id, sport)
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration for {sport} not found"
        )
    
    updated = await SportConfigCRUD.update(
        db,
        config.id,
        **config_data.model_dump(exclude_unset=True)
    )
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "SETTINGS",
        f"Updated {sport} configuration"
    )
    
    return SportConfigResponse.model_validate(updated)


@router.post("/sports", response_model=SportConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_sport_config(
    config_data: SportConfigCreate,
    db: DbSession,
    current_user: CurrentUser
) -> SportConfigResponse:
    """
    Creates a new sport configuration.
    """
    try:
        config = await SportConfigCRUD.create(
            db,
            user_id=current_user.id,
            **config_data.model_dump()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "SETTINGS",
        f"Created {config_data.sport} configuration"
    )
    
    return SportConfigResponse.model_validate(config)


@router.get("/global", response_model=GlobalSettingsResponse)
async def get_global_settings(
    db: DbSession,
    current_user: CurrentUser
) -> GlobalSettingsResponse:
    """
    Returns global bot settings for the user.
    """
    settings = await GlobalSettingsCRUD.get_or_create(db, current_user.id)
    return GlobalSettingsResponse.model_validate(settings)


@router.put("/global", response_model=GlobalSettingsResponse)
async def update_global_settings(
    settings_data: GlobalSettingsUpdate,
    db: DbSession,
    current_user: CurrentUser
) -> GlobalSettingsResponse:
    """
    Updates global bot settings.
    """
    settings = await GlobalSettingsCRUD.update(
        db,
        current_user.id,
        **settings_data.model_dump(exclude_unset=True)
    )
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "SETTINGS",
        "Updated global settings"
    )
    
    return GlobalSettingsResponse.model_validate(settings)


@router.post("/discord/test", response_model=MessageResponse)
async def test_discord_webhook(
    db: DbSession,
    current_user: CurrentUser
) -> MessageResponse:
    """
    Sends a test message to the configured Discord webhook.
    """
    settings = await GlobalSettingsCRUD.get_by_user_id(db, current_user.id)
    
    if not settings or not settings.discord_webhook_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discord webhook URL not configured"
        )
    
    try:
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.discord_webhook_url,
                json={"content": "Test message from Polymarket Trading Bot"}
            )
            response.raise_for_status()
        
        await ActivityLogCRUD.info(
            db,
            current_user.id,
            "DISCORD",
            "Discord webhook test successful"
        )
        
        return MessageResponse(message="Test message sent successfully")
        
    except Exception as e:
        await ActivityLogCRUD.error(
            db,
            current_user.id,
            "DISCORD",
            f"Discord webhook test failed: {str(e)}"
        )
        
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to send test message: {str(e)}"
        )
