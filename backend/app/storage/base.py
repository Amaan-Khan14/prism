"""ArtifactStore protocol — backend-agnostic artifact persistence."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class StoredArtifact:
    """Metadata returned after a successful store operation."""

    key: str
    """Stable, collision-resistant object key (e.g. ``diffs/abc123.patch``)."""

    size_bytes: int
    """Exact byte length of the stored content."""

    sha256: str
    """Hex SHA-256 digest of the raw bytes before storage."""


class ArtifactStore(ABC):
    """Abstract interface for artifact persistence.

    Implementations: :class:`LocalArtifactStore`, :class:`S3ArtifactStore`.
    The backend is selected at startup via :attr:`app.config.Settings.storage_backend`.
    """

    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> StoredArtifact:
        """Store *data* under *key*.  Raises on failure; never silently swallows errors."""

    @abstractmethod
    def get(self, key: str) -> bytes:
        """Retrieve the bytes stored under *key*.  Raises :exc:`KeyError` if not found."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove the object stored under *key*.  No-op if the key does not exist."""
