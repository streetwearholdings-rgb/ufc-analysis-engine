import argparse
from uuid import UUID

from app.database.session import SessionLocal
from app.services.recalculation_service import RecalculationService


def main() -> None:
    parser = argparse.ArgumentParser(description="Recalculate one fighter's derived rolling profiles")
    parser.add_argument("fighter_id", type=UUID)
    args = parser.parse_args()
    with SessionLocal() as session:
        windows = RecalculationService(session).recalculate_fighter(args.fighter_id)
    print(f"Rebuilt {', '.join(windows)} for {args.fighter_id}")


if __name__ == "__main__":
    main()
