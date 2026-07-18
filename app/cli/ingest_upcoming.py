import json
import logging

from app.config import get_settings
from app.database.session import SessionLocal
from app.ingestion.service import UpcomingIngestionService
from app.odds.client import OddsApiClient


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    try:
        summary = UpcomingIngestionService(OddsApiClient(settings), SessionLocal).ingest()
    except Exception as exc:
        logging.getLogger(__name__).error("upcoming_ingestion_command_failed error_type=%s", type(exc).__name__)
        raise SystemExit(1) from None
    print(json.dumps(summary.model_dump(mode="json"), sort_keys=True))


if __name__ == "__main__":
    main()
