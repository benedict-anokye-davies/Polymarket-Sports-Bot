"""
Service module exports.
Import individual modules directly to avoid dependency issues.

Example:
    from src.services.polymarket_client import PolymarketClient
    from src.services.bot_runner import BotRunner
"""

__all__ = [
    "PolymarketClient",
    "ESPNService",
    "MarketMatcher",
    "MatchResult",
    "TradingEngine",
    "PolymarketWebSocket",
    "PriceUpdate",
    "DiscordNotifier",
    "discord_notifier",
    "MarketDiscovery",
    "DiscoveredMarket",
    "market_discovery",
    "BotRunner",
    "BotState",
    "get_bot_runner",
    "get_bot_status",
    "BalanceGuardian",
    "OrderConfirmation",
    "PositionReconciler",
    "ConfidenceScorer",
    "KellyCalculator",
    "AnalyticsService",
    "AccountManager",
]


def __getattr__(name: str):
    """
    Lazy imports to avoid loading all dependencies at module import time.
    This allows the services module to work even if some dependencies
    like py_clob_client are not installed.
    """
    if name == "PolymarketClient":
        from src.services.polymarket_client import PolymarketClient
        return PolymarketClient
    elif name == "ESPNService":
        from src.services.espn_service import ESPNService
        return ESPNService
    elif name in ("MarketMatcher", "MatchResult"):
        from src.services import market_matcher
        return getattr(market_matcher, name)
    elif name == "TradingEngine":
        from src.services.trading_engine import TradingEngine
        return TradingEngine
    elif name in ("PolymarketWebSocket", "PriceUpdate"):
        from src.services import polymarket_ws
        return getattr(polymarket_ws, name)
    elif name in ("DiscordNotifier", "discord_notifier"):
        from src.services import discord_notifier as dn
        return getattr(dn, name) if name == "DiscordNotifier" else dn.discord_notifier
    elif name in ("MarketDiscovery", "DiscoveredMarket", "market_discovery"):
        from src.services import market_discovery as md
        if name == "market_discovery":
            return md.market_discovery
        return getattr(md, name)
    elif name in ("BotRunner", "BotState", "get_bot_runner", "get_bot_status"):
        from src.services import bot_runner as br
        return getattr(br, name)
    elif name == "BalanceGuardian":
        from src.services.balance_guardian import BalanceGuardian
        return BalanceGuardian
    elif name == "OrderConfirmation":
        from src.services.order_confirmation import OrderConfirmation
        return OrderConfirmation
    elif name == "PositionReconciler":
        from src.services.position_reconciler import PositionReconciler
        return PositionReconciler
    elif name == "ConfidenceScorer":
        from src.services.confidence_scorer import ConfidenceScorer
        return ConfidenceScorer
    elif name == "KellyCalculator":
        from src.services.kelly_calculator import KellyCalculator
        return KellyCalculator
    elif name == "AnalyticsService":
        from src.services.analytics_service import AnalyticsService
        return AnalyticsService
    elif name == "AccountManager":
        from src.services.account_manager import AccountManager
        return AccountManager
    
    raise AttributeError(f"module 'src.services' has no attribute '{name}'")
