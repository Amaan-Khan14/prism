"""Diff-based facts extraction.

Converts a :class:`~app.ingestion.bundle.PRBundle` into per-file
:class:`~app.facts.models.FileFacts` structs.  All values are derived
directly from the parsed diff; no LLM inference is performed.
"""
from __future__ import annotations

from app.facts.models import FileFacts, LineRange
from app.ingestion.bundle import FilePatch, PRBundle


def _coalesce_line_numbers(line_numbers: frozenset[int]) -> tuple[LineRange, ...]:
    """Merge a set of line numbers into contiguous :class:`LineRange` spans.

    Lines that differ by exactly 1 are merged into a single range.
    Returns ranges sorted by start line.

    Examples::

        {1, 2, 3, 7, 8} -> [LineRange(1,3), LineRange(7,8)]
        {5}              -> [LineRange(5,5)]
        {}               -> []
    """
    if not line_numbers:
        return ()
    sorted_lines = sorted(line_numbers)
    ranges: list[LineRange] = []
    run_start = sorted_lines[0]
    run_end = sorted_lines[0]
    for ln in sorted_lines[1:]:
        if ln == run_end + 1:
            run_end = ln
        else:
            ranges.append(LineRange(run_start, run_end))
            run_start = ln
            run_end = ln
    ranges.append(LineRange(run_start, run_end))
    return tuple(ranges)


def patch_to_file_facts(patch: FilePatch) -> FileFacts:
    """Convert a single :class:`FilePatch` into a :class:`FileFacts` struct."""
    added_nums = frozenset(ln for ln, _ in patch.added_lines)
    removed_nums = frozenset(ln for ln, _ in patch.removed_lines)
    return FileFacts(
        path=patch.path,
        old_path=patch.old_path,
        is_new_file=patch.is_new_file,
        is_deleted_file=patch.is_deleted_file,
        is_rename=patch.is_rename,
        added_line_numbers=added_nums,
        removed_line_numbers=removed_nums,
        added_ranges=_coalesce_line_numbers(added_nums),
        removed_ranges=_coalesce_line_numbers(removed_nums),
    )


def extract_diff_facts(bundle: PRBundle) -> tuple[FileFacts, ...]:
    """Return one :class:`FileFacts` per file patch in *bundle*.

    Order mirrors the order patches appear in the unified diff.
    """
    return tuple(patch_to_file_facts(p) for p in bundle.patches)
