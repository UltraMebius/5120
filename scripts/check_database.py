"""Verify the local CalmWay PostgreSQL/PostGIS database without modifying it."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.db import CalmWayDatabaseError, dispose_engine  # noqa: E402
from backend.app.repositories.database_repository import (  # noqa: E402
    verify_database,
)


def main() -> int:
    try:
        result = verify_database()
    except CalmWayDatabaseError as exc:
        print(f"Database verification: FAILED - {exc}", file=sys.stderr)
        return 1
    finally:
        dispose_engine()

    print("Database connection: OK")
    print(f"PostgreSQL: {result.postgresql_version}")
    print(f"PostGIS: {result.postgis_version}")
    print("Required schema: OK")
    print("Missing tables: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
