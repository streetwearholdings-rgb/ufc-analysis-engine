from sqlalchemy import func, or_, select

from app.database.models.fight import Fight
from app.database.models.fight_round_stat import FightRoundStat
from app.database.models.fighter import Fighter
from app.database.session import SessionLocal


def main() -> None:
    with SessionLocal() as session:
        fighters = session.scalar(select(func.count()).select_from(Fighter)) or 0
        fights = session.scalar(select(func.count()).select_from(Fight)) or 0
        stats = session.scalar(select(func.count()).select_from(FightRoundStat)) or 0
        self_fights = (
            session.scalar(select(func.count()).select_from(Fight).where(Fight.fighter_a_id == Fight.fighter_b_id)) or 0
        )
        invalid_stats = (
            session.scalar(
                select(func.count())
                .select_from(FightRoundStat)
                .where(
                    or_(
                        FightRoundStat.round_number <= 0,
                        FightRoundStat.round_duration_seconds < 0,
                        FightRoundStat.significant_strikes_landed > FightRoundStat.significant_strikes_attempted,
                        FightRoundStat.takedowns_landed > FightRoundStat.takedowns_attempted,
                    )
                )
            )
            or 0
        )
    print(f"fighters={fighters} fights={fights} round_stats={stats}")
    if self_fights or invalid_stats:
        print(f"validation_failed self_fights={self_fights} invalid_stats={invalid_stats}")
        raise SystemExit(1)
    print("validation_passed")


if __name__ == "__main__":
    main()
