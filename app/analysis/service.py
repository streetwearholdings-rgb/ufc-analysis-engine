import logging
import threading
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session, aliased, sessionmaker

from app.analysis.schemas import AnalysisRunSummary, AnalysisStatusResponse, ModelStatusResponse
from app.config import Settings, get_settings
from app.database.models.analysis import AnalysisRun, FightAnalysis
from app.database.models.event import Event
from app.database.models.fight import Fight
from app.database.models.fighter import Fighter
from app.ml.elo_baseline import elo_win_probability
from app.repositories.context import ContextRepository
from app.repositories.matchups import MatchupRepository
from app.repositories.odds import OddsRepository
from app.repositories.ratings import RatingRepository
from app.repositories.stats import StatsRepository
from app.repositories.styles import StyleRepository
from app.services.context_prediction_service import ContextPredictionService
from app.services.matchup_service import MatchupService

MODEL_TYPE = "statistical_elo_with_deterministic_features"
PROBABILITY_METHOD = "Elo expected-score logistic transform with reviewed context adjustment"
CALIBRATION_STATUS = "uncalibrated"
LOCK_KEY = 2_129_977_341
logger = logging.getLogger(__name__)
_process_lock = threading.Lock()


class AnalysisAlreadyRunningError(RuntimeError):
    pass


class UpcomingAnalysisService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        settings: Settings | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings or get_settings()

    def run(self, *, event_id: UUID | None = None, force: bool = False) -> AnalysisRunSummary:
        started = datetime.now(UTC)
        with self.session_factory() as session:
            locked = False
            try:
                locked = _acquire_lock(session)
                if not locked:
                    raise AnalysisAlreadyRunningError("An upcoming analysis run is already in progress")
                run = AnalysisRun(
                    status="running",
                    model_type=MODEL_TYPE,
                    model_version=self.settings.model_version,
                    probability_method=PROBABILITY_METHOD,
                    calibration_status=CALIBRATION_STATUS,
                    event_id=event_id,
                    started_at=started,
                )
                session.add(run)
                session.commit()
                rows = _upcoming_fights(session, event_id)
                event_count = len({event.id for _, event, _, _ in rows})
                counters = {
                    "fights_analysed": 0,
                    "recommendations_created": 0,
                    "no_bets": 0,
                    "insufficient_data": 0,
                    "failed": 0,
                }
                for fight, event, fighter_a, fighter_b in rows:
                    try:
                        with session.begin_nested():
                            analysis = self._analyse(session, run.id, fight, event, fighter_a, fighter_b)
                            current = session.scalar(
                                select(FightAnalysis).where(
                                    FightAnalysis.fight_id == fight.id,
                                    FightAnalysis.active.is_(True),
                                )
                            )
                            if current is not None and not force:
                                _copy_analysis(analysis, current)
                                analysis = current
                            else:
                                session.execute(
                                    update(FightAnalysis)
                                    .where(FightAnalysis.fight_id == fight.id, FightAnalysis.active.is_(True))
                                    .values(active=False)
                                )
                                session.add(analysis)
                            session.flush()
                        counters["fights_analysed"] += 1
                        if analysis.recommendation_status == "recommended":
                            counters["recommendations_created"] += 1
                        elif analysis.recommendation_status == "insufficient_data":
                            counters["insufficient_data"] += 1
                        else:
                            counters["no_bets"] += 1
                    except Exception as exc:
                        counters["failed"] += 1
                        logger.error("fight_analysis_failed fight_id=%s error_type=%s", fight.id, type(exc).__name__)
                completed = datetime.now(UTC)
                persisted_run = session.get(AnalysisRun, run.id)
                if persisted_run is None:
                    raise RuntimeError("analysis run state was lost")
                persisted_run.status = "success" if counters["failed"] == 0 else "partial_failure"
                persisted_run.completed_at = completed
                persisted_run.events_processed = event_count
                persisted_run.fights_found = len(rows)
                for key, value in counters.items():
                    setattr(persisted_run, key, value)
                session.commit()
                return AnalysisRunSummary(
                    run_id=run.id,
                    model_type=MODEL_TYPE,
                    model_version=self.settings.model_version,
                    events_processed=event_count,
                    fights_found=len(rows),
                    started_at=started,
                    completed_at=completed,
                    **counters,
                )
            except AnalysisAlreadyRunningError:
                raise
            except Exception as exc:
                session.rollback()
                failed_run = session.scalar(
                    select(AnalysisRun).where(AnalysisRun.started_at == started).order_by(AnalysisRun.id.desc())
                )
                if failed_run is not None:
                    failed_run.status = "failed"
                    failed_run.completed_at = datetime.now(UTC)
                    failed_run.error_summary = "Analysis failed; review server logs."
                    session.commit()
                logger.error("upcoming_analysis_failed error_type=%s", type(exc).__name__)
                raise
            finally:
                if locked:
                    _release_lock(session)

    def _analyse(
        self,
        session: Session,
        run_id: UUID,
        fight: Fight,
        event: Event,
        fighter_a: Fighter,
        fighter_b: Fighter,
    ) -> FightAnalysis:
        generated = datetime.now(UTC)
        base = _analysis_base(run_id, fight, event, fighter_a, fighter_b, self.settings, generated)
        profiles = _profiles(session, fighter_a.id, fighter_b.id)
        warnings = profiles.warnings
        if not profiles.complete:
            return FightAnalysis(
                **base,
                confidence_tier="insufficient",
                risk_level="unrated",
                recommendation="no_bet",
                recommendation_status="insufficient_data",
                no_bet_reason="Core fighter ratings, style scores, or rolling statistics are missing.",
                rationale="No prediction was generated because required fighter evidence is unavailable.",
                key_advantages=[],
                key_risks=["Insufficient historical fighter data"],
                warnings=warnings,
            )

        assert profiles.rating_a and profiles.rating_b and profiles.style_a and profiles.style_b
        assert profiles.stats_a and profiles.stats_b
        matchup_response, matchup = MatchupService(MatchupRepository(session), self.settings).compare(
            fighter_a,
            profiles.rating_a,
            profiles.style_a,
            fighter_b,
            profiles.rating_b,
            profiles.style_b,
        )
        base_probability = Decimal(str(elo_win_probability(
            profiles.rating_a.overall_rating - profiles.rating_b.overall_rating
        )))
        pending = ContextRepository(session).pending_for_fight(fight.id)
        contextual = ContextPredictionService(session, self.settings).apply_context_adjustment(
            fight_id=fight.id,
            fighter_a_id=fighter_a.id,
            fighter_b_id=fighter_b.id,
            fighter_a_probability=base_probability,
            as_of_time=generated,
            persist=True,
        )
        probability_a = contextual.fighter_a.final_probability
        probability_b = contextual.fighter_b.final_probability
        winner, loser, model_probability = (
            (fighter_a, fighter_b, probability_a)
            if probability_a > probability_b
            else (fighter_b, fighter_a, probability_b)
        )
        model_probability = _q(model_probability)
        opponent_probability = Decimal(1) - model_probability
        quality = _feature_quality(profiles)
        confidence = Decimal(str(matchup.confidence)).quantize(Decimal("0.0001"))
        market = _market(session, fight.id, winner.id, self.settings, generated)
        reasons: list[str] = []
        if quality < Decimal(str(self.settings.min_feature_quality)):
            reasons.append("Feature quality is below the configured threshold.")
        if confidence < Decimal(str(self.settings.min_confidence_score)):
            reasons.append("Confidence is below the configured threshold.")
        if pending:
            reasons.append("Context review is required before a recommendation.")
            warnings.append(f"{len(pending)} context signal(s) await review")
        if market.reason:
            reasons.append(market.reason)
        edge = expected_value = None
        if market.price is not None and market.no_vig is not None:
            edge = _q(model_probability - market.no_vig)
            expected_value = _q(model_probability * market.price - Decimal(1))
            if edge < Decimal(str(self.settings.min_value_edge)):
                reasons.append("Value edge is below the configured threshold.")
            if expected_value < Decimal(str(self.settings.min_expected_value)):
                reasons.append("Expected value is below the configured threshold.")
            if not Decimal(str(self.settings.min_recommended_odds)) <= market.price <= Decimal(
                str(self.settings.max_recommended_odds)
            ):
                reasons.append("Decimal odds are outside the configured recommendation range.")
        recommended = not reasons
        advantages = [item.model_dump() for item in matchup_response.key_interactions[:4]]
        advantages.extend(_evidence_advantages(fighter_a, fighter_b, profiles, generated.date()))
        risks = list(matchup.limitations)
        if CALIBRATION_STATUS != "calibrated":
            risks.append("Probability method is not calibrated against held-out production outcomes")
        return FightAnalysis(
            **base,
            predicted_winner_id=winner.id,
            predicted_loser_id=loser.id,
            model_probability=_q(model_probability),
            opponent_probability=_q(opponent_probability),
            market_probability=market.implied,
            no_vig_market_probability=market.no_vig,
            decimal_odds=market.price,
            value_edge=edge,
            expected_value=expected_value,
            confidence_score=confidence,
            confidence_tier=_confidence_tier(confidence),
            feature_quality_score=quality,
            risk_level=_risk_level(confidence, quality, bool(pending)),
            recommendation="bet" if recommended else "no_bet",
            recommendation_status="recommended" if recommended else "no_bet",
            recommended_side_id=winner.id if recommended else None,
            recommended_market="moneyline" if recommended else None,
            no_bet_reason=" ".join(reasons) or None,
            odds_snapshot_id=market.snapshot_id,
            odds_updated_at=market.updated_at,
            data_freshness_at=min(profiles.freshness),
            rationale=(
                f"{winner.first_name} {winner.last_name} leads the Elo rating comparison "
                "and deterministic matchup features."
            ),
            key_advantages=advantages,
            key_risks=risks,
            warnings=warnings,
        )


class _Profiles:
    def __init__(self, session: Session, a: UUID, b: UUID) -> None:
        self.rating_a = RatingRepository(session).latest_for_fighter(a)
        self.rating_b = RatingRepository(session).latest_for_fighter(b)
        self.style_a = StyleRepository(session).latest_for_fighter(a)
        self.style_b = StyleRepository(session).latest_for_fighter(b)
        a_stats = StatsRepository(session).rolling_for_fighter(a)
        b_stats = StatsRepository(session).rolling_for_fighter(b)
        self.stats_a = a_stats[0] if a_stats else None
        self.stats_b = b_stats[0] if b_stats else None
        labels = (
            (self.rating_a, "fighter A rating"), (self.rating_b, "fighter B rating"),
            (self.style_a, "fighter A style profile"), (self.style_b, "fighter B style profile"),
            (self.stats_a, "fighter A rolling statistics"), (self.stats_b, "fighter B rolling statistics"),
        )
        self.warnings = [f"Missing {label}" for value, label in labels if value is None]

    @property
    def complete(self) -> bool:
        return not self.warnings

    @property
    def freshness(self) -> list[datetime]:
        values = [self.rating_a, self.rating_b, self.style_a, self.style_b, self.stats_a, self.stats_b]
        return [_aware(item.created_at) for item in values if item is not None]


class _Market:
    def __init__(self) -> None:
        self.price: Decimal | None = None
        self.implied: Decimal | None = None
        self.no_vig: Decimal | None = None
        self.snapshot_id: UUID | None = None
        self.updated_at: datetime | None = None
        self.reason: str | None = None


def _profiles(session: Session, a: UUID, b: UUID) -> _Profiles:
    return _Profiles(session, a, b)


def _market(session: Session, fight_id: UUID, winner_id: UUID, settings: Settings, now: datetime) -> _Market:
    result = _Market()
    rows = OddsRepository(session).get_best_moneyline_odds_for_fight(fight_id)
    by_fighter = {row.internal_fighter_id: row for row in rows if row.internal_fighter_id is not None}
    if len(by_fighter) < 2 or winner_id not in by_fighter:
        result.reason = "A valid two-sided moneyline market is unavailable."
        return result
    selected = by_fighter[winner_id]
    updated = _aware(selected.bookmaker_last_update)
    if now - updated > timedelta(minutes=settings.max_odds_age_minutes):
        result.reason = "Available odds are stale."
        result.updated_at = updated
        return result
    implied = {fighter_id: Decimal(1) / row.decimal_odds for fighter_id, row in by_fighter.items()}
    total = sum(implied.values(), Decimal(0))
    result.price = selected.decimal_odds
    result.implied = _q(implied[winner_id])
    result.no_vig = _q(implied[winner_id] / total)
    result.snapshot_id = selected.id
    result.updated_at = updated
    return result


def _feature_quality(profiles: _Profiles) -> Decimal:
    assert profiles.rating_a and profiles.rating_b and profiles.style_a and profiles.style_b
    assert profiles.stats_a and profiles.stats_b
    confidence = min(
        profiles.rating_a.confidence_score, profiles.rating_b.confidence_score,
        profiles.style_a.confidence_score, profiles.style_b.confidence_score,
    )
    sample = min(1.0, profiles.rating_a.sample_size / 3, profiles.rating_b.sample_size / 3,
                 profiles.stats_a.fights_count / 3, profiles.stats_b.fights_count / 3)
    return Decimal(str(min(confidence, sample))).quantize(Decimal("0.0001"))


def _evidence_advantages(
    fighter_a: Fighter, fighter_b: Fighter, profiles: _Profiles, as_of: date
) -> list[dict[str, object]]:
    assert profiles.stats_a and profiles.stats_b
    comparisons: list[tuple[str, float | None, float | None]] = [
        (
            "significant striking output",
            profiles.stats_a.significant_strikes_landed_per_minute,
            profiles.stats_b.significant_strikes_landed_per_minute,
        ),
        (
            "striking accuracy",
            profiles.stats_a.significant_strike_accuracy,
            profiles.stats_b.significant_strike_accuracy,
        ),
        ("striking defence", profiles.stats_a.significant_strike_defence, profiles.stats_b.significant_strike_defence),
        ("takedown offence", profiles.stats_a.takedowns_landed_per_15, profiles.stats_b.takedowns_landed_per_15),
        ("takedown defence", profiles.stats_a.takedown_defence, profiles.stats_b.takedown_defence),
        ("grappling control", profiles.stats_a.control_seconds_per_15, profiles.stats_b.control_seconds_per_15),
        ("submission threat", profiles.stats_a.submission_attempts_per_15, profiles.stats_b.submission_attempts_per_15),
        ("finish rate", profiles.stats_a.finish_rate, profiles.stats_b.finish_rate),
        ("decision rate", profiles.stats_a.decision_rate, profiles.stats_b.decision_rate),
        ("reach", fighter_a.reach_cm, fighter_b.reach_cm),
        ("height", fighter_a.height_cm, fighter_b.height_cm),
        ("age", _age(fighter_a, as_of), _age(fighter_b, as_of)),
    ]
    items: list[dict[str, object]] = []
    for factor, a_value, b_value in comparisons:
        if a_value is None or b_value is None:
            continue
        difference = a_value - b_value
        if factor == "age":
            difference = -difference
        side = "fighter_a" if difference > 0 else "fighter_b" if difference < 0 else "neutral"
        items.append({"factor": factor, "advantage": side, "difference": round(difference, 4)})
    if fighter_a.stance and fighter_b.stance:
        items.append(
            {
                "factor": "stance matchup",
                "advantage": "unscored",
                "fighter_a": fighter_a.stance,
                "fighter_b": fighter_b.stance,
            }
        )
    return items


def _age(fighter: Fighter, as_of: date) -> float | None:
    if fighter.date_of_birth is None:
        return None
    return (as_of - fighter.date_of_birth).days / 365.2425


def _analysis_base(
    run_id: UUID, fight: Fight, event: Event, a: Fighter, b: Fighter, settings: Settings, generated: datetime
) -> dict[str, object]:
    return {
        "run_id": run_id, "fight_id": fight.id, "event_id": event.id, "active": True,
        "scheduled_at": event.event_date, "fighter_a_id": a.id, "fighter_b_id": b.id,
        "model_type": MODEL_TYPE, "model_version": settings.model_version,
        "probability_method": PROBABILITY_METHOD, "calibration_status": CALIBRATION_STATUS,
        "generated_at": generated,
    }


def _upcoming_fights(session: Session, event_id: UUID | None) -> list[tuple[Fight, Event, Fighter, Fighter]]:
    a, b = aliased(Fighter), aliased(Fighter)
    statement = (
        select(Fight, Event, a, b).join(Event, Event.id == Fight.event_id)
        .join(a, a.id == Fight.fighter_a_id).join(b, b.id == Fight.fighter_b_id)
        .where(Event.event_date >= date.today(), Fight.result == "scheduled")
        .order_by(Event.event_date, Fight.id)
    )
    if event_id:
        statement = statement.where(Event.id == event_id)
    return list(session.execute(statement).tuples())


def _copy_analysis(source: FightAnalysis, target: FightAnalysis) -> None:
    for column in FightAnalysis.__table__.columns:
        if column.name != "id":
            setattr(target, column.name, getattr(source, column.name))


def analysis_status(session: Session, settings: Settings | None = None) -> AnalysisStatusResponse:
    config = settings or get_settings()
    run = session.scalar(select(AnalysisRun).order_by(AnalysisRun.started_at.desc()).limit(1))
    latest = session.scalar(select(func.max(FightAnalysis.generated_at)))
    return AnalysisStatusResponse(
        latest_run=run.id if run else None, run_status=run.status if run else "never_run",
        model_type=MODEL_TYPE, model_version=config.model_version,
        fights_analysed=run.fights_analysed if run else 0,
        recommendations_created=run.recommendations_created if run else 0,
        failures=run.failed if run else 0, safe_error_summary=run.error_summary if run else None,
        latest_analysis_timestamp=latest,
    )


def model_status(session: Session, settings: Settings | None = None) -> ModelStatusResponse:
    config = settings or get_settings()
    latest = session.scalar(select(AnalysisRun).order_by(AnalysisRun.started_at.desc()).limit(1))
    success = session.scalar(
        select(AnalysisRun)
        .where(AnalysisRun.status == "success")
        .order_by(AnalysisRun.completed_at.desc())
        .limit(1)
    )
    count = session.scalar(
        select(func.count()).select_from(FightAnalysis).where(
            FightAnalysis.active.is_(True), FightAnalysis.scheduled_at >= date.today()
        )
    ) or 0
    data_freshness = session.scalar(select(func.max(FightAnalysis.data_freshness_at)))
    odds_freshness = session.scalar(select(func.max(FightAnalysis.odds_updated_at)))
    return ModelStatusResponse(
        model_type=MODEL_TYPE, model_version=config.model_version, probability_method=PROBABILITY_METHOD,
        calibration_status=CALIBRATION_STATUS, latest_run=latest.started_at if latest else None,
        latest_success=success.completed_at if success else None, upcoming_fights_analysed=count,
        data_freshness=data_freshness, odds_freshness=odds_freshness,
    )


def _confidence_tier(value: Decimal) -> str:
    return "high" if value >= Decimal("0.8") else "moderate" if value >= Decimal("0.6") else "low"


def _risk_level(confidence: Decimal, quality: Decimal, pending: bool) -> str:
    if pending or min(confidence, quality) < Decimal("0.6"):
        return "high"
    return "low" if min(confidence, quality) >= Decimal("0.8") else "medium"


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.00000001"))


def _aware(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


def _acquire_lock(session: Session) -> bool:
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        return bool(session.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}))
    return _process_lock.acquire(blocking=False)


def _release_lock(session: Session) -> None:
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
    elif _process_lock.locked():
        _process_lock.release()
