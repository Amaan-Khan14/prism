"""Immutable fact structs produced by the facts engine.

All values in these structs are computed deterministically from
the diff, static AST analysis, or real coverage data.  No LLM
inference is ever used to populate them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# Changed-line facts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LineRange:
    """An inclusive, 1-based line range within a single file."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 1:
            raise ValueError(f"start must be >= 1, got {self.start}")
        if self.end < self.start:
            raise ValueError(f"end must be >= start, got start={self.start} end={self.end}")

    def __contains__(self, lineno: int) -> bool:
        return self.start <= lineno <= self.end

    def overlaps(self, other: "LineRange") -> bool:
        return self.start <= other.end and other.start <= self.end


@dataclass(frozen=True)
class FileFacts:
    """Deterministic facts about one changed file in the PR."""

    path: str
    """Target (new) file path."""

    old_path: str | None
    """Source path before rename; ``None`` unless the file was renamed."""

    is_new_file: bool
    is_deleted_file: bool
    is_rename: bool

    added_line_numbers: frozenset[int]
    """Set of target-side line numbers that were added by this PR."""

    removed_line_numbers: frozenset[int]
    """Set of source-side line numbers that were removed by this PR."""

    added_ranges: tuple[LineRange, ...]
    """Contiguous runs of added lines, coalesced for readability."""

    removed_ranges: tuple[LineRange, ...]
    """Contiguous runs of removed lines, coalesced for readability."""

    @property
    def total_added(self) -> int:
        return len(self.added_line_numbers)

    @property
    def total_removed(self) -> int:
        return len(self.removed_line_numbers)


# ---------------------------------------------------------------------------
# Python dependency facts
# ---------------------------------------------------------------------------


class ImportKind(str, Enum):
    absolute = "absolute"
    relative = "relative"


@dataclass(frozen=True)
class DependencyEdge:
    """A static-analysis dependency edge from one Python module to another.

    The ``from_file`` imports ``imported_module``; the edge is established
    by AST analysis alone — no runtime execution is performed.
    """

    from_file: str
    """Relative path of the importing file (e.g. ``app/models.py``)."""

    imported_module: str
    """Dotted module name as it appears in the import statement."""

    import_kind: ImportKind

    lineno: int
    """Line number in *from_file* where the import statement appears."""


# ---------------------------------------------------------------------------
# Coverage facts
# ---------------------------------------------------------------------------


class CoverageStatus(str, Enum):
    unknown = "unknown"
    """No verified coverage data is available for this file/range."""

    covered = "covered"
    """All changed lines are covered by at least one test run."""

    partial = "partial"
    """Some but not all changed lines are covered."""

    uncovered = "uncovered"
    """No changed lines are covered."""


@dataclass(frozen=True)
class FileCoverage:
    """Coverage status for the changed lines in one file.

    In the current milestone, status is always ``unknown`` because no
    coverage artifact has been linked to the PR head SHA.  This struct
    exists so the LLM agent and evidence gate can work with a typed value
    rather than relying on the absence of a field.
    """

    file_path: str
    status: CoverageStatus = CoverageStatus.unknown
    covered_lines: frozenset[int] = field(default_factory=frozenset)
    uncovered_lines: frozenset[int] = field(default_factory=frozenset)
    source: str | None = None
    """Human-readable provenance string, e.g. 'codecov:abc123' or None."""


# ---------------------------------------------------------------------------
# Top-level PR facts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PRFacts:
    """All deterministic facts computed for a single PR.

    This is the sole input the LLM agent receives about changed lines,
    dependencies, and coverage.  Nothing in this struct is inferred by
    an LLM — every value traces to git diff output or static AST analysis.
    """

    title: str
    description: str
    """PR body, preserved verbatim as the spec for intent-vs-spec facet."""

    files: tuple[FileFacts, ...]
    """Facts for every file touched by the PR, in diff order."""

    dependency_edges: tuple[DependencyEdge, ...]
    """Python import edges sourced from changed .py files (static analysis)."""

    coverage: tuple[FileCoverage, ...]
    """Coverage status per changed file; status is ``unknown`` when unverified."""

    @property
    def changed_file_paths(self) -> list[str]:
        return [f.path for f in self.files]

    @property
    def total_added_lines(self) -> int:
        return sum(f.total_added for f in self.files)

    @property
    def total_removed_lines(self) -> int:
        return sum(f.total_removed for f in self.files)
