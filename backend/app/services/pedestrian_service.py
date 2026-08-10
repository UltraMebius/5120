"""Compatibility boundary for the future PostgreSQL-backed crowd services."""


class PedestrianService:
    """Phase 1 placeholder with no ingestion, scoring, or database access."""

    def load_processed_data(self) -> None:
        """Preserve the old method until Phase 2 replaces file-based assumptions."""
        return None
