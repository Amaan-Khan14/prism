"""Key generation utilities for the artifact store."""
from __future__ import annotations

import uuid


def diff_key(pr_id: uuid.UUID) -> str:
    """Return the storage key for a PR diff artifact.

    Format: ``diffs/<pr_id>.patch``

    The key is deterministic for a given PR id, collision-resistant
    (UUID v4), and contains no user-controlled data.
    """
    return f"diffs/{pr_id}.patch"


def facts_key(analysis_id: uuid.UUID) -> str:
    """Return the artifact key for deterministic facts of one analysis."""
    return f"facts/{analysis_id}.json"
