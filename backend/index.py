"""Vercel entrypoint that re-exports the existing CalmWay ASGI app."""

from app.main import app


__all__ = ["app"]
