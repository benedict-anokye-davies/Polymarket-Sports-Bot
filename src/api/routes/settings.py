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
from src.models.sport_config import SPORT_PROGRESS_CONFIG, ProgressMetricType


router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("/sports/progress-config")
async def get_all_sports_progress_config() -> dict:
    """
    Returns progress metric configuration for all supported sports.
    Used by frontend to render sport-specific threshold inputs.
    
    No auth required - this is static configuration data.
    """
    result = {}
    for sport, config in SPORT_PROGRESS_CONFIG.items():
        metric_type = config.get("metric_type", ProgressMetricType.TIME_COUNTDOWN)
        
        sport_info = {
            "sport": sport,
            "metric_type": metric_type.value,
            "display_name": sport.upper(),
            "segments": config.get("segments", []),
        }
        
        # Add sport-specific UI configuration
        if metric_type == ProgressMetricType.TIME_COUNTDOWN:
            sport_info["fields"] = [{
                "key": "min_time_remaining_minutes",
                "label": config.get("ui_label", "Min Time Remaining (minutes)"),
                "helper": config.get("ui_helper", ""),
                "default": config.get("default_min_time_remaining_minutes", 5),
                "min": 1,
                "max": config.get("period_duration_minutes", 15),
                "unit": "minutes",
                "type": "number",
            }]
            sport_info["total_game_minutes"] = config.get("total_game_minutes", 48)
            sport_info["period_duration_minutes"] = config.get("period_duration_minutes", 12)
            
        elif metric_type == ProgressMetricType.TIME_COUNTUP:
            sport_info["fields"] = [{
                "key": "max_elapsed_minutes",
                "label": config.get("ui_label", "Max Elapsed Minutes"),
                "helper": config.get("ui_helper", ""),
                "default": config.get("default_max_elapsed_minutes", 70),
                "min": 1,
                "max": 90,
                "unit": "minutes",
                "type": "number",
            }]
            sport_info["total_game_minutes"] = config.get("total_game_minutes", 90)
            
        elif metric_type == ProgressMetricType.INNINGS:
            sport_info["fields"] = [
                {
                    "key": "max_entry_inning",
                    "label": config.get("ui_label", "Max Entry Inning"),
                    "helper": config.get("ui_helper", ""),
                    "default": config.get("default_max_entry_inning", 6),
                    "min": 1,
                    "max": 9,
                    "unit": "inning",
                    "type": "number",
                },
                {
                    "key": "min_outs_remaining",
                    "label": config.get("secondary_label", "Min Outs Remaining"),
                    "helper": config.get("secondary_helper", ""),
                    "default": config.get("default_min_outs_remaining", 6),
                    "min": 1,
                    "max": 27,
                    "unit": "outs",
                    "type": "number",
                }
            ]
            sport_info["total_innings"] = config.get("total_innings", 9)
            
        elif metric_type == ProgressMetricType.SETS_GAMES:
            sport_info["fields"] = [
                {
                    "key": "max_entry_set",
                    "label": config.get("ui_label", "Max Entry Set"),
                    "helper": config.get("ui_helper", ""),
                    "default": config.get("default_max_entry_set", 2),
                    "min": 1,
                    "max": 5,
                    "unit": "set",
                    "type": "number",
                },
                {
                    "key": "min_sets_remaining",
                    "label": config.get("secondary_label", "Min Sets Remaining"),
                    "helper": config.get("secondary_helper", ""),
                    "default": config.get("default_min_sets_remaining", 1),
                    "min": 1,
                    "max": 3,
                    "unit": "sets",
                    "type": "number",
                }
            ]
            sport_info["max_sets"] = config.get("max_sets", 5)
            
        elif metric_type == ProgressMetricType.ROUNDS:
            sport_info["fields"] = [{
                "key": "max_entry_round",
                "label": config.get("ui_label", "Max Entry Round"),
                "helper": config.get("ui_helper", ""),
                "default": config.get("default_max_entry_round", 2),
                "min": 1,
                "max": 5,
                "unit": "round",
                "type": "number",
            }]
            sport_info["total_rounds"] = config.get("total_rounds", 3)
            sport_info["round_duration_minutes"] = config.get("round_duration_minutes", 5)
            
        elif metric_type == ProgressMetricType.HOLES:
            sport_info["fields"] = [
                {
                    "key": "max_entry_hole",
                    "label": config.get("ui_label", "Max Entry Hole"),
                    "helper": config.get("ui_helper", ""),
                    "default": config.get("default_max_entry_hole", 14),
                    "min": 1,
                    "max": 18,
                    "unit": "hole",
                    "type": "number",
                },
                {
                    "key": "min_holes_remaining",
                    "label": config.get("secondary_label", "Min Holes Remaining"),
                    "helper": config.get("secondary_helper", ""),
                    "default": config.get("default_min_holes_remaining", 4),
                    "min": 1,
                    "max": 18,
                    "unit": "holes",
                    "type": "number",
                }
            ]
            sport_info["total_holes"] = config.get("total_holes", 18)
        
        result[sport] = sport_info
    
    return result


@router.get("/sports/{sport}/threshold-config")
async def get_sport_threshold_config(
    sport: str,
    db: DbSession,
    current_user: CurrentUser
) -> dict:
    """
    Returns threshold configuration for a specific sport including current user values.
    """
    sport_lower = sport.lower()
    
    if sport_lower not in SPORT_PROGRESS_CONFIG:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported sport: {sport}"
        )
    
    config = await SportConfigCRUD.get_by_user_and_sport(db, current_user.id, sport_lower)
    
    if config:
        return config.get_ui_threshold_config()
    
    # Return defaults if no config exists
    sport_config = SPORT_PROGRESS_CONFIG[sport_lower]
    metric_type = sport_config.get("metric_type", ProgressMetricType.TIME_COUNTDOWN)
    
    return {
        "sport": sport_lower,
        "metric_type": metric_type.value,
        "primary_field": None,
        "secondary_field": None,
        "message": "No configuration exists for this sport. Create one first."
    }


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
