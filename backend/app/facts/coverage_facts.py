"""Coverage facts — deterministic stub for the current milestone.

In this milestone no real coverage artifact is linked, so every file
reports :attr:`~app.facts.models.CoverageStatus.unknown`.

The constraint from codedocket ``coverage.provenance`` is enforced here:
coverage evidence must match the PR head SHA from a verified CI run.
Until that plumbing exists, this module deliberately returns ``unknown``
for every file rather than inferring coverage from incomplete data.

A future milestone will replace :func:`build_coverage_facts` with a
real implementation that reads a coverage.xml / Cobertura artifact
whose workflow run is verified against the PR head SHA.
"""
from __future__ import annotations

from app.facts.models import CoverageStatus, FileCoverage


def build_coverage_facts(
    changed_file_paths: list[str],
    coverage_artifact: object | None = None,
) -> tuple[FileCoverage, ...]:
    """Return coverage facts for *changed_file_paths*.

    Parameters
    ----------
    changed_file_paths:
        Paths of every file changed by the PR.
    coverage_artifact:
        Reserved for a future milestone.  When ``None`` (the only
        currently supported value), all files report ``unknown``.

    Returns
    -------
    tuple[FileCoverage, ...]
        One :class:`FileCoverage` per file, in the same order as the
        input.  Status is always ``unknown`` until a verified artifact
        is supplied.
    """
    if coverage_artifact is not None:
        # Future: parse Cobertura XML, verify head SHA, return real data.
        raise NotImplementedError(
            "Real coverage artifact parsing is not implemented in this milestone. "
            "Pass coverage_artifact=None to receive unknown status for all files."
        )

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
