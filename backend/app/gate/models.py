"""Typed inputs and outputs for the deterministic evidence gate."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EvidenceKind(str, Enum):
    """Fact category a finding uses to support its claim."""

    added_line = "added_line"
    dependency_edge = "dependency_edge"
    coverage = "coverage"


class FindingClaim(str, Enum):
    """Structured claim type used to select the valid evidence contract."""

    code = "code"
    dependency = "dependency"
    coverage_gap = "coverage_gap"
    coverage_unknown = "coverage_unknown"


class EvidenceVerdict(str, Enum):
    verified = "verified"
    unverified = "unverified"


@dataclass(frozen=True)
class EvidenceCitation:
    """A structured reference to one deterministic fact.

    ``file_path`` is the changed file for line and coverage citations, and the
    importing file for dependency citations. Dependency citations also include
    ``imported_module``. Coverage citations use a line number for coverage-gap
    claims and omit it when asserting that coverage status is unknown.
    """

    kind: EvidenceKind
    file_path: str
    line_number: int | None = None
    imported_module: str | None = None

    def __post_init__(self) -> None:
        if not self.file_path:
            raise ValueError("file_path must not be empty")
        if self.line_number is not None and self.line_number < 1:
            raise ValueError("line_number must be >= 1")
        if self.kind is EvidenceKind.dependency_edge and not self.imported_module:
            raise ValueError("dependency_edge citations require imported_module")


@dataclass(frozen=True)
class FindingCandidate:
    """A structured finding awaiting deterministic evidence verification."""

    claim: FindingClaim
    summary: str
    severity: int
    citations: tuple[EvidenceCitation, ...]
    facet: str | None = None

    def __post_init__(self) -> None:
        if not self.summary.strip():
            raise ValueError("summary must not be empty")


@dataclass(frozen=True)
class CitationCheck:
    """Validation result for one citation, including a stable reason code."""

    citation: EvidenceCitation
    supported: bool
    reason: str


@dataclass(frozen=True)
class GatedFinding:
    """A finding with its gate verdict and citation-level audit details."""

    finding: FindingCandidate
    verdict: EvidenceVerdict
    citation_checks: tuple[CitationCheck, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceGateResult:
    """Partitioned review output: verified brief findings and appendix."""

    findings: tuple[GatedFinding, ...]

    @property
    def verified(self) -> tuple[GatedFinding, ...]:
        return tuple(
            item for item in self.findings
            if item.verdict is EvidenceVerdict.verified
        )

    @property
    def unverified(self) -> tuple[GatedFinding, ...]:
        return tuple(
            item for item in self.findings
            if item.verdict is EvidenceVerdict.unverified
        )
