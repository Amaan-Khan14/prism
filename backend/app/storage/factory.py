"""Factory that creates the configured ArtifactStore singleton.

Call :func:`get_artifact_store` to retrieve the process-wide instance;
it is constructed once on first call (lazy singleton via module-level cache).

Selection logic:
  * ``STORAGE_BACKEND=local``  →  :class:`LocalArtifactStore`
  * ``STORAGE_BACKEND=s3``     →  :class:`S3ArtifactStore`
    Requires ``S3_BUCKET_NAME`` and ``AWS_REGION`` to be set; raises
    ``RuntimeError`` with a clear message if they are missing.
"""
from __future__ import annotations

from typing import Optional

_store: Optional["ArtifactStore"] = None  # noqa: F821 — resolved below


def get_artifact_store() -> "ArtifactStore":  # noqa: F821
    """Return the process-wide :class:`ArtifactStore`, constructing it once."""
    global _store
    if _store is None:
        _store = _build_store()
    return _store


def _build_store() -> "ArtifactStore":
    from app.config import settings
    from app.storage.base import ArtifactStore  # noqa: F401 — re-exported
    from app.storage.local import LocalArtifactStore
    from app.storage.s3 import S3ArtifactStore

    backend = settings.storage_backend.lower()

    if backend == "local":
        return LocalArtifactStore(root=settings.local_artifact_root)

    if backend == "s3":
        bucket = settings.s3_bucket_name
        region = settings.aws_region
        if not bucket:
            raise RuntimeError(
                "STORAGE_BACKEND=s3 requires S3_BUCKET_NAME to be set. "
                "Set it in your environment or .env file."
            )
        if not region:
            raise RuntimeError(
                "STORAGE_BACKEND=s3 requires AWS_REGION to be set. "
                "Set it in your environment or .env file."
            )
        return S3ArtifactStore(bucket_name=bucket, region_name=region)

    raise RuntimeError(
        f"Unknown STORAGE_BACKEND={backend!r}. Valid values: 'local', 's3'."
    )


# Allow tests to swap the singleton without restarting the process.
def _reset_store() -> None:
    """Test helper — reset the singleton so the next call rebuilds it."""
    global _store
    _store = None
