"""Coverage facts — deterministic computation from verified CI artifacts.

This module replaces the always-unknown stub from the previous milestone.
It now supports real LCOV and Cobertura XML coverage artifacts supplied
alongside the PR head SHA from a verified CI run.

The ``coverage.provenance`` codedocket constraint is enforced here:
coverage evidence is accepted **only** when the CI run's commit SHA exactly
matches the PR head SHA.  Missing or mismatching SHAs leave every file with
``CoverageStatus.unknown`` and record a clear rejection reason.

Public entry point: :func:`build_coverage_facts`.
"""
from __future__ import annotations

import logging

from app.facts.coverage_intake import (
    AcceptedCoverage,
    CoverageArtifact,
    RejectedCoverage,
    accept_coverage,
    build_file_coverages,
)
from app.facts.models import CoverageStatus, FileCoverage

logger = logging.getLogger(__name__)


def build_coverage_facts(
    changed_file_paths: list[str],
    coverage_artifact: CoverageArtifact | None = None,
    pr_head_sha: str | None = None,
    changed_line_numbers: dict[str, frozenset[int]] | None = None,
    accepted_coverage: AcceptedCoverage | None = None,
    rejected_coverage: RejectedCoverage | None = None,
) -> tuple[FileCoverage, ...]:
    """Return per-file coverage facts for the changed files in a PR.

    Parameters
    ----------
    changed_file_paths:
        Paths of every file changed by the PR (from diff facts).  One
        :class:`~app.facts.models.FileCoverage` is returned per path, in
        the same order.
    coverage_artifact:
        Optional :class:`~app.facts.coverage_intake.CoverageArtifact`
        containing raw artifact bytes and trusted CI run metadata.  When
        ``None``, all files report ``unknown``.
    pr_head_sha:
        The exact commit SHA stored as the PR's ``head_sha``.  Required for
        SHA validation when an artifact is provided.

    Returns
    -------
    tuple[FileCoverage, ...]
        One :class:`~app.facts.models.FileCoverage` per file.  Status is:

        - ``covered`` / ``partial`` / ``uncovered`` — when the artifact was
          accepted and the file appears in the artifact.
        - ``unknown`` — when no artifact is supplied, the SHA does not match,
          the artifact is malformed or oversized, or the file is absent from
          the artifact.
    """
    if rejected_coverage is not None:
        logger.warning("Coverage artifact rejected: %s", rejected_coverage.reason)
        return tuple(
            FileCoverage(path, CoverageStatus.unknown, frozenset(), frozenset(), None)
            for path in changed_file_paths
        )

    if coverage_artifact is None and accepted_coverage is None:
        # No artifact supplied — all files are unknown.
        return tuple(
            FileCoverage(
                file_path=path,
                status=CoverageStatus.unknown,
                covered_lines=frozenset(),
                uncovered_lines=frozenset(),
                source=None,
            )
            for path in changed_file_paths
        )

    result = accepted_coverage or accept_coverage(coverage_artifact, pr_head_sha)

    if isinstance(result, RejectedCoverage):
        logger.warning("Coverage artifact rejected: %s", result.reason)
        return tuple(
            FileCoverage(
                file_path=path,
                status=CoverageStatus.unknown,
                covered_lines=frozenset(),
                uncovered_lines=frozenset(),
                source=None,
            )
            for path in changed_file_paths
        )

    assert isinstance(result, AcceptedCoverage)
    logger.info(
        "Coverage artifact accepted: format=%s provider=%s run=%s sha=%s files=%d",
        result.provenance.format,
        result.provenance.ci_provider,
        result.provenance.run_id,
        result.provenance.commit_sha[:8],
        result.provenance.file_count,
    )

    return build_file_coverages(changed_file_paths, result, changed_line_numbers)
