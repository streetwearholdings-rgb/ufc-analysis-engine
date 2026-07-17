from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.context.calculations import calculate_weighted_context_score
from app.context.enums import ContextCategory, ContextLabel, Direction, ReviewStatus
from app.context.registry import LABEL_ADJUSTMENT_CAPS
from app.context.schemas import (
    ContextFeatureSet,
    ContextualFightPrediction,
    ContextualPrediction,
    WeightedContextSignal,
)
from app.database.models.context import ContextAdjustment, ContextFeatureValue, ContextSignal
from app.repositories.context import ContextRepository

CONTEXT_VERSION = "phase5-v1"
FEATURE_NAMES: dict[ContextLabel, str] = {
    ContextLabel.MISSED_WEIGHT_CURRENT_FIGHT: "missed_weight_current_fight",
    ContextLabel.CAREER_WEIGHT_MISS_COUNT: "career_weight_miss_count",
    ContextLabel.SHORT_NOTICE_DAYS: "short_notice_days",
    ContextLabel.SHORT_NOTICE_REPLACEMENT: "is_short_notice_replacement",
    ContextLabel.OPPONENT_CHANGED: "opponent_changed",
    ContextLabel.WEIGHT_CLASS_DEBUT: "is_weight_class_debut",
    ContextLabel.WEIGHT_CLASS_MOVE_UP: "weight_class_change_direction",
    ContextLabel.WEIGHT_CLASS_MOVE_DOWN: "weight_class_change_direction",
    ContextLabel.LONG_LAYOFF: "layoff_days",
    ContextLabel.RAPID_TURNAROUND: "rapid_turnaround_days",
    ContextLabel.RECENT_KO_LOSS: "days_since_last_ko_loss",
    ContextLabel.ACTIVE_MEDICAL_SUSPENSION: "active_medical_suspension",
    ContextLabel.CONFIRMED_INJURY: "confirmed_injury_score",
    ContextLabel.RECENT_SURGERY: "recent_surgery_score",
    ContextLabel.NEW_TRAINING_CAMP: "training_camp_change",
    ContextLabel.NEW_HEAD_COACH: "head_coach_change",
    ContextLabel.LONG_DISTANCE_TRAVEL: "travel_distance_km",
    ContextLabel.TIMEZONE_DIFFERENCE: "timezone_difference_hours",
    ContextLabel.ALTITUDE_CHANGE: "altitude_change_metres",
    ContextLabel.RETIREMENT_RETURN: "retirement_return",
}


class ContextPredictionService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.repository = ContextRepository(session)

    def generate_context_features(
        self, fighter_id: UUID, fight_id: UUID, *, as_of_time: datetime, persist: bool = True
    ) -> ContextFeatureSet:
        _require_aware(as_of_time)
        active, _ = self._signals(fighter_id, fight_id, as_of_time)
        values: dict[str, Decimal | None] = {name: Decimal(0) for name in set(FEATURE_NAMES.values())}
        values["recent_ko_loss_count"] = Decimal(0)
        sources: dict[str, list[UUID]] = {name: [] for name in values}
        for signal, weighted in active:
            label = ContextLabel(signal.label)
            feature = FEATURE_NAMES.get(label)
            if feature is None:
                continue
            value = _feature_value(signal, weighted, label)
            if label in {ContextLabel.CAREER_WEIGHT_MISS_COUNT, ContextLabel.RECENT_KO_LOSS}:
                values[feature] = (values[feature] or Decimal(0)) + value
            else:
                values[feature] = value
            sources[feature].append(signal.id)
            if label == ContextLabel.RECENT_KO_LOSS:
                values["recent_ko_loss_count"] = (values["recent_ko_loss_count"] or Decimal(0)) + 1
                sources["recent_ko_loss_count"].append(signal.id)
        version = f"{CONTEXT_VERSION}:{_utc(as_of_time).isoformat()}"
        result = ContextFeatureSet(
            fighter_id=fighter_id,
            fight_id=fight_id,
            as_of_time=as_of_time,
            context_version=version,
            values=values,
            source_signal_ids=sources,
        )
        if persist:
            now = datetime.now(UTC)
            for name, stored_value in values.items():
                self.repository.save_feature(
                    ContextFeatureValue(
                        fighter_id=fighter_id,
                        fight_id=fight_id,
                        feature_name=name,
                        numeric_value=stored_value,
                        generated_at=as_of_time,
                        context_version=version,
                        source_signal_ids=[str(item) for item in sources[name]],
                        created_at=now,
                    )
                )
        return result

    def apply_context_adjustment(
        self,
        *,
        fight_id: UUID,
        fighter_a_id: UUID,
        fighter_b_id: UUID,
        fighter_a_probability: Decimal,
        as_of_time: datetime,
        persist: bool = True,
    ) -> ContextualFightPrediction:
        _require_aware(as_of_time)
        if not Decimal(0) < fighter_a_probability < Decimal(1):
            raise ValueError("base probability must be strictly between zero and one")
        base_b = Decimal(1) - fighter_a_probability
        if not self.settings.context_engine_enabled:
            a = _unchanged(fighter_a_id, fight_id, fighter_a_probability, "Context Engine disabled")
            b = _unchanged(fighter_b_id, fight_id, base_b, "Context Engine disabled")
            return ContextualFightPrediction(
                fight_id=fight_id,
                fighter_a=a,
                fighter_b=b,
                calculation_version=CONTEXT_VERSION,
                as_of_time=as_of_time,
            )
        a_requested, a_score, a_items, a_excluded, a_warnings = self._requested(fighter_a_id, fight_id, as_of_time)
        b_requested, b_score, b_items, b_excluded, b_warnings = self._requested(fighter_b_id, fight_id, as_of_time)
        total_cap = Decimal(str(self.settings.context_max_total_adjustment))
        relative = _clamp(a_requested - b_requested, -total_cap, total_cap)
        final_a = _clamp(fighter_a_probability + relative, Decimal("0.01"), Decimal("0.99"))
        final_b = Decimal(1) - final_a
        applied_a, applied_b = final_a - fighter_a_probability, final_b - base_b
        a = _prediction(
            fighter_a_id,
            fight_id,
            fighter_a_probability,
            a_score,
            a_requested,
            applied_a,
            final_a,
            a_items,
            a_excluded,
            a_warnings,
        )
        b = _prediction(
            fighter_b_id, fight_id, base_b, b_score, b_requested, applied_b, final_b, b_items, b_excluded, b_warnings
        )
        if persist:
            self._persist_prediction(a, as_of_time)
            self._persist_prediction(b, as_of_time)
        return ContextualFightPrediction(
            fight_id=fight_id,
            fighter_a=a,
            fighter_b=b,
            calculation_version=CONTEXT_VERSION,
            as_of_time=as_of_time,
        )

    def _signals(
        self, fighter_id: UUID, fight_id: UUID, as_of_time: datetime
    ) -> tuple[list[tuple[ContextSignal, WeightedContextSignal]], list[dict[str, str]]]:
        active = []
        excluded = []
        for signal in self.repository.signals_as_of(fighter_id, fight_id, as_of_time):
            sources = self.repository.sources_for_signal_as_of(signal.id, as_of_time)
            status = self.repository.status_as_of(signal, as_of_time)
            contradicted = self._contradicted_as_of(signal, as_of_time)
            if not sources:
                excluded.append({"signal_id": str(signal.id), "reason": "source unavailable as of prediction time"})
                continue
            weighted = calculate_weighted_context_score(
                signal,
                as_of_time,
                status=status,
                recency_decay_enabled=self.settings.context_recency_decay_enabled,
                is_contradicted=contradicted,
            )
            if status != ReviewStatus.APPROVED:
                excluded.append({"signal_id": str(signal.id), "reason": f"review status is {status.value}"})
            elif contradicted:
                excluded.append({"signal_id": str(signal.id), "reason": "contradictory evidence requires review"})
            elif weighted.recency_weight == 0:
                excluded.append({"signal_id": str(signal.id), "reason": "signal expired"})
            elif Direction(signal.direction) == Direction.UNCERTAIN:
                excluded.append({"signal_id": str(signal.id), "reason": "uncertain signals cannot adjust probability"})
            else:
                active.append((signal, weighted))
        return active, excluded

    def _contradicted_as_of(self, signal: ContextSignal, as_of_time: datetime) -> bool:
        return any(
            other.id != signal.id
            and other.category == signal.category
            and other.fight_id == signal.fight_id
            and other.direction != signal.direction
            and abs((_utc(other.occurred_at) - _utc(signal.occurred_at)).days) <= 7
            and bool(self.repository.sources_for_signal_as_of(other.id, as_of_time))
            for other in self.repository.signals_as_of(signal.fighter_id, signal.fight_id or UUID(int=0), as_of_time)
        )

    def _requested(
        self, fighter_id: UUID, fight_id: UUID, as_of_time: datetime
    ) -> tuple[Decimal, Decimal, list[dict[str, object]], list[dict[str, str]], list[str]]:
        active, excluded = self._signals(fighter_id, fight_id, as_of_time)
        individual_cap = Decimal(str(self.settings.context_max_individual_adjustment))
        category_cap = Decimal(str(self.settings.context_max_category_adjustment))
        categories: dict[ContextCategory, Decimal] = {}
        score = Decimal(0)
        items: list[dict[str, object]] = []
        warnings = []
        for signal, weighted in active:
            label = ContextLabel(signal.label)
            label_cap = Decimal(str(LABEL_ADJUSTMENT_CAPS.get(label, 0)))
            requested = _clamp(weighted.weighted_score * label_cap, -individual_cap, individual_cap)
            category = ContextCategory(signal.category)
            previous = categories.get(category, Decimal(0))
            applied = _clamp(previous + requested, -category_cap, category_cap) - previous
            categories[category] = previous + applied
            score += weighted.weighted_score
            source_rows = self.repository.sources_for_signal_as_of(signal.id, as_of_time)
            source = source_rows[0][1]
            items.append(
                {
                    "signal_id": str(signal.id),
                    "category": category.value,
                    "label": label.value,
                    "direction": signal.direction,
                    "source_title": source.title,
                    "source_type": source.source_type,
                    "source_reliability": str(signal.source_reliability),
                    "confidence": str(signal.confidence),
                    "severity": str(signal.severity),
                    "recency_weight": str(weighted.recency_weight),
                    "weighted_score": str(weighted.weighted_score),
                    "requested_adjustment": str(requested),
                    "applied_adjustment": str(applied),
                    "review_status": ReviewStatus.APPROVED.value,
                    "reason": "approved sourced context",
                }
            )
            if label == ContextLabel.ACTIVE_MEDICAL_SUSPENSION:
                warnings.append("Active medical suspension requires prediction finalisation review")
        total = _clamp(
            sum(categories.values(), Decimal(0)),
            -Decimal(str(self.settings.context_max_total_adjustment)),
            Decimal(str(self.settings.context_max_total_adjustment)),
        )
        return total, score, items, excluded, warnings

    def _persist_prediction(self, result: ContextualPrediction, calculated_at: datetime) -> None:
        now = datetime.now(UTC)
        self.repository.save_adjustment(
            ContextAdjustment(
                fighter_id=result.fighter_id,
                fight_id=result.fight_id,
                base_probability=result.base_probability,
                raw_context_score=result.raw_context_score,
                requested_adjustment=result.requested_adjustment,
                applied_adjustment=result.applied_adjustment,
                final_probability=result.final_probability,
                context_confidence=result.context_confidence,
                calculation_version=CONTEXT_VERSION,
                calculated_at=calculated_at,
                explanation_json=result.model_dump(mode="json"),
                created_at=now,
            )
        )


def _feature_value(signal: ContextSignal, weighted: WeightedContextSignal, label: ContextLabel) -> Decimal:
    if signal.numeric_value is not None:
        return signal.numeric_value
    if label == ContextLabel.WEIGHT_CLASS_MOVE_DOWN:
        return Decimal(-1)
    if label == ContextLabel.WEIGHT_CLASS_MOVE_UP:
        return Decimal(1)
    if label in {ContextLabel.CONFIRMED_INJURY, ContextLabel.RECENT_SURGERY}:
        return signal.severity * weighted.recency_weight
    return Decimal(1)


def _prediction(
    fighter_id: UUID,
    fight_id: UUID,
    base: Decimal,
    score: Decimal,
    requested: Decimal,
    applied: Decimal,
    final: Decimal,
    items: list[dict[str, object]],
    excluded: list[dict[str, str]],
    warnings: list[str],
) -> ContextualPrediction:
    confidences = [Decimal(str(item["confidence"])) for item in items]
    confidence = sum(confidences, Decimal(0)) / len(confidences) if confidences else Decimal(0)
    return ContextualPrediction(
        fighter_id=fighter_id,
        fight_id=fight_id,
        base_probability=base,
        raw_context_score=score,
        requested_adjustment=requested,
        applied_adjustment=applied,
        final_probability=final,
        context_confidence=confidence,
        signals_used=[UUID(str(item["signal_id"])) for item in items],
        signals_excluded=excluded,
        warnings=warnings,
        explanation_items=items,
    )


def _unchanged(fighter_id: UUID, fight_id: UUID, base: Decimal, warning: str) -> ContextualPrediction:
    return _prediction(fighter_id, fight_id, base, Decimal(0), Decimal(0), Decimal(0), base, [], [], [warning])


def _clamp(value: Decimal, lower: Decimal, upper: Decimal) -> Decimal:
    return min(upper, max(lower, value))


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None:
        raise ValueError("as_of_time is mandatory and must be timezone-aware")


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
