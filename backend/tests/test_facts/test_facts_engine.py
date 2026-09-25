"""Tests for the facts engine.

All tests are synchronous and require no database, no network, and no
real filesystem beyond reading the authored fixture in tests/fixtures/.
"""
from __future__ import annotations

import pathlib
import textwrap

import pytest

from app.facts import compute_facts
from app.facts.coverage_facts import build_coverage_facts
from app.facts.diff_facts import _coalesce_line_numbers, extract_diff_facts, patch_to_file_facts
from app.facts.models import (
    CoverageStatus,
    DependencyEdge,
    FileCoverage,
    FileFacts,
    ImportKind,
    LineRange,
    PRFacts,
)
from app.facts.python_deps import extract_python_deps, _ast_imports
from app.ingestion.bundle import FilePatch, PRBundle
from app.ingestion.diff_parser import parse_diff

# ---------------------------------------------------------------------------
# Path to authored fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = pathlib.Path(__file__).parent.parent / "fixtures"
SAMPLE_PATCH = FIXTURES_DIR / "sample_pr.patch"
SAMPLE_MODULE = FIXTURES_DIR / "sample_module.py"


# ===========================================================================
# LineRange
# ===========================================================================


class TestLineRange:
    def test_basic_construction(self) -> None:
        r = LineRange(3, 7)
        assert r.start == 3
        assert r.end == 7

    def test_single_line(self) -> None:
        r = LineRange(5, 5)
        assert 5 in r
        assert 4 not in r
        assert 6 not in r

    def test_contains(self) -> None:
        r = LineRange(10, 20)
        assert 10 in r
        assert 15 in r
        assert 20 in r
        assert 9 not in r
        assert 21 not in r

    def test_overlaps_true(self) -> None:
        a = LineRange(1, 10)
        b = LineRange(8, 15)
        assert a.overlaps(b)
        assert b.overlaps(a)

    def test_overlaps_adjacent_is_false(self) -> None:
        a = LineRange(1, 5)
        b = LineRange(6, 10)
        assert not a.overlaps(b)

    def test_overlaps_touching_single_line(self) -> None:
        a = LineRange(1, 5)
        b = LineRange(5, 10)
        assert a.overlaps(b)

    def test_invalid_start(self) -> None:
        with pytest.raises(ValueError, match="start must be >= 1"):
            LineRange(0, 5)

    def test_invalid_end_less_than_start(self) -> None:
        with pytest.raises(ValueError, match="end must be >= start"):
            LineRange(5, 3)

    def test_frozen(self) -> None:
        r = LineRange(1, 5)
        with pytest.raises((AttributeError, TypeError)):
            r.start = 99  # type: ignore[misc]


# ===========================================================================
# _coalesce_line_numbers
# ===========================================================================


class TestCoalesceLineNumbers:
    def test_empty(self) -> None:
        assert _coalesce_line_numbers(frozenset()) == ()

    def test_single_line(self) -> None:
        result = _coalesce_line_numbers(frozenset({5}))
        assert result == (LineRange(5, 5),)

    def test_contiguous_run(self) -> None:
        result = _coalesce_line_numbers(frozenset({1, 2, 3}))
        assert result == (LineRange(1, 3),)

    def test_two_separate_runs(self) -> None:
        result = _coalesce_line_numbers(frozenset({1, 2, 3, 7, 8}))
        assert result == (LineRange(1, 3), LineRange(7, 8))

    def test_unsorted_input_sorted_output(self) -> None:
        result = _coalesce_line_numbers(frozenset({10, 2, 3, 1}))
        assert result == (LineRange(1, 3), LineRange(10, 10))

    def test_no_gaps(self) -> None:
        nums = frozenset(range(100, 120))
        result = _coalesce_line_numbers(nums)
        assert result == (LineRange(100, 119),)


# ===========================================================================
# patch_to_file_facts
# ===========================================================================


class TestPatchToFileFacts:
    def _make_patch(
        self,
        path: str = "app/foo.py",
        added: list[tuple[int, str]] | None = None,
        removed: list[tuple[int, str]] | None = None,
        is_new: bool = False,
        is_deleted: bool = False,
        is_rename: bool = False,
        old_path: str | None = None,
    ) -> FilePatch:
        return FilePatch(
            path=path,
            old_path=old_path,
            is_new_file=is_new,
            is_deleted_file=is_deleted,
            is_rename=is_rename,
            added_lines=added or [],
            removed_lines=removed or [],
        )

    def test_basic_added_and_removed(self) -> None:
        patch = self._make_patch(
            added=[(3, "+new line"), (4, "+another")],
            removed=[(2, "-old line")],
        )
        facts = patch_to_file_facts(patch)
        assert isinstance(facts, FileFacts)
        assert facts.path == "app/foo.py"
        assert facts.added_line_numbers == frozenset({3, 4})
        assert facts.removed_line_numbers == frozenset({2})
        assert facts.total_added == 2
        assert facts.total_removed == 1

    def test_added_ranges_coalesced(self) -> None:
        patch = self._make_patch(added=[(1, "a"), (2, "b"), (5, "c")])
        facts = patch_to_file_facts(patch)
        assert facts.added_ranges == (LineRange(1, 2), LineRange(5, 5))

    def test_new_file_flags(self) -> None:
        patch = self._make_patch(is_new=True, added=[(1, "x")])
        facts = patch_to_file_facts(patch)
        assert facts.is_new_file is True
        assert facts.is_deleted_file is False

    def test_rename_preserves_old_path(self) -> None:
        patch = self._make_patch(is_rename=True, old_path="app/old.py")
        facts = patch_to_file_facts(patch)
        assert facts.is_rename is True
        assert facts.old_path == "app/old.py"

    def test_empty_patch(self) -> None:
        patch = self._make_patch()
        facts = patch_to_file_facts(patch)
        assert facts.added_line_numbers == frozenset()
        assert facts.removed_line_numbers == frozenset()
        assert facts.added_ranges == ()
        assert facts.removed_ranges == ()


# ===========================================================================
# extract_diff_facts — uses authored fixture
# ===========================================================================


class TestExtractDiffFacts:
    def _load_fixture(self) -> list[FilePatch]:
        diff_text = SAMPLE_PATCH.read_text()
        return parse_diff(diff_text)

    def test_fixture_parses_two_files(self) -> None:
        patches = self._load_fixture()
        assert len(patches) == 2

    def test_fixture_first_file_is_python(self) -> None:
        patches = self._load_fixture()
        assert patches[0].path.endswith("sample_module.py")

    def test_fixture_second_file_is_yaml_new_file(self) -> None:
        patches = self._load_fixture()
        yaml_patch = patches[1]
        assert yaml_patch.path.endswith("config.yaml")
        assert yaml_patch.is_new_file is True

    def test_fixture_python_file_has_additions(self) -> None:
        patches = self._load_fixture()
        py_patch = patches[0]
        assert len(py_patch.added_lines) > 0

    def test_extract_returns_file_facts_tuple(self) -> None:
        diff_text = SAMPLE_PATCH.read_text()
        patches = parse_diff(diff_text)
        bundle = PRBundle(
            title="Add DiffStats class",
            description="Adds a lightweight DiffStats container and updates imports.",
            diff_raw=diff_text,
            patches=patches,
        )
        file_facts = extract_diff_facts(bundle)
        assert isinstance(file_facts, tuple)
        assert len(file_facts) == 2
        assert all(isinstance(f, FileFacts) for f in file_facts)

    def test_file_facts_line_numbers_are_positive(self) -> None:
        diff_text = SAMPLE_PATCH.read_text()
        patches = parse_diff(diff_text)
        bundle = PRBundle(
            title="test",
            description="",
            diff_raw=diff_text,
            patches=patches,
        )
        for ff in extract_diff_facts(bundle):
            for ln in ff.added_line_numbers:
                assert ln >= 1, f"line number {ln} < 1 in {ff.path}"
            for ln in ff.removed_line_numbers:
                assert ln >= 1, f"line number {ln} < 1 in {ff.path}"

    def test_file_facts_ranges_cover_all_lines(self) -> None:
        """Every added/removed line number must fall within a declared range."""
        diff_text = SAMPLE_PATCH.read_text()
        patches = parse_diff(diff_text)
        bundle = PRBundle(
            title="test",
            description="",
            diff_raw=diff_text,
            patches=patches,
        )
        for ff in extract_diff_facts(bundle):
            for ln in ff.added_line_numbers:
                assert any(ln in r for r in ff.added_ranges), (
                    f"Line {ln} in {ff.path} not covered by any added_range"
                )
            for ln in ff.removed_line_numbers:
                assert any(ln in r for r in ff.removed_ranges), (
                    f"Line {ln} in {ff.path} not covered by any removed_range"
                )


# ===========================================================================
# Python dependency analysis
# ===========================================================================


class TestAstImports:
    def test_simple_import(self) -> None:
        source = "import os\nimport sys\n"
        edges = _ast_imports(source, "app/foo.py")
        modules = {e.imported_module for e in edges}
        assert "os" in modules
        assert "sys" in modules

    def test_from_import(self) -> None:
        source = "from pathlib import Path\n"
        edges = _ast_imports(source, "app/foo.py")
        assert len(edges) == 1
        assert edges[0].imported_module == "pathlib"
        assert edges[0].import_kind == ImportKind.absolute

    def test_relative_import(self) -> None:
        source = "from .models import MyModel\n"
        edges = _ast_imports(source, "app/foo.py")
        assert len(edges) == 1
        assert edges[0].import_kind == ImportKind.relative
        assert edges[0].imported_module == ".models"

    def test_relative_import_bare_dot(self) -> None:
        source = "from . import utils\n"
        edges = _ast_imports(source, "app/foo.py")
        assert len(edges) == 1
        assert edges[0].import_kind == ImportKind.relative
        assert edges[0].imported_module == ".utils"

    def test_double_relative_import(self) -> None:
        source = "from ..base import Base\n"
        edges = _ast_imports(source, "app/sub/foo.py")
        assert len(edges) == 1
        assert edges[0].imported_module == "..base"

    def test_line_number_recorded(self) -> None:
        source = textwrap.dedent("""\
            # comment
            import os
            import sys
        """)
        edges = _ast_imports(source, "app/foo.py")
        linenos = {e.lineno for e in edges}
        assert 2 in linenos
        assert 3 in linenos

    def test_syntax_error_returns_empty(self) -> None:
        source = "def broken(\n"
        edges = _ast_imports(source, "bad.py")
        assert edges == []

    def test_empty_file(self) -> None:
        edges = _ast_imports("", "app/empty.py")
        assert edges == []

    def test_from_file_is_correct(self) -> None:
        source = "from app.models import Foo\n"
        edges = _ast_imports(source, "app/service.py")
        assert edges[0].from_file == "app/service.py"


class TestExtractPythonDeps:
    def test_non_python_files_skipped(self) -> None:
        edges = extract_python_deps(
            changed_py_files=["config.yaml", "README.md"],
            file_source_map={"config.yaml": "key: value\n"},
        )
        assert edges == ()

    def test_missing_source_skipped(self) -> None:
        # File listed as changed but not in source map → no edges, no error
        edges = extract_python_deps(
            changed_py_files=["app/missing.py"],
            file_source_map={},
        )
        assert edges == ()

    def test_fixture_module_has_expected_imports(self) -> None:
        source = SAMPLE_MODULE.read_text()
        edges = extract_python_deps(
            changed_py_files=["backend/tests/fixtures/sample_module.py"],
            file_source_map={"backend/tests/fixtures/sample_module.py": source},
        )
        modules = {e.imported_module for e in edges}
        assert "__future__" in modules
        assert "hashlib" in modules
        assert "logging" in modules
        # typing.Optional
        assert "typing" in modules

    def test_edges_are_tuple(self) -> None:
        edges = extract_python_deps(
            changed_py_files=["app/x.py"],
            file_source_map={"app/x.py": "import os\n"},
        )
        assert isinstance(edges, tuple)
        assert len(edges) == 1
        assert isinstance(edges[0], DependencyEdge)


# ===========================================================================
# Coverage facts
# ===========================================================================


class TestBuildCoverageFacts:
    def test_all_files_are_unknown(self) -> None:
        paths = ["app/foo.py", "app/bar.py", "config.yaml"]
        result = build_coverage_facts(paths)
        assert len(result) == 3
        for fc in result:
            assert fc.status == CoverageStatus.unknown
            assert fc.covered_lines == frozenset()
            assert fc.uncovered_lines == frozenset()
            assert fc.source is None

    def test_preserves_path_order(self) -> None:
        paths = ["z.py", "a.py", "m.py"]
        result = build_coverage_facts(paths)
        assert [fc.file_path for fc in result] == paths

    def test_empty_input(self) -> None:
        result = build_coverage_facts([])
        assert result == ()

    def test_real_artifact_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError):
            build_coverage_facts(["x.py"], coverage_artifact=object())


# ===========================================================================
# compute_facts — end-to-end with authored fixture
# ===========================================================================


class TestComputeFacts:
    def _make_bundle(self) -> PRBundle:
        diff_text = SAMPLE_PATCH.read_text()
        patches = parse_diff(diff_text)
        return PRBundle(
            title="Add DiffStats class",
            description=(
                "Adds a DiffStats container with added/removed counts and net delta. "
                "Updates imports: replaces List with Optional."
            ),
            diff_raw=diff_text,
            patches=patches,
        )

    def test_returns_pr_facts(self) -> None:
        bundle = self._make_bundle()
        facts = compute_facts(bundle)
        assert isinstance(facts, PRFacts)

    def test_title_and_description_preserved(self) -> None:
        bundle = self._make_bundle()
        facts = compute_facts(bundle)
        assert facts.title == bundle.title
        assert facts.description == bundle.description

    def test_two_changed_files(self) -> None:
        bundle = self._make_bundle()
        facts = compute_facts(bundle)
        assert len(facts.files) == 2

    def test_coverage_is_all_unknown(self) -> None:
        bundle = self._make_bundle()
        facts = compute_facts(bundle)
        assert len(facts.coverage) == 2
        for fc in facts.coverage:
            assert fc.status == CoverageStatus.unknown

    def test_no_deps_without_source_map(self) -> None:
        """Without a source map, no dependency edges should be emitted."""
        bundle = self._make_bundle()
        facts = compute_facts(bundle, file_source_map=None)
        assert facts.dependency_edges == ()

    def test_deps_with_source_map(self) -> None:
        """Providing the Python source produces dependency edges."""
        bundle = self._make_bundle()
        py_path = bundle.patches[0].path
        source = SAMPLE_MODULE.read_text()
        facts = compute_facts(bundle, file_source_map={py_path: source})
        assert len(facts.dependency_edges) > 0
        assert all(isinstance(e, DependencyEdge) for e in facts.dependency_edges)

    def test_changed_file_paths_property(self) -> None:
        bundle = self._make_bundle()
        facts = compute_facts(bundle)
        paths = facts.changed_file_paths
        assert len(paths) == 2
        assert any(p.endswith("sample_module.py") for p in paths)
        assert any(p.endswith("config.yaml") for p in paths)

    def test_total_added_lines_positive(self) -> None:
        bundle = self._make_bundle()
        facts = compute_facts(bundle)
        assert facts.total_added_lines > 0

    def test_yaml_file_has_no_dep_edges(self) -> None:
        """Non-.py files must not produce dependency edges."""
        bundle = self._make_bundle()
        yaml_path = next(p.path for p in bundle.patches if p.path.endswith(".yaml"))
        facts = compute_facts(bundle, file_source_map={yaml_path: "key: val\n"})
        # No edges should come from the yaml file
        yaml_edges = [e for e in facts.dependency_edges if e.from_file == yaml_path]
        assert yaml_edges == []

    def test_pr_facts_is_frozen_dataclass(self) -> None:
        """PRFacts must be immutable."""
        bundle = self._make_bundle()
        facts = compute_facts(bundle)
        with pytest.raises((AttributeError, TypeError)):
            facts.title = "mutated"  # type: ignore[misc]
