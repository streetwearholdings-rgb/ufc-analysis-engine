from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.models.context import ContextSignal
from app.database.models.event import Event
from app.database.models.fight import Fight
from app.database.models.fighter import Fighter
from app.repositories.context import ContextRepository
from app.repositories.events import EventRepository
from app.repositories.matchups import MatchupRepository
from app.schemas.events import (
    ConsolidatedFightAnalysis,
    ContextSignalSummary,
    EventFightCard,
    EventSummary,
    FighterSummary,
    FightSummary,
    MarketSummary,
    PendingContextPage,
    ProbabilitySummary,
)
from app.services.odds_market_service import OddsMarketService


class FightAnalysisNotReadyError(RuntimeError):
    pass


class FightAnalysisService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.events = EventRepository(session)
        self.context = ContextRepository(session)

    def upcoming_events(self, *, from_date: date, limit: int) -> list[EventSummary]:
        return [_event_summary(event, count) for event, count in self.events.upcoming(from_date=from_date, limit=limit)]

    def event_fight_card(self, event_id: UUID) -> EventFightCard:
        event = self.events.get(event_id)
        if event is None:
            raise LookupError("Event not found")
        rows = self.events.fight_card(event_id)
        return EventFightCard(
            event=_event_summary(event, len(rows)),
            fights=[_fight_summary(fight, fighter_a, fighter_b) for fight, fighter_a, fighter_b in rows],
        )

    def pending_context(self, *, limit: int, offset: int) -> PendingContextPage:
        rows, total = self.context.pending_page(limit=limit, offset=offset)
        return PendingContextPage(
            items=[_signal_summary(signal) for signal in rows], total=total, limit=limit, offset=offset
        )

    def consolidated(self, fight_id: UUID) -> ConsolidatedFightAnalysis:
        row = self.events.fight(fight_id)
        if row is None:
            raise LookupError("Fight not found")
        fight, fighter_a, fighter_b = row
        adjustment_a = self.context.latest_adjustment(fighter_a.id, fight.id)
        adjustment_b = self.context.latest_adjustment(fighter_b.id, fight.id)
        if adjustment_a is None or adjustment_b is None:
            raise FightAnalysisNotReadyError("No complete contextual prediction has been calculated for this fight")
        warnings: list[str] = []
        if adjustment_a.calculated_at != adjustment_b.calculated_at:
            warnings.append("Fighter prediction records were calculated at different timestamps")
        matchup = MatchupRepository(self.session).latest_for_pair(fighter_a.id, fighter_b.id)
        if matchup is None:
            warnings.append("No persisted matchup-confidence analysis is available")
        market = OddsMarketService(self.session, self.settings).get_fight_market_odds(fight.id)
        odds_by_fighter = {selection.fighter_id: selection for selection in market.selections}
        probabilities = {
            fighter_a.id: adjustment_a.final_probability,
            fighter_b.id: adjustment_b.final_probability,
        }
        markets = []
        for fighter_id, probability in probabilities.items():
            odds = odds_by_fighter.get(fighter_id)
            if odds is None:
                warnings.append(f"No fresh matched moneyline odds for fighter {fighter_id}")
                continue
            markets.append(
                MarketSummary(
                    fighter_id=fighter_id,
                    bookmaker=odds.best_bookmaker,
                    decimal_odds=odds.best_decimal_odds,
                    market_probability=odds.raw_implied_probability,
                    expected_value=(probability * odds.best_decimal_odds - Decimal(1)).quantize(Decimal("0.00000001")),
                    bookmaker_count=odds.bookmaker_count,
                    bookmaker_last_update=odds.bookmaker_last_update,
                )
            )
        explanations = [adjustment_a.explanation_json, adjustment_b.explanation_json]
        applied = [item for explanation in explanations for item in _list(explanation.get("explanation_items"))]
        excluded = [item for explanation in explanations for item in _list(explanation.get("signals_excluded"))]
        warnings.extend(str(item) for explanation in explanations for item in _list(explanation.get("warnings")))
        pending = [_signal_summary(signal) for signal in self.context.pending_for_fight(fight.id)]
        if pending:
            warnings.append(f"{len(pending)} context signal(s) await review")
        prediction_time = max(_aware(adjustment_a.calculated_at), _aware(adjustment_b.calculated_at))
        odds_timestamp = max((item.bookmaker_last_update for item in markets), default=None)
        return ConsolidatedFightAnalysis(
            fight=_fight_summary(fight, fighter_a, fighter_b),
            fighters=[_fighter_summary(fighter_a), _fighter_summary(fighter_b)],
            probabilities=[
                ProbabilitySummary(
                    fighter_id=fighter_a.id,
                    base_probability=adjustment_a.base_probability,
                    context_adjusted_probability=adjustment_a.final_probability,
                ),
                ProbabilitySummary(
                    fighter_id=fighter_b.id,
                    base_probability=adjustment_b.base_probability,
                    context_adjusted_probability=adjustment_b.final_probability,
                ),
            ],
            model_confidence=Decimal(str(matchup.confidence_score if matchup else 0)),
            best_bookmaker_odds=markets,
            applied_context_signals=applied,
            excluded_context_signals=excluded,
            pending_context_signals=pending,
            data_quality_warnings=sorted(set(warnings)),
            prediction_timestamp=prediction_time,
            model_version=matchup.model_version if matchup else self.settings.model_version,
            context_engine_version=adjustment_a.calculation_version,
            odds_timestamp=odds_timestamp,
        )


def _fighter_summary(fighter: Fighter) -> FighterSummary:
    return FighterSummary(
        fighter_id=fighter.id,
        name=f"{fighter.first_name} {fighter.last_name}".strip(),
        nickname=fighter.nickname,
        weight_class=fighter.current_weight_class,
    )


def _fight_summary(fight: Fight, fighter_a: Fighter, fighter_b: Fighter) -> FightSummary:
    return FightSummary(
        fight_id=fight.id,
        event_id=fight.event_id,
        weight_class=fight.weight_class,
        scheduled_rounds=fight.scheduled_rounds,
        status=fight.result,
        fighter_a=_fighter_summary(fighter_a),
        fighter_b=_fighter_summary(fighter_b),
    )


def _event_summary(event: Event, count: int) -> EventSummary:
    return EventSummary(
        event_id=event.id,
        name=event.name,
        event_date=event.event_date,
        location=event.location,
        promotion=event.promotion,
        fight_count=count,
    )


def _signal_summary(signal: ContextSignal) -> ContextSignalSummary:
    return ContextSignalSummary(
        signal_id=signal.id,
        fighter_id=signal.fighter_id,
        fight_id=signal.fight_id,
        category=signal.category,
        label=signal.label,
        direction=signal.direction,
        review_status=signal.review_status,
        confidence=signal.confidence,
        severity=signal.severity,
        occurred_at=_aware(signal.occurred_at),
    )


def _list(value: object) -> list[dict[str, object]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _aware(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
