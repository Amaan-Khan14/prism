"""facts — deterministic facts engine for PRism.

Public API::

    from app.facts import compute_facts
    from app.facts.models import PRFacts, FileFacts, DependencyEdge, FileCoverage

The only function most callers need is :func:`compute_facts`.
"""
from app.facts.engine import compute_facts
from app.facts.models import (
    CoverageStatus,
    DependencyEdge,
    FileCoverage,
    FileFacts,
    ImportKind,
    LineRange,
    PRFacts,
)

__all__ = [
    "compute_facts",
    "CoverageStatus",
    "DependencyEdge",
    "FileCoverage",
    "FileFacts",
    "ImportKind",
    "LineRange",
    "PRFacts",
]
