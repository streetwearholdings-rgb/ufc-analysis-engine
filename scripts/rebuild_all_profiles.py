from app.database.session import SessionLocal
from app.services.recalculation_service import RecalculationService


def main() -> None:
    with SessionLocal() as session:
        processed, failed = RecalculationService(session).rebuild_all()
    print(f"Rebuild complete: processed={processed}, failed={failed}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
