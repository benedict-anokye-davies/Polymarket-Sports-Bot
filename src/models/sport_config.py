"""
Sport configuration model for per-sport trading parameters.
Each user can have different settings for NBA, NFL, MLB, NHL, Tennis, Soccer, MMA, Golf.

Progress Metrics by Sport:
- NBA/NFL/NHL: Time-based (minutes remaining in period/game)
- MLB: Innings-based (current inning, outs remaining)
- Tennis: Sets/Games-based (sets won, games in current set)
- Soccer: Time-based but clock counts UP (minutes elapsed)
- MMA/UFC: Rounds-based (current round, time in round)
- Golf: Holes-based (holes completed)
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from sqlalchemy import String, Boolean, Integer, DateTime, Numeric, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from src.db.database import Base


class ProgressMetricType(str, Enum):
    """
    Defines how game progress is measured for different sports.
    """
    TIME_COUNTDOWN = "time_countdown"   # NBA, NFL, NHL - clock counts down
    TIME_COUNTUP = "time_countup"       # Soccer - clock counts up
    INNINGS = "innings"                  # MLB - innings and outs
    SETS_GAMES = "sets_games"           # Tennis - sets and games
    ROUNDS = "rounds"                    # MMA/UFC - rounds
    HOLES = "holes"                      # Golf - holes completed


# Sport-specific defaults and metadata
SPORT_PROGRESS_CONFIG = {
    "nba": {
        "metric_type": ProgressMetricType.TIME_COUNTDOWN,
        "total_periods": 4,
        "period_duration_minutes": 12,
        "total_game_minutes": 48,
        "segments": ["q1", "q2", "q3", "q4", "ot"],
        "default_min_time_remaining_minutes": 5,
        "default_max_entry_segment": "q3",
        "ui_label": "Min Time Remaining (minutes)",
        "ui_helper": "Minimum minutes left in period to enter trade",
    },
    "nfl": {
        "metric_type": ProgressMetricType.TIME_COUNTDOWN,
        "total_periods": 4,
        "period_duration_minutes": 15,
        "total_game_minutes": 60,
        "segments": ["q1", "q2", "q3", "q4", "ot"],
        "default_min_time_remaining_minutes": 5,
        "default_max_entry_segment": "q3",
        "ui_label": "Min Time Remaining (minutes)",
        "ui_helper": "Minimum minutes left in quarter to enter trade",
    },
    "nhl": {
        "metric_type": ProgressMetricType.TIME_COUNTDOWN,
        "total_periods": 3,
        "period_duration_minutes": 20,
        "total_game_minutes": 60,
        "segments": ["p1", "p2", "p3", "ot"],
        "default_min_time_remaining_minutes": 5,
        "default_max_entry_segment": "p2",
        "ui_label": "Min Time Remaining (minutes)",
        "ui_helper": "Minimum minutes left in period to enter trade",
    },
    "mlb": {
        "metric_type": ProgressMetricType.INNINGS,
        "total_innings": 9,
        "outs_per_half_inning": 3,
        "segments": [f"inning_{i}" for i in range(1, 13)],
        "default_max_entry_inning": 6,
        "default_min_outs_remaining": 6,  # ~2 innings worth of outs
        "ui_label": "Max Entry Inning",
        "ui_helper": "Latest inning to enter a trade (1-9)",
        "secondary_label": "Min Outs Remaining",
        "secondary_helper": "Minimum outs left in game (27 total in 9 innings)",
    },
    "tennis": {
        "metric_type": ProgressMetricType.SETS_GAMES,
        "max_sets": 5,  # Grand slam men's
        "games_to_win_set": 6,
        "segments": ["set_1", "set_2", "set_3", "set_4", "set_5"],
        "default_max_entry_set": 2,
        "default_min_sets_remaining": 1,
        "ui_label": "Max Entry Set",
        "ui_helper": "Latest set number to enter a trade (1-5)",
        "secondary_label": "Min Sets Remaining",
        "secondary_helper": "Minimum sets that must still be possible",
    },
    "soccer": {
        "metric_type": ProgressMetricType.TIME_COUNTUP,
        "total_periods": 2,
        "period_duration_minutes": 45,
        "total_game_minutes": 90,
        "segments": ["h1", "h2", "et1", "et2"],  # Extra time for knockouts
        "default_max_elapsed_minutes": 70,
        "default_min_minutes_until_end": 20,
        "ui_label": "Max Elapsed Minutes",
        "ui_helper": "Latest game minute to enter trade (0-90+)",
        "secondary_label": "Min Minutes Until End",
        "secondary_helper": "Minimum minutes remaining before 90th minute",
    },
    "mma": {
        "metric_type": ProgressMetricType.ROUNDS,
        "total_rounds": 3,  # Can be 5 for title fights
        "round_duration_minutes": 5,
        "segments": ["r1", "r2", "r3", "r4", "r5"],
        "default_max_entry_round": 2,
        "default_min_time_in_round_minutes": 2,
        "ui_label": "Max Entry Round",
        "ui_helper": "Latest round to enter a trade (1-5)",
        "secondary_label": "Min Time in Round (minutes)",
        "secondary_helper": "Minimum minutes left in round to enter",
    },
    "golf": {
        "metric_type": ProgressMetricType.HOLES,
        "total_holes": 18,
        "segments": [f"hole_{i}" for i in range(1, 19)],
        "default_max_entry_hole": 14,
        "default_min_holes_remaining": 4,
        "ui_label": "Max Entry Hole",
        "ui_helper": "Latest hole number to enter a trade (1-18)",
        "secondary_label": "Min Holes Remaining",
        "secondary_helper": "Minimum holes left to play",
    },
}


class SportConfig(Base):
    """
    Stores trading configuration for a specific sport.
    Controls entry conditions, exit conditions, and position sizing.
    """
    
    __tablename__ = "sport_configs"
    __table_args__ = (
        UniqueConstraint("user_id", "sport", name="uq_user_sport"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    sport: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )
    
    min_pregame_price: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("0.55")
    )
    entry_threshold_drop: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("0.15")
    )
    entry_threshold_absolute: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("0.50")
    )
    max_entry_segment: Mapped[str] = mapped_column(
        String(20),
        default="q3"
    )
    min_time_remaining_seconds: Mapped[int] = mapped_column(
        Integer,
        default=300
    )
    
    # Sport-specific progress thresholds (new flexible system)
    # For TIME_COUNTDOWN sports (NBA, NFL, NHL): minutes remaining in period
    min_time_remaining_minutes: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=True
    )
    
    # For TIME_COUNTUP sports (Soccer): max elapsed minutes
    max_elapsed_minutes: Mapped[int] = mapped_column(
        Integer,
        default=70,
        nullable=True
    )
    
    # For INNINGS sports (MLB): max inning to enter, min outs remaining
    max_entry_inning: Mapped[int] = mapped_column(
        Integer,
        default=6,
        nullable=True
    )
    min_outs_remaining: Mapped[int] = mapped_column(
        Integer,
        default=6,
        nullable=True
    )
    
    # For SETS_GAMES sports (Tennis): max set to enter
    max_entry_set: Mapped[int] = mapped_column(
        Integer,
        default=2,
        nullable=True
    )
    min_sets_remaining: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=True
    )
    
    # For ROUNDS sports (MMA): max round to enter
    max_entry_round: Mapped[int] = mapped_column(
        Integer,
        default=2,
        nullable=True
    )
    
    # For HOLES sports (Golf): max hole to enter
    max_entry_hole: Mapped[int] = mapped_column(
        Integer,
        default=14,
        nullable=True
    )
    min_holes_remaining: Mapped[int] = mapped_column(
        Integer,
        default=4,
        nullable=True
    )

    # Latest exit time - must sell once X seconds remaining in game
    exit_time_remaining_seconds: Mapped[int | None] = mapped_column(
        Integer,
        default=120,  # 2 minutes before game ends
        nullable=True
    )

    # Minimum market volume threshold (in USDC) to enter
    min_volume_threshold: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        default=Decimal("1000.00"),
        nullable=True
    )

    take_profit_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("0.20")
    )
    stop_loss_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("0.10")
    )
    exit_before_segment: Mapped[str] = mapped_column(
        String(20),
        default="q4_2min"
    )
    
    position_size_usdc: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("50.00")
    )
    max_positions_per_game: Mapped[int] = mapped_column(
        Integer,
        default=1
    )
    max_total_positions: Mapped[int] = mapped_column(
        Integer,
        default=5
    )
    
    # Per-sport risk limits
    max_daily_loss_usdc: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("50.00"),
        nullable=True
    )
    max_exposure_usdc: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("200.00"),
        nullable=True
    )
    
    # Priority for capital allocation (1 = highest)
    priority: Mapped[int] = mapped_column(
        Integer,
        default=1
    )
    
    # Trading schedule (JSON string: "18:00-23:59")
    trading_hours_start: Mapped[str | None] = mapped_column(
        String(10),
        default=None,
        nullable=True
    )
    trading_hours_end: Mapped[str | None] = mapped_column(
        String(10),
        default=None,
        nullable=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now()
    )
    
    user: Mapped["User"] = relationship(
        "User",
        back_populates="sport_configs"
    )
    
    # Property aliases to match code expectations
    @property
    def is_enabled(self) -> bool:
        """Alias for enabled field to match code expectations."""
        return self.enabled
    
    @property
    def sport_type(self) -> str:
        """Alias for sport field to match code expectations."""
        return self.sport
    
    @property
    def entry_threshold_pct(self) -> Decimal:
        """Alias for entry_threshold_drop to match code expectations."""
        return self.entry_threshold_drop
    
    @property
    def absolute_entry_price(self) -> Decimal:
        """Alias for entry_threshold_absolute to match code expectations."""
        return self.entry_threshold_absolute
    
    @property
    def default_position_size_usdc(self) -> Decimal:
        """Alias for position_size_usdc to match code expectations."""
        return self.position_size_usdc
    
    @property
    def allowed_entry_segments(self) -> list[str]:
        """
        Generate list of allowed entry segments based on max_entry_segment.
        For NBA/NFL: q1, q2, q3 if max is q3
        For NHL: p1, p2 if max is p2
        """
        segment_orders = {
            "q1": ["q1"],
            "q2": ["q1", "q2"],
            "q3": ["q1", "q2", "q3"],
            "q4": ["q1", "q2", "q3", "q4"],
            "p1": ["p1"],
            "p2": ["p1", "p2"],
            "p3": ["p1", "p2", "p3"],
            "h1": ["h1"],
            "h2": ["h1", "h2"],
        }
        return segment_orders.get(self.max_entry_segment, ["q1", "q2", "q3"])
    
    def __repr__(self) -> str:
        return f"<SportConfig(user_id={self.user_id}, sport={self.sport}, enabled={self.enabled})>"
    
    @property
    def progress_metric_type(self) -> ProgressMetricType:
        """Returns the progress metric type for this sport."""
        config = SPORT_PROGRESS_CONFIG.get(self.sport.lower(), {})
        return config.get("metric_type", ProgressMetricType.TIME_COUNTDOWN)
    
    @property
    def sport_config_metadata(self) -> dict:
        """Returns the full sport configuration metadata."""
        return SPORT_PROGRESS_CONFIG.get(self.sport.lower(), {})
    
    def is_valid_entry_progress(self, game_state: dict) -> tuple[bool, str]:
        """
        Checks if current game progress allows entry based on sport-specific rules.
        
        Args:
            game_state: Normalized game state from ESPN service
            
        Returns:
            Tuple of (is_valid, reason_message)
        """
        sport = self.sport.lower()
        metric_type = self.progress_metric_type
        
        if metric_type == ProgressMetricType.TIME_COUNTDOWN:
            # NBA, NFL, NHL - check minutes remaining in period
            time_remaining_sec = game_state.get("time_remaining_seconds", 0)
            time_remaining_min = time_remaining_sec / 60
            min_required = self.min_time_remaining_minutes or 5
            
            if time_remaining_min < min_required:
                return False, f"Only {time_remaining_min:.1f} min left in period (need {min_required}+ min)"
            return True, "Time remaining check passed"
        
        elif metric_type == ProgressMetricType.TIME_COUNTUP:
            # Soccer - check elapsed minutes
            elapsed_minutes = game_state.get("elapsed_minutes", 0)
            max_elapsed = self.max_elapsed_minutes or 70
            
            if elapsed_minutes > max_elapsed:
                return False, f"Game at {elapsed_minutes} min (max entry at {max_elapsed} min)"
            return True, "Elapsed time check passed"
        
        elif metric_type == ProgressMetricType.INNINGS:
            # MLB - check inning and outs
            current_inning = game_state.get("period", 1)
            max_inning = self.max_entry_inning or 6
            
            if current_inning > max_inning:
                return False, f"Game in inning {current_inning} (max entry inning {max_inning})"
            
            # Calculate total outs remaining (9 innings * 6 outs per inning = 54 total)
            outs_in_game = (9 - current_inning) * 6
            min_outs = self.min_outs_remaining or 6
            
            if outs_in_game < min_outs:
                return False, f"Only {outs_in_game} outs remaining (need {min_outs}+)"
            return True, "Inning/outs check passed"
        
        elif metric_type == ProgressMetricType.SETS_GAMES:
            # Tennis - check current set
            current_set = game_state.get("period", 1)
            max_set = self.max_entry_set or 2
            
            if current_set > max_set:
                return False, f"Match in set {current_set} (max entry set {max_set})"
            return True, "Set check passed"
        
        elif metric_type == ProgressMetricType.ROUNDS:
            # MMA - check current round
            current_round = game_state.get("period", 1)
            max_round = self.max_entry_round or 2
            
            if current_round > max_round:
                return False, f"Fight in round {current_round} (max entry round {max_round})"
            
            # Also check time remaining in round
            time_remaining_sec = game_state.get("time_remaining_seconds", 0)
            time_remaining_min = time_remaining_sec / 60
            min_time_in_round = 2  # Default 2 minutes
            
            if time_remaining_min < min_time_in_round:
                return False, f"Only {time_remaining_min:.1f} min left in round"
            return True, "Round check passed"
        
        elif metric_type == ProgressMetricType.HOLES:
            # Golf - check current hole
            current_hole = game_state.get("period", 1)
            max_hole = self.max_entry_hole or 14
            
            if current_hole > max_hole:
                return False, f"Tournament at hole {current_hole} (max entry hole {max_hole})"
            
            holes_remaining = 18 - current_hole
            min_holes = self.min_holes_remaining or 4
            
            if holes_remaining < min_holes:
                return False, f"Only {holes_remaining} holes remaining (need {min_holes}+)"
            return True, "Holes check passed"
        
        # Unknown metric type - allow by default
        return True, "No progress restrictions for this sport"
    
    def get_ui_threshold_config(self) -> dict:
        """
        Returns UI configuration for displaying sport-specific threshold inputs.
        
        Returns:
            Dictionary with field configs for frontend form generation
        """
        config = SPORT_PROGRESS_CONFIG.get(self.sport.lower(), {})
        metric_type = config.get("metric_type", ProgressMetricType.TIME_COUNTDOWN)
        
        result = {
            "sport": self.sport,
            "metric_type": metric_type.value,
            "primary_field": None,
            "secondary_field": None,
        }
        
        if metric_type == ProgressMetricType.TIME_COUNTDOWN:
            result["primary_field"] = {
                "key": "min_time_remaining_minutes",
                "label": config.get("ui_label", "Min Time Remaining (minutes)"),
                "helper": config.get("ui_helper", ""),
                "value": self.min_time_remaining_minutes or 5,
                "min": 1,
                "max": config.get("period_duration_minutes", 15),
                "unit": "minutes",
            }
        elif metric_type == ProgressMetricType.TIME_COUNTUP:
            result["primary_field"] = {
                "key": "max_elapsed_minutes",
                "label": config.get("ui_label", "Max Elapsed Minutes"),
                "helper": config.get("ui_helper", ""),
                "value": self.max_elapsed_minutes or 70,
                "min": 1,
                "max": 90,
                "unit": "minutes",
            }
        elif metric_type == ProgressMetricType.INNINGS:
            result["primary_field"] = {
                "key": "max_entry_inning",
                "label": config.get("ui_label", "Max Entry Inning"),
                "helper": config.get("ui_helper", ""),
                "value": self.max_entry_inning or 6,
                "min": 1,
                "max": 9,
                "unit": "inning",
            }
            result["secondary_field"] = {
                "key": "min_outs_remaining",
                "label": config.get("secondary_label", "Min Outs Remaining"),
                "helper": config.get("secondary_helper", ""),
                "value": self.min_outs_remaining or 6,
                "min": 1,
                "max": 27,
                "unit": "outs",
            }
        elif metric_type == ProgressMetricType.SETS_GAMES:
            result["primary_field"] = {
                "key": "max_entry_set",
                "label": config.get("ui_label", "Max Entry Set"),
                "helper": config.get("ui_helper", ""),
                "value": self.max_entry_set or 2,
                "min": 1,
                "max": 5,
                "unit": "set",
            }
        elif metric_type == ProgressMetricType.ROUNDS:
            result["primary_field"] = {
                "key": "max_entry_round",
                "label": config.get("ui_label", "Max Entry Round"),
                "helper": config.get("ui_helper", ""),
                "value": self.max_entry_round or 2,
                "min": 1,
                "max": 5,
                "unit": "round",
            }
        elif metric_type == ProgressMetricType.HOLES:
            result["primary_field"] = {
                "key": "max_entry_hole",
                "label": config.get("ui_label", "Max Entry Hole"),
                "helper": config.get("ui_helper", ""),
                "value": self.max_entry_hole or 14,
                "min": 1,
                "max": 18,
                "unit": "hole",
            }
            result["secondary_field"] = {
                "key": "min_holes_remaining",
                "label": config.get("secondary_label", "Min Holes Remaining"),
                "helper": config.get("secondary_helper", ""),
                "value": self.min_holes_remaining or 4,
                "min": 1,
                "max": 18,
                "unit": "holes",
            }
        
        return result
