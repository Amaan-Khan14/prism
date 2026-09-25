"""Diff parsing helpers shared by both ingestion paths."""
from __future__ import annotations

from unidiff import PatchSet

from app.ingestion.bundle import FilePatch


def parse_diff(diff_text: str) -> list[FilePatch]:
    """Parse a unified diff string into a list of FilePatch objects."""
    patch_set = PatchSet(diff_text)
    patches: list[FilePatch] = []

    for patched_file in patch_set:
        added: list[tuple[int, str]] = []
        removed: list[tuple[int, str]] = []

        for hunk in patched_file:
            for line in hunk:
                if line.is_added and line.target_line_no is not None:
                    added.append((line.target_line_no, line.value.rstrip("\n")))
                elif line.is_removed and line.source_line_no is not None:
                    removed.append((line.source_line_no, line.value.rstrip("\n")))

        patches.append(
            FilePatch(
                path=patched_file.path,
                old_path=patched_file.source_file if patched_file.is_rename else None,
                is_new_file=patched_file.is_added_file,
                is_deleted_file=patched_file.is_removed_file,
                is_rename=patched_file.is_rename,
                added_lines=added,
                removed_lines=removed,
            )
        )

    return patches
