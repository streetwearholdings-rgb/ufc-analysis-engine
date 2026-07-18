from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analysis.schemas import AnalysisFilters, AnalysisPage, AnalysisResponse, FighterReference
from app.database.models.analysis import FightAnalysis
from app.database.models.event import Event
from app.database.models.fighter import Fighter


class AnalysisReadService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def page(self, filters: AnalysisFilters) -> AnalysisPage:
        statement = select(FightAnalysis).where(
            FightAnalysis.active.is_(True), FightAnalysis.scheduled_at >= date.today()
        )
        if filters.event_id:
            statement = statement.where(FightAnalysis.event_id == filters.event_id)
        if filters.minimum_confidence is not None:
            statement = statement.where(FightAnalysis.confidence_score >= filters.minimum_confidence)
        if filters.minimum_value_edge is not None:
            statement = statement.where(FightAnalysis.value_edge >= filters.minimum_value_edge)
        if filters.recommendation_status:
            statement = statement.where(FightAnalysis.recommendation_status == filters.recommendation_status)
        total = self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        rows = list(
            self.session.scalars(
                statement.order_by(FightAnalysis.scheduled_at, FightAnalysis.generated_at.desc())
                .limit(filters.limit)
                .offset(filters.offset)
            )
        )
        return AnalysisPage(
            items=[self._response(row) for row in rows], total=total, limit=filters.limit, offset=filters.offset
        )

    def fight(self, fight_id: UUID) -> AnalysisResponse:
        row = self.session.scalar(
            select(FightAnalysis).where(FightAnalysis.fight_id == fight_id, FightAnalysis.active.is_(True))
        )
        if row is None:
            raise LookupError("Fight analysis not found")
        return self._response(row)

    def picks(
        self,
        *,
        event_id: UUID | None,
        market: str | None,
        confidence_tier: str | None,
        minimum_expected_value: Decimal | None,
        include_no_bets: bool,
        limit: int,
        offset: int,
    ) -> AnalysisPage:
        status = None if include_no_bets else "recommended"
        statement = select(FightAnalysis).where(
            FightAnalysis.active.is_(True), FightAnalysis.scheduled_at >= date.today()
        )
        if status:
            statement = statement.where(FightAnalysis.recommendation_status == status)
        if event_id:
            statement = statement.where(FightAnalysis.event_id == event_id)
        if market:
            statement = statement.where(FightAnalysis.recommended_market == market)
        if confidence_tier:
            statement = statement.where(FightAnalysis.confidence_tier == confidence_tier)
        if minimum_expected_value is not None:
            statement = statement.where(FightAnalysis.expected_value >= minimum_expected_value)
        total = self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        rows = list(self.session.scalars(
            statement.order_by(FightAnalysis.scheduled_at, FightAnalysis.expected_value.desc())
            .limit(limit).offset(offset)
        ))
        return AnalysisPage(items=[self._response(row) for row in rows], total=total, limit=limit, offset=offset)

    def _response(self, row: FightAnalysis) -> AnalysisResponse:
        event = self.session.get(Event, row.event_id)
        fighter_a = self.session.get(Fighter, row.fighter_a_id)
        fighter_b = self.session.get(Fighter, row.fighter_b_id)
        if event is None or fighter_a is None or fighter_b is None:
            raise LookupError("Analysis references unavailable event or fighter data")
        by_id = {fighter_a.id: fighter_a, fighter_b.id: fighter_b}
        winner = by_id.get(row.predicted_winner_id) if row.predicted_winner_id else None
        loser = by_id.get(row.predicted_loser_id) if row.predicted_loser_id else None
        return AnalysisResponse(
            fight_id=row.fight_id, event_id=row.event_id, event_name=event.name, scheduled_at=row.scheduled_at,
            fighter_a=_fighter(fighter_a), fighter_b=_fighter(fighter_b),
            predicted_winner=_fighter(winner) if winner else None,
            predicted_loser=_fighter(loser) if loser else None,
            model_probability=row.model_probability, opponent_probability=row.opponent_probability,
            market_probability=row.market_probability, no_vig_market_probability=row.no_vig_market_probability,
            decimal_odds=row.decimal_odds, value_edge=row.value_edge, expected_value=row.expected_value,
            confidence_score=row.confidence_score, confidence_tier=row.confidence_tier,
            feature_quality_score=row.feature_quality_score, risk_level=row.risk_level,
            recommendation=row.recommendation, recommendation_status=row.recommendation_status,
            no_bet_reason=row.no_bet_reason, recommended_market=row.recommended_market,
            rationale=row.rationale, key_advantages=row.key_advantages, key_risks=row.key_risks,
            warnings=row.warnings, model_type=row.model_type, model_version=row.model_version,
            probability_method=row.probability_method, calibration_status=row.calibration_status,
            generated_at=row.generated_at, odds_updated_at=row.odds_updated_at,
        )


def _fighter(value: Fighter) -> FighterReference:
    return FighterReference(
        fighter_id=value.id,
        name=" ".join(part for part in (value.first_name, value.last_name) if part),
    )
