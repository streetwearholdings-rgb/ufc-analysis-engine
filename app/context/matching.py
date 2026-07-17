from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.context.enums import ContextMatchStatus
from app.database.models.context import FighterAlias
from app.database.models.fight import Fight
from app.database.models.fighter import Fighter
from app.odds.matching import fighter_name, normalise_fighter_name


@dataclass(frozen=True, slots=True)
class ContextMatchResult:
    status: ContextMatchStatus
    fighter_id: UUID | None = None
    fight_id: UUID | None = None
    event_id: UUID | None = None
    confidence: float = 0.0
    candidate_ids: list[UUID] = field(default_factory=list)
    reason: str = ""


class ContextMatcher:
    def __init__(self, session: Session) -> None:
        self.session = session

    def match_fighter(self, reference: str) -> ContextMatchResult:
        try:
            fighter_id = UUID(reference)
        except ValueError:
            fighter_id = None
        if fighter_id is not None:
            fighter = self.session.get(Fighter, fighter_id)
            return ContextMatchResult(
                ContextMatchStatus.MATCHED if fighter else ContextMatchStatus.UNMATCHED_FIGHTER,
                fighter_id=fighter.id if fighter else None,
                confidence=1.0 if fighter else 0.0,
                reason="explicit internal identifier" if fighter else "fighter ID not found",
            )
        key = normalise_fighter_name(reference)
        alias_ids = list(
            self.session.scalars(
                select(FighterAlias.fighter_id).where(
                    FighterAlias.normalised_alias == key, FighterAlias.is_verified.is_(True)
                )
            )
        )
        if len(alias_ids) == 1:
            return ContextMatchResult(
                ContextMatchStatus.MATCHED, fighter_id=alias_ids[0], confidence=1.0, reason="verified alias"
            )
        fighters = [
            fighter
            for fighter in self.session.scalars(select(Fighter))
            if _comparison_key(fighter_name(fighter)) == _comparison_key(reference)
        ]
        candidate_ids = [fighter.id for fighter in fighters]
        if len(fighters) == 1:
            return ContextMatchResult(
                ContextMatchStatus.MATCHED,
                fighter_id=fighters[0].id,
                confidence=1.0,
                candidate_ids=candidate_ids,
                reason="exact normalised name",
            )
        status = ContextMatchStatus.AMBIGUOUS_FIGHTER if fighters else ContextMatchStatus.UNMATCHED_FIGHTER
        return ContextMatchResult(status, candidate_ids=candidate_ids, reason="name did not resolve uniquely")

    def match_fight(self, fight_id: UUID, fighter_id: UUID) -> ContextMatchResult:
        fight = self.session.get(Fight, fight_id)
        if fight is None:
            return ContextMatchResult(
                ContextMatchStatus.UNMATCHED_FIGHT, fighter_id=fighter_id, reason="fight ID not found"
            )
        if fighter_id not in {fight.fighter_a_id, fight.fighter_b_id}:
            return ContextMatchResult(
                ContextMatchStatus.UNMATCHED_FIGHTER,
                fighter_id=fighter_id,
                fight_id=fight.id,
                event_id=fight.event_id,
                reason="fighter is not a participant in the fight",
            )
        return ContextMatchResult(
            ContextMatchStatus.MATCHED,
            fighter_id=fighter_id,
            fight_id=fight.id,
            event_id=fight.event_id,
            confidence=1.0,
            reason="explicit fight and participant match",
        )


def _comparison_key(value: str) -> str:
    return normalise_fighter_name(value).replace(" ", "")
