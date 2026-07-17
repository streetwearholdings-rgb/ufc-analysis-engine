from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.matchup_analysis import MatchupAnalysis


class MatchupRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def latest(self, fighter_a_id: UUID, fighter_b_id: UUID) -> MatchupAnalysis | None:
        statement = (
            select(MatchupAnalysis)
            .where(
                MatchupAnalysis.fighter_a_id == fighter_a_id,
                MatchupAnalysis.fighter_b_id == fighter_b_id,
            )
            .order_by(MatchupAnalysis.analysis_date.desc(), MatchupAnalysis.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def save(self, analysis: MatchupAnalysis) -> MatchupAnalysis:
        self.session.add(analysis)
        self.session.flush()
        return analysis

    def latest_for_pair(self, fighter_a_id: UUID, fighter_b_id: UUID) -> MatchupAnalysis | None:
        return self.session.scalar(
            select(MatchupAnalysis).where(
                ((MatchupAnalysis.fighter_a_id == fighter_a_id) &
                 (MatchupAnalysis.fighter_b_id == fighter_b_id))
                | ((MatchupAnalysis.fighter_a_id == fighter_b_id) &
                   (MatchupAnalysis.fighter_b_id == fighter_a_id))
            ).order_by(MatchupAnalysis.analysis_date.desc(), MatchupAnalysis.created_at.desc()).limit(1)
        )

    def for_date(
        self, fighter_a_id: UUID, fighter_b_id: UUID, analysis_date: date, model_version: str
    ) -> MatchupAnalysis | None:
        return self.session.scalar(
            select(MatchupAnalysis).where(
                MatchupAnalysis.fighter_a_id == fighter_a_id,
                MatchupAnalysis.fighter_b_id == fighter_b_id,
                MatchupAnalysis.analysis_date == analysis_date,
                MatchupAnalysis.model_version == model_version,
            )
        )
