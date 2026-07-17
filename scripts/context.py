import argparse
import json
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.context.enums import ClaimType, ContextCategory, ContextLabel, Direction, ReviewStatus, SourceType
from app.context.matching import ContextMatcher
from app.context.schemas import ContextSignalInput, ContextSourceInput
from app.database.session import SessionLocal
from app.repositories.context import ContextRepository
from app.services.context_prediction_service import ContextPredictionService
from app.services.context_service import ContextService


def main() -> None:
    parser = _parser()
    args = parser.parse_args()
    result: object
    with SessionLocal.begin() as session:
        if args.command == "add":
            result = _add(session, args)
        elif args.command == "list-pending":
            result = [
                {"id": str(item.id), "label": item.label, "fighter_id": str(item.fighter_id)}
                for item in ContextRepository(session).list_pending()
            ]
        elif args.command == "review":
            decision = ReviewStatus.APPROVED if args.approve else ReviewStatus.REJECTED
            signal = ContextService(session).review_signal(
                UUID(args.signal_id),
                reviewer=args.reviewer,
                decision=decision,
                reason=args.reason or decision.value,
                reviewed_at=_date(args.reviewed_at),
            )
            result = {"signal_id": str(signal.id), "review_status": signal.review_status}
        elif args.command == "features":
            result = (
                ContextPredictionService(session)
                .generate_context_features(UUID(args.fighter_id), UUID(args.fight_id), as_of_time=_date(args.as_of))
                .model_dump(mode="json")
            )
        else:
            prediction = ContextPredictionService(session).apply_context_adjustment(
                fight_id=UUID(args.fight_id),
                fighter_a_id=UUID(args.fighter_a_id),
                fighter_b_id=UUID(args.fighter_b_id),
                fighter_a_probability=Decimal(args.probability),
                as_of_time=_date(args.as_of),
            )
            result = prediction.model_dump(mode="json")
    print(json.dumps(result, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 5 Context Engine operations")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add")
    add.add_argument("--fighter", required=True)
    add.add_argument("--fight-id")
    add.add_argument("--category", required=True, choices=[item.value for item in ContextCategory])
    add.add_argument("--label", required=True, choices=[item.value for item in ContextLabel])
    add.add_argument("--direction", required=True, choices=[item.value for item in Direction])
    add.add_argument("--severity", required=True)
    add.add_argument("--confidence", required=True)
    add.add_argument("--source-type", required=True, choices=[item.value for item in SourceType])
    add.add_argument("--source-url")
    add.add_argument("--source-title", required=True)
    add.add_argument("--publisher", required=True)
    add.add_argument("--published-at", required=True)
    add.add_argument("--captured-at", required=True)
    add.add_argument("--occurred-at", required=True)
    add.add_argument("--expires-at")
    add.add_argument("--supporting-text", required=True)
    add.add_argument("--notes")
    add.add_argument("--value")
    add.add_argument(
        "--claim-type", default=ClaimType.CREDIBLE_REPORT.value, choices=[item.value for item in ClaimType]
    )
    commands.add_parser("list-pending")
    review = commands.add_parser("review")
    review.add_argument("signal_id")
    choice = review.add_mutually_exclusive_group(required=True)
    choice.add_argument("--approve", action="store_true")
    choice.add_argument("--reject", action="store_true")
    review.add_argument("--reviewer", required=True)
    review.add_argument("--reason")
    review.add_argument("--reviewed-at", required=True)
    features = commands.add_parser("features")
    features.add_argument("--fighter-id", required=True)
    features.add_argument("--fight-id", required=True)
    features.add_argument("--as-of", required=True)
    predict = commands.add_parser("predict")
    predict.add_argument("--fight-id", required=True)
    predict.add_argument("--fighter-a-id", required=True)
    predict.add_argument("--fighter-b-id", required=True)
    predict.add_argument("--probability", required=True)
    predict.add_argument("--as-of", required=True)
    return parser


def _add(session: object, args: argparse.Namespace) -> dict[str, str]:
    matcher = ContextMatcher(session)  # type: ignore[arg-type]
    fighter = matcher.match_fighter(args.fighter)
    if fighter.fighter_id is None:
        raise ValueError(f"fighter match failed: {fighter.status.value}: {fighter.reason}")
    fight_id = UUID(args.fight_id) if args.fight_id else None
    fight = matcher.match_fight(fight_id, fighter.fighter_id) if fight_id else fighter
    if fight_id and fight.status.value != "matched":
        raise ValueError(f"fight match failed: {fight.status.value}: {fight.reason}")
    service = ContextService(session)  # type: ignore[arg-type]
    source = service.create_source(
        ContextSourceInput(
            source_type=args.source_type,
            publisher=args.publisher,
            url=args.source_url,
            title=args.source_title,
            published_at=_date(args.published_at),
            captured_at=_date(args.captured_at),
        )
    )
    signal, created = service.create_signal(
        ContextSignalInput(
            fighter_id=fighter.fighter_id,
            fight_id=fight_id,
            event_id=fight.event_id,
            category=args.category,
            label=args.label,
            direction=args.direction,
            severity=Decimal(args.severity),
            confidence=Decimal(args.confidence),
            occurred_at=_date(args.occurred_at),
            expires_at=_date(args.expires_at) if args.expires_at else None,
            claim_type=args.claim_type,
            notes=args.notes,
            measurable_value=Decimal(args.value) if args.value else None,
        ),
        source_id=source.id,
        supporting_text=args.supporting_text,
    )
    return {"signal_id": str(signal.id), "review_status": signal.review_status, "created": str(created).lower()}


def _date(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


if __name__ == "__main__":
    main()
