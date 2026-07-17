import re
import unicodedata
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from app.database.models.event import Event
from app.database.models.fight import Fight
from app.database.models.fighter import Fighter
from app.odds.schemas import ProviderEvent

NICKNAME_PATTERN = re.compile(r'["“”][^"“”]+["“”]')
NON_ALPHANUMERIC = re.compile(r"[^a-z0-9 ]+")


def normalise_fighter_name(value: str) -> str:
    without_nickname = NICKNAME_PATTERN.sub(" ", value)
    ascii_value = unicodedata.normalize("NFKD", without_nickname).encode("ascii", "ignore").decode()
    simplified = NON_ALPHANUMERIC.sub(" ", ascii_value.lower().replace("'", "").replace("-", " "))
    return " ".join(simplified.split())


def fighter_name(fighter: Fighter) -> str:
    return " ".join(part for part in (fighter.first_name, fighter.last_name) if part)


@dataclass(frozen=True, slots=True)
class MatchResult:
    status: str
    internal_event_id: UUID | None = None
    internal_fight_id: UUID | None = None
    selections: dict[str, UUID] | None = None


def match_provider_event(
    provider_event: ProviderEvent,
    candidates: list[tuple[Fight, Event, Fighter, Fighter]],
    *,
    tolerance_hours: float,
) -> MatchResult:
    provider_names = {
        normalise_fighter_name(provider_event.home_team),
        normalise_fighter_name(provider_event.away_team),
    }
    within_time: list[tuple[Fight, Event, Fighter, Fighter]] = []
    tolerance = timedelta(hours=tolerance_hours)
    for candidate in candidates:
        fight, event, fighter_a, fighter_b = candidate
        event_start = provider_event.commence_time.replace(hour=0, minute=0, second=0, microsecond=0)
        delta = abs(event_start.date() - event.event_date)
        if timedelta(days=delta.days) <= tolerance:
            within_time.append(candidate)
    matches = [
        item for item in within_time
        if {normalise_fighter_name(fighter_name(item[2])), normalise_fighter_name(fighter_name(item[3]))}
        == provider_names
    ]
    if len(matches) > 1:
        return MatchResult("ambiguous_event")
    if not matches:
        return MatchResult("unmatched_fighter" if within_time else "unmatched_event")
    fight, event, fighter_a, fighter_b = matches[0]
    lookup = {
        normalise_fighter_name(fighter_name(fighter_a)): fighter_a.id,
        normalise_fighter_name(fighter_name(fighter_b)): fighter_b.id,
    }
    selections = {
        provider_event.home_team: lookup[normalise_fighter_name(provider_event.home_team)],
        provider_event.away_team: lookup[normalise_fighter_name(provider_event.away_team)],
    }
    return MatchResult("matched", event.id, fight.id, selections)
