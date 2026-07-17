from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select

from app.database.models.event import Event
from app.database.models.fight import Fight, FightResult
from app.database.models.fight_round_stat import FightRoundStat
from app.database.models.fighter import Fighter
from app.database.models.fighter_rating import FighterRating
from app.database.models.fighter_style_score import FighterStyleScore
from app.database.session import SessionLocal

A_ID = UUID("10000000-0000-0000-0000-000000000001")
B_ID = UUID("10000000-0000-0000-0000-000000000002")


def main() -> None:
    with SessionLocal.begin() as session:
        if session.scalar(select(Fighter).where(Fighter.external_id == "fictional-ari-vale")):
            print("Sample data already exists")
            return
        session.add_all(
            [
                Fighter(
                    id=A_ID,
                    external_id="fictional-ari-vale",
                    first_name="Ari",
                    last_name="Vale",
                    stance="Orthodox",
                    current_weight_class="Lightweight",
                ),
                Fighter(
                    id=B_ID,
                    external_id="fictional-bo-north",
                    first_name="Bo",
                    last_name="North",
                    stance="Southpaw",
                    current_weight_class="Lightweight",
                ),
            ]
        )
        session.flush()
        for index in range(5):
            event_id = UUID(int=20_000 + index)
            fight_id = UUID(int=30_000 + index)
            session.add(
                Event(
                    id=event_id,
                    external_id=f"fictional-event-{index + 1}",
                    name=f"Fictional Combat {index + 1}",
                    event_date=date.today() - timedelta(days=180 * (4 - index)),
                    location="Harbour City",
                    promotion="UFC",
                )
            )
            session.flush()
            a_wins = index != 1
            session.add(
                Fight(
                    id=fight_id,
                    external_id=f"fictional-fight-{index + 1}",
                    event_id=event_id,
                    fighter_a_id=A_ID,
                    fighter_b_id=B_ID,
                    winner_id=A_ID if a_wins else B_ID,
                    loser_id=B_ID if a_wins else A_ID,
                    weight_class="Lightweight",
                    scheduled_rounds=3,
                    completed_rounds=3,
                    result=FightResult.FIGHTER_A_WIN if a_wins else FightResult.FIGHTER_B_WIN,
                    method="Unanimous Decision",
                )
            )
            session.flush()
            for round_number in range(1, 4):
                session.add_all(
                    [
                        _round_stat(fight_id, A_ID, B_ID, round_number, 10 + index + round_number),
                        _round_stat(fight_id, B_ID, A_ID, round_number, 8 + index + round_number),
                    ]
                )
            session.flush()
        session.add_all([_rating(A_ID, 1580, 68), _rating(B_ID, 1510, 57), _style(A_ID, 78, 74), _style(B_ID, 48, 58)])
    print("Seeded two fictional fighters, five fights, ratings, and style profiles")


def _round_stat(fight_id: UUID, fighter_id: UUID, opponent_id: UUID, round_number: int, landed: int) -> FightRoundStat:
    return FightRoundStat(
        fight_id=fight_id,
        fighter_id=fighter_id,
        opponent_id=opponent_id,
        round_number=round_number,
        round_duration_seconds=300,
        significant_strikes_landed=landed,
        significant_strikes_attempted=landed * 2,
        total_strikes_landed=landed + 5,
        total_strikes_attempted=landed * 2 + 10,
        head_landed=landed // 2,
        head_attempted=landed,
        takedowns_landed=1,
        takedowns_attempted=3,
        control_time_seconds=90,
    )


def _rating(fighter_id: UUID, overall: float, performance: float) -> FighterRating:
    return FighterRating(
        fighter_id=fighter_id,
        rating_date=date.today(),
        weight_class="Lightweight",
        overall_rating=overall,
        striking_rating=overall + 10,
        wrestling_rating=overall - 10,
        submission_rating=overall - 20,
        defensive_rating=overall,
        five_round_rating=1500,
        performance_score=performance,
        confidence_score=0.82,
        sample_size=5,
        model_version="phase2-v1",
    )


def _style(fighter_id: UUID, pressure: float, power: float) -> FighterStyleScore:
    return FighterStyleScore(
        fighter_id=fighter_id,
        calculation_date=date.today(),
        weight_class="Lightweight",
        pressure_striking=pressure,
        counter_striking=60,
        striking_power=power,
        striking_volume=pressure,
        defensive_movement=60,
        wrestling_pressure=55,
        grappling_control=55,
        submission_threat=50,
        takedown_defence=65,
        scramble_ability=60,
        cardio=70,
        durability=68,
        pace_sustainability=70,
        confidence_score=0.8,
        model_version="phase2-v1",
    )


if __name__ == "__main__":
    main()
