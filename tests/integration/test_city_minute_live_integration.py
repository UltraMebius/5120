"""Explicit live City API -> PostgreSQL -> current activity cycle."""

from datetime import datetime
import os
from zoneinfo import ZoneInfo

import pytest

from backend.app.config import SETTINGS
from backend.app.db.connection import create_database_engine
from backend.app.repositories.current_activity_repository import (
    CurrentActivityRepository,
)
from backend.app.repositories.minute_repository import MinuteRepository
from backend.app.services.crowd.current_activity_service import CurrentActivityService
from backend.app.services.ingestion.current_activity_refresh import (
    CurrentActivityRefreshService,
)


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
RUN_LIVE = os.getenv("RUN_CITY_MINUTE_INTEGRATION", "") == "1"


@pytest.mark.skipif(
    not DATABASE_URL or not RUN_LIVE,
    reason=(
        "Set DATABASE_URL and RUN_CITY_MINUTE_INTEGRATION=1 to run the live "
        "City minute-to-current cycle."
    ),
)
def test_live_city_minute_cycle_materialises_verified_current_activity() -> None:
    engine = create_database_engine(DATABASE_URL)
    minute_repository = MinuteRepository(engine)
    current_repository = CurrentActivityRepository(engine)
    service = CurrentActivityRefreshService(
        minute_repository=minute_repository,
        current_repository=current_repository,
        activity_service=CurrentActivityService(current_repository),
    )
    try:
        result = service.refresh(
            as_of=datetime.now(ZoneInfo(SETTINGS.app_timezone)),
            dry_run=False,
        )
        verification = current_repository.inspect_current_activity()
    finally:
        service.client.close()
        engine.dispose()

    assert result.snapshot.total_count > 0
    assert result.transform.invalid_record_count == 0
    assert result.raw.rows_received == result.snapshot.total_count
    assert result.current_rows_written == len(result.activity.records)
    assert verification.ok
