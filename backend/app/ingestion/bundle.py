"""PRBundle — the normalised struct consumed by the facts engine.

Both ingestion paths (GitHub PR URL and raw diff upload) produce a PRBundle.
The facts engine only ever sees a PRBundle; it never touches ingestion details.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FilePatch:
    """Parsed diff for a single file."""

    path: str
    """Target file path (b-side of the diff)."""

    old_path: str | None
    """Source file path (a-side); set only when the file was renamed."""

    is_new_file: bool
    is_deleted_file: bool
    is_rename: bool

    added_lines: list[tuple[int, str]]
    """List of (line_number, line_content) for added lines."""

    removed_lines: list[tuple[int, str]]
    """List of (line_number, line_content) for removed lines."""


@dataclass
class PRBundle:
    """Normalised pull-request representation passed to the facts engine."""

    title: str
    description: str
    """PR body — used as the spec for the intent-vs-spec facet."""

    diff_raw: str
    """Original unified diff text, preserved for reference."""

    patches: list[FilePatch] = field(default_factory=list)
    """Parsed per-file patches derived from diff_raw."""

    # Optional metadata populated by GitHubIngestion
    github_pr_url: str | None = None
    head_sha: str | None = None
    base_sha: str | None = None
    repo_full_name: str | None = None
    pr_number: int | None = None

    @property
    def changed_files(self) -> list[str]:
        return [p.path for p in self.patches]

    @property
    def total_additions(self) -> int:
        return sum(len(p.added_lines) for p in self.patches)

    @property
    def total_deletions(self) -> int:
        return sum(len(p.removed_lines) for p in self.patches)
