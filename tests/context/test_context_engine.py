from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.context.calculations import calculate_recency_weight, calculate_weighted_context_score
from app.context.enums import (
    ClaimType,
    ContextCategory,
    ContextLabel,
    Direction,
    ExtractionMethod,
    ReviewStatus,
    SourceType,
)
from app.context.matching import ContextMatcher
from app.context.registry import CONTEXT_LABEL_REGISTRY
from app.context.reliability import calculate_effective_source_reliability, get_default_source_reliability
from app.context.schemas import ContextSignalInput, ContextSourceInput, LlmExtractedContext
from app.database.base import Base
from app.database.models.context import (
    ContextAdjustment,
    ContextFeatureValue,
    ContextReview,
    ContextSignal,
    ContextSignalSource,
    FighterAlias,
)
from app.database.models.event import Event
from app.database.models.fight import Fight
from app.database.models.fighter import Fighter
from app.services.context_prediction_service import ContextPredictionService
from app.services.context_service import ContextService, build_signal_deduplication_key

A, B, FIGHT, EVENT = UUID(int=801), UUID(int=802), UUID(int=803), UUID(int=804)
OCCURRED = datetime(2026, 7, 18, 8, tzinfo=UTC)
CAPTURED = datetime(2026, 7, 19, 10, tzinfo=UTC)
REVIEWED = datetime(2026, 7, 20, 10, tzinfo=UTC)
AS_OF = datetime(2026, 7, 21, 10, tzinfo=UTC)


@pytest.fixture
def factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    result = sessionmaker(bind=engine, expire_on_commit=False)
    with result.begin() as session:
        session.add_all(
            [
                Fighter(id=A, external_id="a", first_name="José", last_name="O'Malley"),
                Fighter(id=B, external_id="b", first_name="Beta", last_name="Two"),
                Event(id=EVENT, external_id="e", name="UFC Context", event_date=date(2026, 7, 30)),
            ]
        )
        session.flush()
        session.add(
            Fight(
                id=FIGHT,
                external_id="f",
                event_id=EVENT,
                fighter_a_id=A,
                fighter_b_id=B,
                weight_class="Lightweight",
                scheduled_rounds=3,
                completed_rounds=0,
                result="scheduled",
            )
        )
    return result


def test_configuration_caps_defaults_and_disabled() -> None:
    settings = Settings(_env_file=None)
    assert settings.context_engine_enabled and settings.context_max_total_adjustment == 0.05
    with pytest.raises(ValidationError, match="individual"):
        Settings(
            _env_file=None,
            context_max_individual_adjustment=0.04,
            context_max_category_adjustment=0.03,
            context_max_total_adjustment=0.05,
        )
    with pytest.raises(ValidationError, match="CONTEXT_MAX_CATEGORY"):
        Settings(
            _env_file=None,
            context_max_individual_adjustment=0.01,
            context_max_category_adjustment=0.06,
            context_max_total_adjustment=0.05,
        )


def test_signal_and_llm_validation() -> None:
    valid = _signal_input()
    assert valid.label == ContextLabel.MISSED_WEIGHT_CURRENT_FIGHT
    with pytest.raises(ValidationError, match="not valid"):
        _signal_input(category=ContextCategory.INJURY)
    with pytest.raises(ValidationError):
        _signal_input(severity=Decimal("1.1"))
    with pytest.raises(ValidationError, match="fight_id is required"):
        _signal_input(fight_id=None)
    with pytest.raises(ValidationError):
        LlmExtractedContext(
            fighter_name="A",
            fight_reference="A v B",
            category="injury",
            label="confirmed_injury",
            direction="negative",
            severity=0.5,
            confidence=0.7,
            claim_type="credible_report",
            occurred_at=OCCURRED,
            supporting_text="",
        )


def test_source_reliability_and_override() -> None:
    assert get_default_source_reliability(SourceType.ATHLETIC_COMMISSION) == Decimal("0.98")
    assert get_default_source_reliability(SourceType.FIGHTER_STATEMENT) == Decimal("0.9")
    assert get_default_source_reliability(SourceType.SOCIAL_MEDIA) == Decimal("0.55")
    assert calculate_effective_source_reliability(SourceType.OTHER, Decimal("0.8")) == Decimal("0.8")
    with pytest.raises(ValueError):
        calculate_effective_source_reliability(SourceType.OTHER, Decimal("1.1"))


def test_matching_exact_alias_ambiguity_and_fight(factory: sessionmaker[Session]) -> None:
    with factory.begin() as session:
        session.add(
            FighterAlias(
                fighter_id=A, alias="The Jose", normalised_alias="the jose", source="reviewed", is_verified=True
            )
        )
    with factory() as session:
        matcher = ContextMatcher(session)
        assert matcher.match_fighter(" jose o-malley ").fighter_id == A
        assert matcher.match_fighter("The Jose").fighter_id == A
        assert matcher.match_fight(FIGHT, A).event_id == EVENT
        assert matcher.match_fight(FIGHT, UUID(int=999)).status.value == "unmatched_fighter"


def test_recency_half_life_expiry_and_scoring(factory: sessionmaker[Session]) -> None:
    age, weight = calculate_recency_weight(ContextCategory.INJURY, OCCURRED, OCCURRED + timedelta(days=90))
    assert age == Decimal("90.0") and float(weight) == pytest.approx(0.5)
    _, expired = calculate_recency_weight(
        ContextCategory.INJURY, OCCURRED, AS_OF, expires_at=OCCURRED + timedelta(days=1)
    )
    assert expired == 0
    with factory.begin() as session:
        signal = ContextSignal(
            fighter_id=A,
            fight_id=FIGHT,
            event_id=EVENT,
            category="injury",
            label="confirmed_injury",
            direction="negative",
            severity=Decimal("0.5"),
            confidence=Decimal("0.8"),
            source_reliability=Decimal("0.9"),
            occurred_at=OCCURRED,
            review_status="approved",
            claim_type="confirmed_fact",
            extraction_method="manual",
            deduplication_key="x",
            is_contradicted=False,
        )
        session.add(signal)
        session.flush()
        negative = calculate_weighted_context_score(signal, AS_OF, status=ReviewStatus.APPROVED)
        assert negative.weighted_score < 0
        assert calculate_weighted_context_score(signal, AS_OF, status=ReviewStatus.PENDING).weighted_score == 0


def test_end_to_end_review_features_adjustment_dedup_and_historical_safety(
    factory: sessionmaker[Session],
) -> None:
    with factory.begin() as session:
        service = ContextService(session)
        source = service.create_source(_source("https://example.test/one"))
        document = service.create_document(source.id, "Official weigh-in result")
        duplicate_document = service.create_document(source.id, "Official weigh-in result")
        assert document.id == duplicate_document.id
        signal, created = service.create_signal(
            _signal_input(), source_id=source.id, supporting_text="Fighter missed the contracted limit."
        )
        assert created and signal.review_status == ReviewStatus.PENDING
        before = ContextPredictionService(session).apply_context_adjustment(
            fight_id=FIGHT,
            fighter_a_id=A,
            fighter_b_id=B,
            fighter_a_probability=Decimal("0.58"),
            as_of_time=CAPTURED + timedelta(minutes=1),
        )
        assert before.fighter_a.final_probability == Decimal("0.58")
        assert "pending" in before.fighter_a.signals_excluded[0]["reason"]
        service.review_signal(
            signal.id,
            reviewer="reviewer@example.test",
            decision=ReviewStatus.APPROVED,
            reason="official record verified",
            reviewed_at=REVIEWED,
        )
        second_source = service.create_source(_source("https://example.test/two"))
        duplicate, duplicate_created = service.create_signal(
            _signal_input(), source_id=second_source.id, supporting_text="Second confirmation"
        )
        assert duplicate.id == signal.id and not duplicate_created
        assert session.scalar(select(func.count()).select_from(ContextSignal)) == 1
        assert session.scalar(select(func.count()).select_from(ContextSignalSource)) == 2
        historical = ContextPredictionService(session).apply_context_adjustment(
            fight_id=FIGHT,
            fighter_a_id=A,
            fighter_b_id=B,
            fighter_a_probability=Decimal("0.58"),
            as_of_time=CAPTURED + timedelta(minutes=1),
            persist=False,
        )
        assert historical.fighter_a.final_probability == Decimal("0.58")
        prediction = ContextPredictionService(session).apply_context_adjustment(
            fight_id=FIGHT,
            fighter_a_id=A,
            fighter_b_id=B,
            fighter_a_probability=Decimal("0.58"),
            as_of_time=AS_OF,
        )
        assert prediction.fighter_a.final_probability < Decimal("0.58")
        assert prediction.fighter_a.final_probability + prediction.fighter_b.final_probability == 1
        assert prediction.fighter_a.explanation_items[0]["source_title"] == "Verified report"
        features = ContextPredictionService(session).generate_context_features(A, FIGHT, as_of_time=AS_OF)
        assert features.values["missed_weight_current_fight"] == 1
        assert features.source_signal_ids["missed_weight_current_fight"] == [signal.id]
        assert session.scalar(select(func.count()).select_from(ContextAdjustment)) == 4
        feature_count = session.scalar(select(func.count()).select_from(ContextFeatureValue))
        assert feature_count is not None and feature_count > 0
        assert session.scalar(select(func.count()).select_from(ContextReview)) == 1


def test_auto_approval_injury_review_contradiction_and_disabled(factory: sessionmaker[Session]) -> None:
    with factory.begin() as session:
        service = ContextService(session)
        official = service.create_source(
            _source("https://example.test/official", source_type=SourceType.ATHLETIC_COMMISSION)
        )
        auto, _ = service.create_signal(
            _signal_input(extraction_method=ExtractionMethod.IMPORTED, confidence=Decimal("0.95")),
            source_id=official.id,
            supporting_text="Official weigh-in record",
        )
        assert auto.review_status == ReviewStatus.APPROVED
        injury_source = service.create_source(_source("https://example.test/injury"))
        injury, _ = service.create_signal(
            _signal_input(
                category=ContextCategory.INJURY, label=ContextLabel.CONFIRMED_INJURY, fight_id=None, notes="knee injury"
            ),
            source_id=injury_source.id,
            supporting_text="Reported knee injury",
        )
        assert injury.review_status == ReviewStatus.PENDING
        disabled = ContextPredictionService(session, Settings(_env_file=None, context_engine_enabled=False))
        result = disabled.apply_context_adjustment(
            fight_id=FIGHT,
            fighter_a_id=A,
            fighter_b_id=B,
            fighter_a_probability=Decimal("0.6"),
            as_of_time=AS_OF,
        )
        assert result.fighter_a.final_probability == Decimal("0.6")


def test_adjustment_total_cap_and_probability_boundary(factory: sessionmaker[Session]) -> None:
    with factory.begin() as session:
        service = ContextService(session)
        for index, label in enumerate(
            (
                ContextLabel.MISSED_WEIGHT_CURRENT_FIGHT,
                ContextLabel.SHORT_NOTICE_REPLACEMENT,
                ContextLabel.WEIGHT_CLASS_DEBUT,
                ContextLabel.RECENT_KO_LOSS,
                ContextLabel.CONFIRMED_INJURY,
            )
        ):
            source = service.create_source(_source(f"https://example.test/cap-{index}"))
            category = next(category for category, labels in CONTEXT_LABEL_REGISTRY.items() if label in labels)
            data = _signal_input(
                category=category,
                label=label,
                fight_id=FIGHT if label != ContextLabel.RECENT_KO_LOSS else None,
                notes=f"distinct-{index}",
            )
            signal, _ = service.create_signal(data, source_id=source.id, supporting_text="Verified")
            service.review_signal(
                signal.id, reviewer="reviewer", decision=ReviewStatus.APPROVED, reason="verified", reviewed_at=REVIEWED
            )
        result = ContextPredictionService(session).apply_context_adjustment(
            fight_id=FIGHT,
            fighter_a_id=A,
            fighter_b_id=B,
            fighter_a_probability=Decimal("0.02"),
            as_of_time=AS_OF,
        )
        assert abs(result.fighter_a.applied_adjustment) <= Decimal("0.05")
        assert result.fighter_a.final_probability >= Decimal("0.01")
        assert result.fighter_a.final_probability + result.fighter_b.final_probability == 1


def test_contradiction_preserved_and_does_not_leak_backward(factory: sessionmaker[Session]) -> None:
    late_capture = AS_OF + timedelta(days=2)
    with factory.begin() as session:
        service = ContextService(session)
        first_source = service.create_source(_source("https://example.test/claim"))
        first, _ = service.create_signal(
            _signal_input(), source_id=first_source.id, supporting_text="Official missed-weight claim"
        )
        service.review_signal(
            first.id,
            reviewer="reviewer",
            decision=ReviewStatus.APPROVED,
            reason="verified",
            reviewed_at=REVIEWED,
        )
        before = ContextPredictionService(session).apply_context_adjustment(
            fight_id=FIGHT,
            fighter_a_id=A,
            fighter_b_id=B,
            fighter_a_probability=Decimal("0.5"),
            as_of_time=AS_OF,
            persist=False,
        )
        late_source = service.create_source(
            ContextSourceInput(
                source_type=SourceType.FIGHTER_STATEMENT,
                publisher="Fighter",
                url="https://example.test/denial",
                title="Denial",
                published_at=late_capture,
                captured_at=late_capture,
                is_primary_source=True,
            )
        )
        denial, _ = service.create_signal(
            _signal_input(direction=Direction.POSITIVE, notes="denied missed weight"),
            source_id=late_source.id,
            supporting_text="Fighter denied the report",
        )
        after = ContextPredictionService(session).apply_context_adjustment(
            fight_id=FIGHT,
            fighter_a_id=A,
            fighter_b_id=B,
            fighter_a_probability=Decimal("0.5"),
            as_of_time=late_capture + timedelta(hours=1),
            persist=False,
        )
        assert before.fighter_a.final_probability < Decimal("0.5")
        assert after.fighter_a.final_probability == Decimal("0.5")
        assert first.is_contradicted and denial.is_contradicted
        assert session.scalar(select(func.count()).select_from(ContextSignal)) == 2
        assert any("contradictory" in item["reason"] for item in after.fighter_a.signals_excluded)


def test_stable_deduplication_key() -> None:
    assert build_signal_deduplication_key(_signal_input()) == build_signal_deduplication_key(_signal_input())
    assert build_signal_deduplication_key(_signal_input(notes="other")) != build_signal_deduplication_key(
        _signal_input()
    )


def _source(url: str, *, source_type: SourceType = SourceType.OFFICIAL_UFC) -> ContextSourceInput:
    return ContextSourceInput(
        source_type=source_type,
        publisher="Official",
        url=url,
        title="Verified report",
        published_at=OCCURRED,
        captured_at=CAPTURED,
        is_primary_source=True,
    )


def _signal_input(**changes: object) -> ContextSignalInput:
    values: dict[str, object] = {
        "fighter_id": A,
        "fight_id": FIGHT,
        "event_id": EVENT,
        "category": ContextCategory.WEIGHT_CUT,
        "label": ContextLabel.MISSED_WEIGHT_CURRENT_FIGHT,
        "direction": Direction.NEGATIVE,
        "severity": Decimal("1"),
        "confidence": Decimal("0.95"),
        "occurred_at": OCCURRED,
        "claim_type": ClaimType.CONFIRMED_FACT,
        "extraction_method": ExtractionMethod.MANUAL,
        "notes": "official missed weight",
    }
    values.update(changes)
    return ContextSignalInput.model_validate(values)
