from dataclasses import asdict
from datetime import date

from app.calculations.matchup_advantages import MatchupFighter, MatchupResult, calculate_matchup
from app.config import Settings, get_settings
from app.database.models.fighter import Fighter
from app.database.models.fighter_rating import FighterRating
from app.database.models.fighter_style_score import FighterStyleScore
from app.database.models.matchup_analysis import MatchupAnalysis
from app.repositories.matchups import MatchupRepository
from app.schemas.matchup import (
    AdvantageResponse,
    KeyInteractionResponse,
    MatchupConfidenceResponse,
    MatchupFighterResponse,
    MatchupResponse,
)


class MatchupService:
    def __init__(self, repository: MatchupRepository, settings: Settings | None = None) -> None:
        self.repository = repository
        self.settings = settings or get_settings()

    def compare(
        self,
        fighter_a: Fighter,
        rating_a: FighterRating,
        style_a: FighterStyleScore,
        fighter_b: Fighter,
        rating_b: FighterRating,
        style_b: FighterStyleScore,
    ) -> tuple[MatchupResponse, MatchupResult]:
        profile_a = _profile(fighter_a, rating_a, style_a)
        profile_b = _profile(fighter_b, rating_b, style_b)
        result = calculate_matchup(profile_a, profile_b)
        response = MatchupResponse(
            fighter_a=_fighter_response(profile_a, rating_a, style_a),
            fighter_b=_fighter_response(profile_b, rating_b, style_b),
            comparison={name: AdvantageResponse(**asdict(value)) for name, value in result.advantages.items()},
            key_interactions=[KeyInteractionResponse(**asdict(value)) for value in result.key_interactions],
            confidence=MatchupConfidenceResponse(
                overall=result.confidence,
                category=result.confidence_category,
                limitations=list(result.limitations),
            ),
            model_version=self.settings.model_version,
        )
        return response, result

    def persist(
        self,
        response: MatchupResponse,
        result: MatchupResult,
        *,
        weight_class: str,
        analysis_date: date,
    ) -> MatchupAnalysis:
        existing = self.repository.for_date(
            response.fighter_a.fighter_id,
            response.fighter_b.fighter_id,
            analysis_date,
            self.settings.model_version,
        )
        values = {
            "weight_class": weight_class,
            "fighter_a_overall_advantage": result.advantages["overall"].difference,
            "fighter_a_striking_advantage": result.advantages["striking"].difference,
            "fighter_a_wrestling_advantage": result.advantages["wrestling"].difference,
            "fighter_a_submission_advantage": result.advantages["submission"].difference,
            "fighter_a_cardio_advantage": result.advantages["cardio"].difference,
            "fighter_a_durability_advantage": result.advantages["durability"].difference,
            "confidence_score": result.confidence,
            "key_interactions": [asdict(value) for value in result.key_interactions],
        }
        if existing is not None:
            for key, value in values.items():
                setattr(existing, key, value)
            return existing
        return self.repository.save(
            MatchupAnalysis(
                fighter_a_id=response.fighter_a.fighter_id,
                fighter_b_id=response.fighter_b.fighter_id,
                analysis_date=analysis_date,
                model_version=self.settings.model_version,
                **values,
            )
        )


def _profile(fighter: Fighter, rating: FighterRating, style: FighterStyleScore) -> MatchupFighter:
    return MatchupFighter(
        fighter_id=fighter.id,
        name=" ".join(part for part in (fighter.first_name, fighter.last_name) if part),
        overall_rating=rating.overall_rating,
        striking_offence=_rating_score(rating.striking_rating),
        striking_defence=_rating_score(rating.defensive_rating),
        wrestling_offence=_rating_score(rating.wrestling_rating),
        takedown_defence=style.takedown_defence,
        submission_threat=style.submission_threat,
        submission_defence=_rating_score(rating.defensive_rating),
        cardio=style.cardio,
        durability=style.durability,
        power=style.striking_power,
        pace=style.pace_sustainability,
        recent_form=rating.performance_score,
        strength_of_schedule=_rating_score(rating.overall_rating),
        pressure=style.pressure_striking,
        defensive_movement=style.defensive_movement,
        knockdown_rate=style.striking_power,
        grappling_control=style.grappling_control,
        getup_score=style.scramble_ability,
        confidence=min(rating.confidence_score, style.confidence_score),
    )


def _fighter_response(
    profile: MatchupFighter, rating: FighterRating, style: FighterStyleScore
) -> MatchupFighterResponse:
    return MatchupFighterResponse(
        fighter_id=profile.fighter_id,
        name=profile.name,
        profile={"confidence": profile.confidence},
        ratings={
            "overall": rating.overall_rating,
            "striking": rating.striking_rating,
            "wrestling": rating.wrestling_rating,
            "submission": rating.submission_rating,
            "defence": rating.defensive_rating,
        },
        style_scores={
            "pressure": style.pressure_striking,
            "power": style.striking_power,
            "cardio": style.cardio,
            "durability": style.durability,
            "takedown_defence": style.takedown_defence,
            "submission_threat": style.submission_threat,
        },
        recent_form={"performance_score": rating.performance_score},
    )


def _rating_score(rating: float) -> float:
    return min(100.0, max(0.0, 50.0 + (rating - 1500.0) / 10.0))
