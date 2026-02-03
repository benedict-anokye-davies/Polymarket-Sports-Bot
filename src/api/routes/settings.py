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
    BulkLeagueConfigRequest,
    BulkLeagueConfigResponse,
    LeagueEnableRequest,
    LeagueEnableResponse,
    UserLeagueStatus,
    LEAGUE_SPORT_TYPE_MAP,
    ALL_SUPPORTED_LEAGUES,
)
from src.schemas.common import MessageResponse
from src.models.sport_config import SPORT_PROGRESS_CONFIG, ProgressMetricType
from src.services.espn_service import ESPNService


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


# ============================================================================
# Bulk League Configuration Endpoints
# ============================================================================

@router.post("/leagues/bulk", response_model=BulkLeagueConfigResponse)
async def bulk_configure_leagues(
    config_data: BulkLeagueConfigRequest,
    db: DbSession,
    current_user: CurrentUser
) -> BulkLeagueConfigResponse:
    """
    Configure multiple leagues at once with the same parameters.
    
    Use this to quickly set up trading for multiple leagues (e.g., all European
    soccer leagues) with identical settings. Each league will get its own
    config entry that can be customized later if needed.
    
    Example request:
    ```json
    {
        "leagues": ["epl", "laliga", "bundesliga", "seriea", "ucl"],
        "enabled": true,
        "entry_threshold_drop": 0.15,
        "position_size_usdc": 50.00,
        "take_profit_pct": 0.20
    }
    ```
    """
    configured = []
    failed = []
    
    for league in config_data.leagues:
        league_lower = league.lower()
        
        # Validate league exists
        if league_lower not in LEAGUE_SPORT_TYPE_MAP:
            failed.append(league)
            continue
        
        # Get sport type for defaults
        sport_type = LEAGUE_SPORT_TYPE_MAP[league_lower]
        
        # Prepare config data
        config_dict = config_data.model_dump(exclude={"leagues"})
        config_dict["sport"] = league_lower
        
        # Apply sport-type-specific defaults
        sport_defaults = SPORT_PROGRESS_CONFIG.get(sport_type, {})
        metric_type = sport_defaults.get("metric_type", ProgressMetricType.TIME_COUNTDOWN)
        
        if metric_type == ProgressMetricType.TIME_COUNTUP:
            # Soccer - use max_elapsed_minutes
            config_dict["min_time_remaining_seconds"] = 0
        else:
            # Other sports - use min_time_remaining_minutes
            minutes = config_dict.get("min_time_remaining_minutes", 5)
            config_dict["min_time_remaining_seconds"] = minutes * 60
        
        try:
            # Check if config exists
            existing = await SportConfigCRUD.get_by_user_and_sport(
                db, current_user.id, league_lower
            )
            
            if existing:
                # Update existing config
                await SportConfigCRUD.update(db, existing.id, **config_dict)
            else:
                # Create new config
                await SportConfigCRUD.create(
                    db,
                    user_id=current_user.id,
                    **config_dict
                )
            
            configured.append(league_lower)
            
        except Exception as e:
            failed.append(f"{league}: {str(e)}")
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "SETTINGS",
        f"Bulk configured {len(configured)} leagues"
    )
    
    return BulkLeagueConfigResponse(
        success=len(failed) == 0,
        configured_leagues=configured,
        failed_leagues=failed,
        message=f"Configured {len(configured)} leagues" + 
                (f", {len(failed)} failed" if failed else "")
    )


@router.post("/leagues/enable", response_model=LeagueEnableResponse)
async def bulk_enable_leagues(
    request: LeagueEnableRequest,
    db: DbSession,
    current_user: CurrentUser
) -> LeagueEnableResponse:
    """
    Enable or disable multiple leagues at once without changing other settings.
    
    Use this for quick toggling when you want to temporarily disable
    certain leagues (e.g., during off-season).
    """
    updated = []
    
    for league in request.leagues:
        league_lower = league.lower()
        
        config = await SportConfigCRUD.get_by_user_and_sport(
            db, current_user.id, league_lower
        )
        
        if config:
            await SportConfigCRUD.update(db, config.id, enabled=request.enabled)
            updated.append(league_lower)
    
    action = "enabled" if request.enabled else "disabled"
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "SETTINGS",
        f"Bulk {action} {len(updated)} leagues"
    )
    
    return LeagueEnableResponse(
        success=True,
        updated_leagues=updated,
        message=f"{action.capitalize()} {len(updated)} leagues"
    )


@router.get("/leagues/status", response_model=UserLeagueStatus)
async def get_user_league_status(
    db: DbSession,
    current_user: CurrentUser
) -> UserLeagueStatus:
    """
    Returns all available leagues with their configuration status for the user.
    
    Shows which leagues the user has configured, which are enabled,
    and basic config info for each.
    """
    from src.schemas.settings import UserLeagueConfig, LeagueInfo
    
    # Get all user's sport configs
    user_configs = await SportConfigCRUD.get_all_for_user(db, current_user.id)
    config_map = {c.sport: c for c in user_configs}
    
    # Get league display names from ESPN service
    league_names = ESPNService.LEAGUE_DISPLAY_NAMES
    
    configured_leagues = []
    available_leagues = []
    enabled_count = 0
    
    for league_id, sport_type in LEAGUE_SPORT_TYPE_MAP.items():
        config = config_map.get(league_id)
        display_name = league_names.get(league_id, league_id.upper())
        
        if config:
            # User has configured this league
            configured_leagues.append(UserLeagueConfig(
                league_key=league_id,
                enabled=config.enabled,
                entry_threshold_drop=config.entry_threshold_drop,
                entry_threshold_absolute=config.entry_threshold_absolute,
                take_profit_pct=config.take_profit_pct,
                stop_loss_pct=config.stop_loss_pct,
                position_size_usdc=config.position_size_usdc,
                min_time_remaining_seconds=int(config.min_time_remaining_seconds) if config.min_time_remaining_seconds else None,
                max_positions=int(config.max_total_positions) if config.max_total_positions else None,
            ))
            if config.enabled:
                enabled_count += 1
        else:
            # League is available but not configured
            available_leagues.append(LeagueInfo(
                league_key=league_id,
                display_name=display_name,
                sport_type=sport_type,
            ))
    
    # Sort configured leagues: enabled first, then alphabetically
    configured_leagues.sort(key=lambda x: (not x.enabled, x.league_key))
    # Sort available leagues alphabetically
    available_leagues.sort(key=lambda x: x.display_name)
    
    return UserLeagueStatus(
        configured_leagues=configured_leagues,
        available_leagues=available_leagues,
        enabled_count=enabled_count,
        total_available=len(LEAGUE_SPORT_TYPE_MAP)
    )


@router.delete("/leagues/{league}")
async def delete_league_config(
    league: str,
    db: DbSession,
    current_user: CurrentUser
) -> MessageResponse:
    """
    Deletes a specific league configuration.
    """
    config = await SportConfigCRUD.get_by_user_and_sport(db, current_user.id, league.lower())
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration for {league} not found"
        )
    
    await SportConfigCRUD.delete(db, config.id)
    
    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "SETTINGS",
        f"Deleted {league} configuration"
    )
    
    return MessageResponse(message=f"Deleted {league} configuration")


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


# ============================================================================
# Wallet/Credential Management Endpoints
# ============================================================================

from src.db.crud.polymarket_account import PolymarketAccountCRUD
from src.core.encryption import decrypt_credential
from src.schemas.settings import WalletStatusResponse, WalletUpdateRequest


@router.get("/wallet", response_model=WalletStatusResponse)
async def get_wallet_status(
    db: DbSession,
    current_user: CurrentUser
) -> WalletStatusResponse:
    """
    Returns wallet connection status without exposing raw credentials.
    Shows masked identifier and connection status.
    """
    account = await PolymarketAccountCRUD.get_by_user_id(db, current_user.id)

    if not account:
        return WalletStatusResponse(
            is_connected=False,
            platform=None,
            masked_identifier=None,
            last_tested_at=None,
            connection_error=None
        )

    # Mask the identifier based on platform
    masked = None
    try:
        if account.platform == "kalshi" and account.api_key_encrypted:
            decrypted = decrypt_credential(account.api_key_encrypted)
            if decrypted and len(decrypted) > 4:
                masked = f"{'*' * (len(decrypted) - 4)}{decrypted[-4:]}"
            else:
                masked = "****"
        elif account.platform == "polymarket" and account.funder_address:
            addr = account.funder_address
            if len(addr) > 10:
                masked = f"{addr[:6]}...{addr[-4:]}"
            else:
                masked = addr
    except Exception:
        masked = "****"

    return WalletStatusResponse(
        is_connected=account.is_connected,
        platform=account.platform,
        masked_identifier=masked,
        last_tested_at=account.updated_at,
        connection_error=getattr(account, 'connection_error', None)
    )


@router.put("/wallet", response_model=WalletStatusResponse)
async def update_wallet_credentials(
    wallet_data: WalletUpdateRequest,
    db: DbSession,
    current_user: CurrentUser
) -> WalletStatusResponse:
    """
    Updates wallet credentials for the user.
    Encrypts credentials before storing.
    """
    from src.core.encryption import encrypt_credential

    account = await PolymarketAccountCRUD.get_by_user_id(db, current_user.id)

    update_data = {"platform": wallet_data.platform}

    if wallet_data.platform == "kalshi":
        if wallet_data.api_key:
            update_data["api_key_encrypted"] = encrypt_credential(wallet_data.api_key)
        if wallet_data.api_secret:
            from src.services.kalshi_client import KalshiClient
            is_valid, error_msg, formatted_key = KalshiClient.validate_rsa_key(wallet_data.api_secret)
            
            if not is_valid:
                # Early return or raise? Better to raise to inform user
                from fastapi import HTTPException
                raise HTTPException(status_code=400, detail=f"Invalid RSA Key: {error_msg}")
            
            # Use the clean, formatted key
            update_data["api_secret_encrypted"] = encrypt_credential(formatted_key)
        # Clear polymarket fields
        update_data["private_key_encrypted"] = None
        update_data["funder_address"] = None
    else:  # polymarket
        if wallet_data.private_key:
            update_data["private_key_encrypted"] = encrypt_credential(wallet_data.private_key)
        if wallet_data.funder_address:
            update_data["funder_address"] = wallet_data.funder_address
        # Clear kalshi fields
        update_data["api_key_encrypted"] = None
        update_data["api_secret_encrypted"] = None

    update_data["is_connected"] = True

    if account:
        # Update existing account
        await PolymarketAccountCRUD.update(db, account.id, **update_data)
    else:
        # Create new account
        await PolymarketAccountCRUD.create(db, user_id=current_user.id, **update_data)

    await ActivityLogCRUD.info(
        db,
        current_user.id,
        "WALLET",
        f"Updated {wallet_data.platform} credentials"
    )

    # Return updated status
    return await get_wallet_status(db, current_user)
