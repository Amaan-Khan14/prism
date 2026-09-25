"""LocalArtifactStore — filesystem-backed implementation for development."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from app.storage.base import ArtifactStore, StoredArtifact


class LocalArtifactStore(ArtifactStore):
    """Stores artifacts in a local directory tree.

    Used as the default in development (``STORAGE_BACKEND=local``).
    The root directory is created on first use if it does not exist.
    """

    def __init__(self, root: str = "/tmp/prism-artifacts") -> None:
        self._root = Path(root)

    # ------------------------------------------------------------------
    # Interface implementation
    # ------------------------------------------------------------------

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> StoredArtifact:  # noqa: ARG002
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return StoredArtifact(
            key=key,
            size_bytes=len(data),
            sha256=_sha256(data),
        )

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise KeyError(f"Artifact not found: {key!r}")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._path(key)
        try:
            os.remove(path)
        except FileNotFoundError:
            pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _path(self, key: str) -> Path:
        # Guard against path traversal: resolve and verify the candidate is
        # strictly inside the root.  str.startswith is unsafe — "/tmp/prism"
        # is a prefix of "/tmp/prism-evil/x", so it would pass falsely.
        # Instead compare resolved Path objects using is_relative_to (3.9+).
        candidate = (self._root / key).resolve()
        root_resolved = self._root.resolve()
        try:
            candidate.relative_to(root_resolved)
        except ValueError:
            raise ValueError(f"Unsafe storage key: {key!r}")
        return candidate


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
