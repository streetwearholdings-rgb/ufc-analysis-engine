from uuid import UUID

from app.repositories.performances import PerformanceRepository
from app.schemas.performance import FightPerformanceResponse, PerformanceComponentResponse

EXPLANATIONS = {
    "damage": "Damage reflects knockdowns, head strikes, strike differential, and finish quality.",
    "striking": "Striking effectiveness combines differential, accuracy, avoidance, output, and opponent context.",
    "grappling": "Grappling effectiveness reflects takedowns, submissions, reversals, and control differential.",
    "control": "Control is rewarded only when duration is supported by activity and advancement.",
    "result_quality": "Result quality accounts for outcome, opponent strength, finish timing, and bout context.",
}


class PerformanceService:
    def __init__(self, repository: PerformanceRepository) -> None:
        self.repository = repository

    def for_fighter(self, fighter_id: UUID) -> list[FightPerformanceResponse]:
        return [
            FightPerformanceResponse(
                fight_id=row.fight_id,
                fighter_id=row.fighter_id,
                opponent_id=row.opponent_id,
                damage=PerformanceComponentResponse(score=row.damage_score, explanation=EXPLANATIONS["damage"]),
                striking=PerformanceComponentResponse(score=row.striking_score, explanation=EXPLANATIONS["striking"]),
                grappling=PerformanceComponentResponse(
                    score=row.grappling_score, explanation=EXPLANATIONS["grappling"]
                ),
                control=PerformanceComponentResponse(score=row.control_score, explanation=EXPLANATIONS["control"]),
                result_quality=PerformanceComponentResponse(
                    score=row.result_quality_score,
                    explanation=EXPLANATIONS["result_quality"],
                ),
                raw_performance_score=row.raw_performance_score,
                opponent_adjusted_score=row.opponent_adjusted_score,
                final_performance_score=row.final_performance_score,
                model_version=row.model_version,
                calculated_at=row.calculated_at,
            )
            for row in self.repository.for_fighter(fighter_id)
        ]
