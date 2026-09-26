"""facts — deterministic facts engine for PRism.

Public API::

    from app.facts import compute_facts
    from app.facts.models import PRFacts, FileFacts, DependencyEdge, FileCoverage
    from app.facts.coverage_intake import CoverageArtifact, CIRunMetadata

The only function most callers need is :func:`compute_facts`.
To supply coverage data, pass a :class:`~app.facts.coverage_intake.CoverageArtifact`
as the *coverage_artifact* keyword argument.
"""
from app.facts.coverage_intake import CIRunMetadata, CoverageArtifact
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
    "CIRunMetadata",
    "CoverageArtifact",
    "CoverageStatus",
    "DependencyEdge",
    "FileCoverage",
    "FileFacts",
    "ImportKind",
    "LineRange",
    "PRFacts",
]
