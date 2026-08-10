"""Authenticated operational endpoints for explicit scheduler calls."""

from datetime import datetime, timezone
from functools import lru_cache
from secrets import compare_digest
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from ..config import SETTINGS
from ..services.ingestion.current_activity_refresh import (
    CurrentActivityRefreshService,
)


router = APIRouter(prefix="/internal", tags=["internal"])

_refresh_bearer = HTTPBearer(
    auto_error=False,
    bearerFormat="REFRESH_SECRET",
    scheme_name="RefreshBearer",
)


class CurrentActivityRefreshResponse(BaseModel):
    status: Literal["ok"] = "ok"
    updated: int = Field(ge=0)


@lru_cache
def get_current_activity_refresh_service() -> CurrentActivityRefreshService:
    """Reuse the existing bounded refresh service in a warm function instance."""

    return CurrentActivityRefreshService()


def get_refresh_secret() -> str:
    """Return the environment-backed scheduler secret without exposing it."""

    return SETTINGS.refresh_secret


def _authentication_required() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Bearer authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_refresh_authorization(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_refresh_bearer),
    ],
    expected_secret: Annotated[str, Depends(get_refresh_secret)],
) -> None:
    """Validate one strict Bearer credential and fail closed if unconfigured."""

    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not credentials.credentials
        or any(character.isspace() for character in credentials.credentials)
    ):
        raise _authentication_required()

    if not expected_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Current activity refresh is not configured.",
        )

    if not compare_digest(
        credentials.credentials.encode("utf-8"),
        expected_secret.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Refresh authorization rejected.",
        )


@router.post(
    "/refresh-current-activity",
    response_model=CurrentActivityRefreshResponse,
)
def refresh_current_activity(
    _authorized: Annotated[None, Depends(require_refresh_authorization)],
    service: Annotated[
        CurrentActivityRefreshService,
        Depends(get_current_activity_refresh_service),
    ],
) -> CurrentActivityRefreshResponse:
    """Run one explicit City minute-data to current-activity refresh."""

    try:
        result = service.refresh(
            as_of=datetime.now(timezone.utc),
            dry_run=False,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Current activity refresh failed.",
        ) from None

    return CurrentActivityRefreshResponse(
        updated=result.current_rows_written,
    )
