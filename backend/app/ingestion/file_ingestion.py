"""FileIngestion — builds a PRBundle from a raw diff + metadata."""
from __future__ import annotations

from app.ingestion.bundle import PRBundle
from app.ingestion.diff_parser import parse_diff


class FileIngestion:
    """Accepts a raw unified diff and optional metadata; returns a PRBundle."""

    def ingest(
        self,
        diff: str,
        title: str = "",
        description: str = "",
    ) -> PRBundle:
        patches = parse_diff(diff)
        return PRBundle(
            title=title,
            description=description,
            diff_raw=diff,
            patches=patches,
        )
