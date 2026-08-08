from fastapi import APIRouter

from ..services.route_service import get_mock_routes

router = APIRouter(tags=["routes"])


@router.get("/routes")
def list_routes(
    origin: str | None = None,
    destination: str | None = None,
) -> list[dict[str, object]]:
    """Return temporary route options for the practice user interface."""
    # The inputs reserve the future API shape. Mock routes do not use them yet.
    _ = (origin, destination)
    return get_mock_routes()
