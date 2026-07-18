import json
import logging

from app.analysis.service import UpcomingAnalysisService
from app.config import get_settings
from app.database.session import SessionLocal


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    try:
        result = UpcomingAnalysisService(SessionLocal, settings).run()
    except Exception as exc:
        logging.getLogger(__name__).error("analysis_cli_failed error_type=%s", type(exc).__name__)
        raise SystemExit(1) from None
    print(json.dumps(result.model_dump(mode="json"), sort_keys=True))


if __name__ == "__main__":
    main()
