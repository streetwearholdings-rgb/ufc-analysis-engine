from app.calculations.elo import EloConfig, EloFight, RatingSnapshot, calculate_elo_history
from app.config import Settings, get_settings


class RatingService:
    """Coordinates chronological rating calculations using application settings."""

    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        self.config = EloConfig(
            initial_rating=settings.elo_initial_rating,
            k_factor=settings.elo_k_factor,
            method_multiplier=settings.elo_method_multiplier,
            dominance_multiplier=settings.elo_dominance_multiplier,
            context_multiplier=settings.elo_context_multiplier,
        )

    def calculate_history(self, fights: list[EloFight]) -> list[RatingSnapshot]:
        return calculate_elo_history(fights, self.config)
