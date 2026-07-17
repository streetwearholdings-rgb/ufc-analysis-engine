import argparse
import json
import logging

from app.config import get_settings
from app.database.session import SessionLocal
from app.odds.client import OddsApiClient
from app.services.odds_ingestion_service import OddsIngestionService


def main() -> None:
    parser = argparse.ArgumentParser(description="The Odds API operations")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="ingest upcoming UFC moneyline odds")
    ingest.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    summary = OddsIngestionService(OddsApiClient(settings), SessionLocal, settings).ingest_upcoming_ufc_odds(
        dry_run=args.dry_run
    )
    print(json.dumps(summary.model_dump(mode="json"), sort_keys=True))


if __name__ == "__main__":
    main()
