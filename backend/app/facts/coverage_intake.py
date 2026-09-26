"""Coverage artifact intake: trusted CI metadata + exact-SHA acceptance gate.

The central rule (from the ``coverage.provenance`` codedocket constraint)::

    Coverage evidence is accepted *only* when the CI run that produced the
    artifact is tied to the exact PR head SHA.  Any mismatch, absent SHA, or
    missing metadata leaves coverage unknown for all files and records a
    clear rejection reason.

Public API
----------
- :class:`CIRunMetadata` — provenance fields supplied alongside a raw artifact.
- :class:`CoverageArtifact` — the complete intake package (metadata + bytes).
- :func:`accept_coverage` — validates SHA, parses the artifact, returns
  :class:`AcceptedCoverage` or :class:`RejectedCoverage`.

The result objects carry full provenance so the facts engine can persist them
without re-deriving them from the raw bytes.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from app.facts.coverage_parsers import (
    MAX_ARTIFACT_BYTES,
    ParseResult,
    parse_cobertura,
    parse_lcov,
)
from app.facts.models import CoverageStatus, FileCoverage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public input types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CIRunMetadata:
    """Trusted provenance metadata for a single CI coverage upload.

    Callers **must** populate this from a trusted source (e.g. a GitHub
    Actions workflow run verified via the API, or an authenticated webhook
    payload).  PRism never infers the SHA from the artifact itself.

    Attributes
    ----------
    commit_sha:
        The full 40-character commit SHA that the CI run built and tested.
        This *must* match the PR's ``head_sha`` exactly for the artifact to
        be accepted.
    ci_provider:
        Human-readable provider tag, e.g. ``'github_actions'``, ``'circleci'``,
        ``'jenkins'``.  Used for provenance display only.
    run_id:
        Provider-specific run identifier (e.g. a GitHub Actions workflow run
        ID as a string, or a CircleCI pipeline number).  Used for provenance.
    artifact_name:
        Optional artifact name within the run (e.g. ``'coverage-report'``).
    """

    commit_sha: str
    ci_provider: str
    run_id: str
    artifact_name: str | None = None
    run_attempt: str | None = None


@dataclass(frozen=True)
class CoverageArtifact:
    """A raw coverage artifact paired with its trusted CI metadata.

    Attributes
    ----------
    raw:
        Raw artifact bytes (LCOV text or Cobertura XML — both UTF-8 or ASCII).
    format:
        ``'lcov'``, ``'cobertura'``, or ``'auto'`` to try Cobertura first then
        LCOV.
    metadata:
        Trusted CI run provenance.  **Required.**  The SHA validation gate
        will reject the artifact if this is absent or if the SHA does not
        match the PR head SHA.
    """

    raw: bytes
    metadata: CIRunMetadata
    format: Literal["lcov", "cobertura", "auto"] = "auto"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AcceptedCoverage:
    """Coverage data accepted after passing SHA validation.

    Attributes
    ----------
    per_file:
        Mapping from normalized file path to
        ``(covered_lines, uncovered_lines)`` frozensets.
    parse_result:
        The raw :class:`~app.facts.coverage_parsers.ParseResult` with parser
        warnings.
    provenance:
        Full provenance record for persistence.
    """

    per_file: dict[str, tuple[frozenset[int], frozenset[int]]]
    parse_result: ParseResult
    provenance: "CoverageProvenance"


@dataclass(frozen=True)
class RejectedCoverage:
    """Coverage artifact that failed validation.

    Attributes
    ----------
    reason:
        A clear human-readable explanation of why the artifact was rejected.
        Examples:
        - ``"SHA mismatch: artifact SHA abc123 != PR head SHA def456"``
        - ``"Artifact SHA is absent; cannot verify against PR head SHA def456"``
        - ``"No artifact supplied; coverage is unknown"``
    """

    reason: str


@dataclass(frozen=True)
class CoverageProvenance:
    """Persisted provenance record for an accepted coverage artifact.

    Attributes
    ----------
    format:
        ``'lcov'`` or ``'cobertura'``.
    ci_provider:
        E.g. ``'github_actions'``.
    run_id:
        Provider-specific run identifier.
    artifact_name:
        Optional artifact name (may be None).
    commit_sha:
        The SHA that the artifact was verified against.
    artifact_sha256:
        Hex SHA-256 of the raw artifact bytes (for integrity verification).
    parsed_at:
        UTC timestamp when this artifact was parsed and accepted.
    file_count:
        Number of distinct files in the parsed artifact.
    parser_warnings:
        Any non-fatal parser warnings.
    """

    format: str
    ci_provider: str
    run_id: str
    run_attempt: str | None
    artifact_name: str | None
    commit_sha: str
    artifact_sha256: str
    parsed_at: datetime
    file_count: int
    parser_warnings: list[str]


# ---------------------------------------------------------------------------
# SHA acceptance gate
# ---------------------------------------------------------------------------


def _normalize_sha(sha: str) -> str:
    """Lowercase and strip whitespace from a commit SHA."""
    return sha.lower().strip()


def accept_coverage(
    artifact: CoverageArtifact | None,
    pr_head_sha: str | None,
) -> AcceptedCoverage | RejectedCoverage:
    """Validate a coverage artifact against the PR head SHA and parse it.

    This is the single entry point for all coverage intake.  It enforces
    the ``coverage.provenance`` constraint:

    1. If no artifact is supplied → :class:`RejectedCoverage` (missing).
    2. If ``pr_head_sha`` is absent → :class:`RejectedCoverage` (unknown PR SHA).
    3. If the artifact's ``commit_sha`` is absent → :class:`RejectedCoverage`.
    4. If the SHAs do not match exactly (case-insensitive) → :class:`RejectedCoverage`.
    5. If the raw bytes exceed :data:`~app.facts.coverage_parsers.MAX_ARTIFACT_BYTES`
       → :class:`RejectedCoverage` (oversized; do not parse).
    6. If parsing fails → :class:`RejectedCoverage` (malformed).
    7. All checks pass → :class:`AcceptedCoverage` with full provenance.

    Parameters
    ----------
    artifact:
        The coverage artifact to validate and parse, or ``None`` if none was
        supplied.
    pr_head_sha:
        The exact 40-character SHA stored as the PR's ``head_sha`` in the DB.

    Returns
    -------
    AcceptedCoverage | RejectedCoverage
    """
    # Step 1 — missing artifact.
    if artifact is None:
        return RejectedCoverage(reason="No coverage artifact was supplied; coverage is unknown.")

    # Step 2 — unknown PR head SHA.
    if not pr_head_sha:
        return RejectedCoverage(
            reason="PR head SHA is not recorded; cannot validate coverage provenance."
        )

    # Step 3 — absent CI commit SHA.
    if not artifact.metadata.commit_sha:
        return RejectedCoverage(
            reason=(
                f"CI run metadata is missing a commit SHA; "
                f"cannot verify against PR head SHA {pr_head_sha!r}."
            )
        )

    # Step 4 — SHA comparison (case-insensitive, full SHA only).
    artifact_sha = _normalize_sha(artifact.metadata.commit_sha)
    pr_sha = _normalize_sha(pr_head_sha)
    if artifact_sha != pr_sha:
        return RejectedCoverage(
            reason=(
                f"Coverage artifact commit SHA {artifact_sha!r} does not match "
                f"PR head SHA {pr_sha!r}. "
                "Coverage from a different commit is never substituted."
            )
        )

    # Step 5 — size check before parsing (fail fast, no memory allocation).
    if len(artifact.raw) > MAX_ARTIFACT_BYTES:
        return RejectedCoverage(
            reason=(
                f"Coverage artifact is too large "
                f"({len(artifact.raw):,} bytes > {MAX_ARTIFACT_BYTES:,} byte limit)."
            )
        )

    # Step 6 — parse.
    raw_sha256 = hashlib.sha256(artifact.raw).hexdigest()
    try:
        fmt = artifact.format
        if fmt == "auto":
            # Cobertura is XML (starts with "<" after optional BOM/whitespace).
            stripped = artifact.raw.lstrip(b"\xef\xbb\xbf \t\r\n")
            if stripped.startswith(b"<"):
                parse_result = parse_cobertura(artifact.raw)
            else:
                parse_result = parse_lcov(artifact.raw)
        elif fmt == "cobertura":
            parse_result = parse_cobertura(artifact.raw)
        elif fmt == "lcov":
            parse_result = parse_lcov(artifact.raw)
        else:
            return RejectedCoverage(reason=f"Unknown coverage format {fmt!r}.")
    except ValueError as exc:
        logger.warning("Coverage artifact parse failed: %s", exc)
        return RejectedCoverage(reason=f"Coverage artifact could not be parsed: {exc}")
    except Exception as exc:
        logger.exception("Unexpected error parsing coverage artifact")
        return RejectedCoverage(
            reason=f"Coverage artifact parse encountered an unexpected error: {type(exc).__name__}."
        )

    provenance = CoverageProvenance(
        format=parse_result.format,
        ci_provider=artifact.metadata.ci_provider,
        run_id=artifact.metadata.run_id,
        run_attempt=artifact.metadata.run_attempt,
        artifact_name=artifact.metadata.artifact_name,
        commit_sha=artifact_sha,
        artifact_sha256=raw_sha256,
        parsed_at=datetime.now(tz=timezone.utc),
        file_count=len(parse_result.data),
        parser_warnings=parse_result.warnings,
    )

    if parse_result.warnings:
        logger.warning(
            "Coverage artifact accepted with %d parser warning(s): %s",
            len(parse_result.warnings),
            "; ".join(parse_result.warnings),
        )

    return AcceptedCoverage(
        per_file=parse_result.data,
        parse_result=parse_result,
        provenance=provenance,
    )


# ---------------------------------------------------------------------------
# Map accepted coverage → FileCoverage facts
# ---------------------------------------------------------------------------


def build_file_coverages(
    changed_file_paths: list[str],
    accepted: AcceptedCoverage,
    changed_line_numbers: dict[str, frozenset[int]] | None = None,
) -> tuple[FileCoverage, ...]:
    """Convert :class:`AcceptedCoverage` to per-file :class:`FileCoverage` facts.

    Files present in the artifact are resolved to the correct
    :class:`~app.facts.models.CoverageStatus`; files absent from the artifact
    receive ``CoverageStatus.unknown`` (the artifact may not cover every file
    in the repository).

    Parameters
    ----------
    changed_file_paths:
        Paths of files changed by the PR (from diff facts).
    accepted:
        Validated and parsed coverage data.

    Returns
    -------
    tuple[FileCoverage, ...]
        One :class:`FileCoverage` per file in *changed_file_paths*, in order.
    """
    provenance_tag = (
        f"{accepted.provenance.ci_provider}:"
        f"{accepted.provenance.run_id}@{accepted.provenance.commit_sha[:8]}"
    )

    results: list[FileCoverage] = []
    for path in changed_file_paths:
        # Try exact match first, then strip common repo-root prefixes.
        entry = accepted.per_file.get(path)
        if entry is None:
            # Attempt to match by suffix (artifact paths may include full
            # repo root while diff paths are relative).
            matches = [
                val
                for artifact_path, val in accepted.per_file.items()
                if artifact_path.endswith("/" + path) or path.endswith("/" + artifact_path)
            ]
            if len(matches) == 1:
                entry = matches[0]
            # Ambiguous suffix matches are deliberately treated as unknown.

        if entry is None:
            # File not in artifact — unknown, not zero.
            results.append(
                FileCoverage(
                    file_path=path,
                    status=CoverageStatus.unknown,
                    covered_lines=frozenset(),
                    uncovered_lines=frozenset(),
                    source=None,
                )
            )
            continue

        covered_lines, uncovered_lines = entry
        if changed_line_numbers is not None:
            changed_lines = changed_line_numbers.get(path, frozenset())
            if not changed_lines:
                results.append(FileCoverage(
                    file_path=path,
                    status=CoverageStatus.unknown,
                    covered_lines=frozenset(),
                    uncovered_lines=frozenset(),
                    source=None,
                ))
                continue
            covered_lines = frozenset(covered_lines & changed_lines)
            uncovered_lines = frozenset(uncovered_lines & changed_lines)
            # Reports can omit lines (for example excluded code); only make
            # a status claim when every changed line is accounted for.
            reported = covered_lines | uncovered_lines
            if reported != changed_lines:
                results.append(FileCoverage(
                    file_path=path,
                    status=CoverageStatus.unknown,
                    covered_lines=covered_lines,
                    uncovered_lines=uncovered_lines,
                    source=provenance_tag,
                ))
                continue
        if not covered_lines and not uncovered_lines:
            status = CoverageStatus.unknown
        elif not uncovered_lines:
            status = CoverageStatus.covered
        elif not covered_lines:
            status = CoverageStatus.uncovered
        else:
            status = CoverageStatus.partial

        results.append(
            FileCoverage(
                file_path=path,
                status=status,
                covered_lines=covered_lines,
                uncovered_lines=uncovered_lines,
                source=provenance_tag,
            )
        )

    return tuple(results)
