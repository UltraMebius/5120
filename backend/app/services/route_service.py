"""Deprecated compatibility wrapper for the original practice scaffold."""

from .routing.preview_service import get_preview_routes


def get_mock_routes() -> list[dict[str, object]]:
    """Return serialised preview routes for callers of the old service path."""
    return [route.model_dump(mode="json") for route in get_preview_routes()]
