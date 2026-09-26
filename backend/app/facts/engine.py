"""Facts engine — public entry point.

:func:`compute_facts` is the single function the rest of the backend
(and eventually the LLM agent) calls.  It orchestrates the three
deterministic sub-engines:

1. ``diff_facts`` — changed files and exact line ranges from the diff.
2. ``python_deps`` — import edges via stdlib AST walking.
3. ``coverage_facts`` — per-file line coverage from a verified CI artifact,
   or ``unknown`` when no verified artifact is available.

The function accepts an optional *file_source_map* so callers that
already have file contents in memory can pass them in without an
additional filesystem read.  When the map is omitted, Python dependency
analysis is skipped for all files (no inference is performed).

Pass *coverage_artifact* (a :class:`~app.facts.coverage_intake.CoverageArtifact`)
to supply real coverage data.  The artifact is accepted only when its
``metadata.commit_sha`` exactly matches ``bundle.head_sha``; any mismatch
leaves all files with ``CoverageStatus.unknown``.

No LLM calls are made here; this module must remain a pure-Python,
synchronous, side-effect-free computation.
"""
from __future__ import annotations

import logging
from typing import Mapping

from app.facts.coverage_facts import build_coverage_facts
from app.facts.coverage_intake import AcceptedCoverage, CoverageArtifact, RejectedCoverage
from app.facts.diff_facts import extract_diff_facts
from app.facts.models import PRFacts
from app.facts.python_deps import extract_python_deps
from app.ingestion.bundle import PRBundle

logger = logging.getLogger(__name__)


def compute_facts(
    bundle: PRBundle,
    file_source_map: Mapping[str, str] | None = None,
    coverage_artifact: CoverageArtifact | None = None,
    accepted_coverage: AcceptedCoverage | None = None,
    rejected_coverage: RejectedCoverage | None = None,
) -> PRFacts:
    """Compute all deterministic facts for *bundle*.

    Parameters
    ----------
    bundle:
        The normalised PR representation produced by either ingestion path.
    file_source_map:
        Optional mapping from file path to source text (the *new* version
        of the file, i.e. the b-side of the diff).  When provided, Python
        files in the map will have their import statements extracted via
        static analysis.  Files absent from the map are skipped — no
        dependency information is fabricated.
    coverage_artifact:
        Optional coverage artifact for this PR.  When provided, it is
        validated against ``bundle.head_sha``; only an exact-SHA match
        yields real coverage data.  When ``None``, all files report
        ``CoverageStatus.unknown``.

    Returns
    -------
    PRFacts
        All facts computed from the PR.  Every field is either derived
        from the diff / source text or explicitly marked ``unknown``.
    """
    # 1. Diff facts
    file_facts = extract_diff_facts(bundle)
    logger.debug(
        "facts-engine: extracted diff facts for %d files (%d added, %d removed lines)",
        len(file_facts),
        sum(f.total_added for f in file_facts),
        sum(f.total_removed for f in file_facts),
    )

    # 2. Python dependency edges (only for .py files with known source)
    changed_py_paths = [f.path for f in file_facts if f.path.endswith(".py")]
    dep_edges = extract_python_deps(
        changed_py_files=changed_py_paths,
        file_source_map=file_source_map or {},
    )
    logger.debug(
        "facts-engine: extracted %d Python dependency edges from %d .py files",
        len(dep_edges),
        len(changed_py_paths),
    )

    # 3. Coverage — accepted only when the artifact's SHA matches bundle.head_sha.
    all_paths = [f.path for f in file_facts]
    coverage_facts = build_coverage_facts(
        changed_file_paths=all_paths,
        coverage_artifact=coverage_artifact,
        pr_head_sha=bundle.head_sha,
        changed_line_numbers={f.path: f.added_line_numbers for f in file_facts},
        accepted_coverage=accepted_coverage,
        rejected_coverage=rejected_coverage,
    )

    return PRFacts(
        title=bundle.title,
        description=bundle.description,
        files=file_facts,
        dependency_edges=dep_edges,
        coverage=coverage_facts,
    )
