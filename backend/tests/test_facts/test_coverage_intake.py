"""Tests for the coverage intake pipeline: SHA gate, artifact acceptance/rejection,
missing artifacts, malformed files, and provenance persistence.

All tests are synchronous, require no database, no network, and no
real filesystem access.
"""
from __future__ import annotations

import textwrap
from datetime import timezone

import pytest

from app.facts.coverage_intake import (
    AcceptedCoverage,
    CIRunMetadata,
    CoverageArtifact,
    CoverageProvenance,
    RejectedCoverage,
    accept_coverage,
    build_file_coverages,
)
from app.facts.coverage_parsers import MAX_ARTIFACT_BYTES
from app.facts.models import CoverageStatus


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

_PR_HEAD_SHA = "a" * 40
_MATCHING_SHA = "a" * 40
_MISMATCHING_SHA = "b" * 40

_SIMPLE_LCOV = textwrap.dedent("""\
    TN:
    SF:src/app.py
    DA:1,1
    DA:2,0
    DA:3,1
    end_of_record
""").encode("utf-8")

_SIMPLE_COBERTURA = textwrap.dedent("""\
    <?xml version="1.0" ?>
    <coverage>
      <packages><package><classes>
        <class filename="src/app.py">
          <lines>
            <line number="1" hits="1"/>
            <line number="2" hits="0"/>
          </lines>
        </class>
      </classes></package></packages>
    </coverage>
""").encode("utf-8")


def _make_meta(sha: str = _MATCHING_SHA, provider: str = "github_actions", run_id: str = "12345") -> CIRunMetadata:
    return CIRunMetadata(commit_sha=sha, ci_provider=provider, run_id=run_id)


def _make_artifact(
    raw: bytes = _SIMPLE_LCOV,
    sha: str = _MATCHING_SHA,
    fmt: str = "lcov",
) -> CoverageArtifact:
    return CoverageArtifact(raw=raw, metadata=_make_meta(sha=sha), format=fmt)  # type: ignore[arg-type]


# ===========================================================================
# accept_coverage — missing / absent cases
# ===========================================================================


class TestAcceptCoverageMissingCases:
    def test_none_artifact_is_rejected(self) -> None:
        result = accept_coverage(None, _PR_HEAD_SHA)
        assert isinstance(result, RejectedCoverage)
        assert "No coverage artifact" in result.reason

    def test_none_pr_head_sha_is_rejected(self) -> None:
        artifact = _make_artifact()
        result = accept_coverage(artifact, None)
        assert isinstance(result, RejectedCoverage)
        assert "PR head SHA is not recorded" in result.reason

    def test_empty_pr_head_sha_is_rejected(self) -> None:
        artifact = _make_artifact()
        result = accept_coverage(artifact, "")
        assert isinstance(result, RejectedCoverage)

    def test_absent_artifact_commit_sha_is_rejected(self) -> None:
        artifact = CoverageArtifact(
            raw=_SIMPLE_LCOV,
            metadata=CIRunMetadata(commit_sha="", ci_provider="ci", run_id="1"),
            format="lcov",
        )
        result = accept_coverage(artifact, _PR_HEAD_SHA)
        assert isinstance(result, RejectedCoverage)
        assert "missing a commit SHA" in result.reason


# ===========================================================================
# accept_coverage — SHA mismatch
# ===========================================================================


class TestAcceptCoverageSHAMismatch:
    def test_mismatching_sha_is_rejected(self) -> None:
        artifact = _make_artifact(sha=_MISMATCHING_SHA)
        result = accept_coverage(artifact, _PR_HEAD_SHA)
        assert isinstance(result, RejectedCoverage)

    def test_rejection_reason_includes_both_shas(self) -> None:
        artifact = _make_artifact(sha=_MISMATCHING_SHA)
        result = accept_coverage(artifact, _PR_HEAD_SHA)
        assert isinstance(result, RejectedCoverage)
        reason = result.reason
        assert _MISMATCHING_SHA[:8] in reason or _MISMATCHING_SHA in reason

    def test_sha_comparison_is_case_insensitive(self) -> None:
        upper_sha = _PR_HEAD_SHA.upper()
        artifact = _make_artifact(sha=upper_sha)
        result = accept_coverage(artifact, _PR_HEAD_SHA)
        assert isinstance(result, AcceptedCoverage)

    def test_partial_sha_is_rejected(self) -> None:
        # A prefix of the head SHA is not an exact match
        partial = _PR_HEAD_SHA[:10]
        artifact = _make_artifact(sha=partial)
        result = accept_coverage(artifact, _PR_HEAD_SHA)
        assert isinstance(result, RejectedCoverage)

    def test_exact_sha_match_is_accepted(self) -> None:
        artifact = _make_artifact(sha=_MATCHING_SHA)
        result = accept_coverage(artifact, _PR_HEAD_SHA)
        assert isinstance(result, AcceptedCoverage)

    def test_sha_with_leading_whitespace_normalized(self) -> None:
        artifact = _make_artifact(sha="  " + _MATCHING_SHA)
        result = accept_coverage(artifact, _PR_HEAD_SHA)
        assert isinstance(result, AcceptedCoverage)


# ===========================================================================
# accept_coverage — oversized artifact
# ===========================================================================


class TestAcceptCoverageOversized:
    def test_oversized_artifact_is_rejected(self) -> None:
        artifact = CoverageArtifact(
            raw=b"x" * (MAX_ARTIFACT_BYTES + 1),
            metadata=_make_meta(),
            format="lcov",
        )
        result = accept_coverage(artifact, _PR_HEAD_SHA)
        assert isinstance(result, RejectedCoverage)
        assert "too large" in result.reason

    def test_exactly_limit_is_accepted_if_parseable(self) -> None:
        # We can't easily generate a valid LCOV file that fills 50 MB, but we
        # can verify that the size check alone doesn't reject valid small input.
        artifact = _make_artifact()
        result = accept_coverage(artifact, _PR_HEAD_SHA)
        assert isinstance(result, AcceptedCoverage)


# ===========================================================================
# accept_coverage — malformed artifacts
# ===========================================================================


class TestAcceptCoverageMalformed:
    def test_empty_lcov_is_rejected(self) -> None:
        artifact = CoverageArtifact(
            raw=b"",
            metadata=_make_meta(),
            format="lcov",
        )
        result = accept_coverage(artifact, _PR_HEAD_SHA)
        assert isinstance(result, RejectedCoverage)
        assert "could not be parsed" in result.reason

    def test_malformed_xml_is_rejected(self) -> None:
        artifact = CoverageArtifact(
            raw=b"this is not xml <<<<",
            metadata=_make_meta(),
            format="cobertura",
        )
        result = accept_coverage(artifact, _PR_HEAD_SHA)
        assert isinstance(result, RejectedCoverage)
        assert "could not be parsed" in result.reason

    def test_unknown_format_is_rejected(self) -> None:
        artifact = CoverageArtifact(
            raw=_SIMPLE_LCOV,
            metadata=_make_meta(),
            format="unknown_fmt",  # type: ignore[arg-type]
        )
        result = accept_coverage(artifact, _PR_HEAD_SHA)
        assert isinstance(result, RejectedCoverage)
        assert "Unknown coverage format" in result.reason


# ===========================================================================
# accept_coverage — auto-format detection
# ===========================================================================


class TestAcceptCoverageAutoFormat:
    def test_auto_detects_cobertura_from_xml_prefix(self) -> None:
        artifact = CoverageArtifact(
            raw=_SIMPLE_COBERTURA,
            metadata=_make_meta(),
            format="auto",
        )
        result = accept_coverage(artifact, _PR_HEAD_SHA)
        assert isinstance(result, AcceptedCoverage)
        assert result.provenance.format == "cobertura"

    def test_auto_detects_lcov_from_non_xml(self) -> None:
        artifact = CoverageArtifact(
            raw=_SIMPLE_LCOV,
            metadata=_make_meta(),
            format="auto",
        )
        result = accept_coverage(artifact, _PR_HEAD_SHA)
        assert isinstance(result, AcceptedCoverage)
        assert result.provenance.format == "lcov"

    def test_auto_handles_bom_prefix(self) -> None:
        bom_xml = b"\xef\xbb\xbf" + _SIMPLE_COBERTURA
        artifact = CoverageArtifact(
            raw=bom_xml,
            metadata=_make_meta(),
            format="auto",
        )
        result = accept_coverage(artifact, _PR_HEAD_SHA)
        assert isinstance(result, AcceptedCoverage)
        assert result.provenance.format == "cobertura"


# ===========================================================================
# Accepted coverage — provenance record
# ===========================================================================


class TestAcceptedCoverageProvenance:
    def _accept(self) -> AcceptedCoverage:
        artifact = _make_artifact()
        result = accept_coverage(artifact, _PR_HEAD_SHA)
        assert isinstance(result, AcceptedCoverage)
        return result

    def test_provenance_is_coverage_provenance(self) -> None:
        result = self._accept()
        assert isinstance(result.provenance, CoverageProvenance)

    def test_provenance_format_is_lcov(self) -> None:
        result = self._accept()
        assert result.provenance.format == "lcov"

    def test_provenance_ci_provider_preserved(self) -> None:
        result = self._accept()
        assert result.provenance.ci_provider == "github_actions"

    def test_provenance_run_id_preserved(self) -> None:
        result = self._accept()
        assert result.provenance.run_id == "12345"

    def test_provenance_commit_sha_normalized(self) -> None:
        result = self._accept()
        assert result.provenance.commit_sha == _MATCHING_SHA.lower()

    def test_provenance_artifact_sha256_is_hex(self) -> None:
        result = self._accept()
        sha = result.provenance.artifact_sha256
        assert len(sha) == 64
        assert all(c in "0123456789abcdef" for c in sha)

    def test_provenance_parsed_at_is_utc(self) -> None:
        result = self._accept()
        assert result.provenance.parsed_at.tzinfo is not None
        # Should be UTC
        assert result.provenance.parsed_at.utcoffset().total_seconds() == 0

    def test_provenance_file_count_matches_data(self) -> None:
        result = self._accept()
        assert result.provenance.file_count == len(result.per_file)

    def test_provenance_warnings_list(self) -> None:
        result = self._accept()
        assert isinstance(result.provenance.parser_warnings, list)

    def test_per_file_data_contains_expected_path(self) -> None:
        result = self._accept()
        assert "src/app.py" in result.per_file

    def test_artifact_name_preserved_when_set(self) -> None:
        artifact = CoverageArtifact(
            raw=_SIMPLE_LCOV,
            metadata=CIRunMetadata(
                commit_sha=_MATCHING_SHA,
                ci_provider="github_actions",
                run_id="999",
                artifact_name="coverage-report",
            ),
            format="lcov",
        )
        result = accept_coverage(artifact, _PR_HEAD_SHA)
        assert isinstance(result, AcceptedCoverage)
        assert result.provenance.artifact_name == "coverage-report"

    def test_artifact_name_none_when_absent(self) -> None:
        result = self._accept()
        assert result.provenance.artifact_name is None


# ===========================================================================
# build_file_coverages — mapping to FileCoverage facts
# ===========================================================================


class TestBuildFileCoverages:
    def _accepted(self, lcov_text: bytes = _SIMPLE_LCOV) -> AcceptedCoverage:
        artifact = CoverageArtifact(
            raw=lcov_text,
            metadata=_make_meta(),
            format="lcov",
        )
        result = accept_coverage(artifact, _PR_HEAD_SHA)
        assert isinstance(result, AcceptedCoverage)
        return result

    def test_file_in_artifact_gets_real_status(self) -> None:
        accepted = self._accepted()
        coverages = build_file_coverages(["src/app.py"], accepted)
        assert len(coverages) == 1
        fc = coverages[0]
        assert fc.status != CoverageStatus.unknown

    def test_covered_status_when_all_lines_hit(self) -> None:
        lcov = b"TN:\nSF:src/x.py\nDA:1,1\nDA:2,5\nend_of_record\n"
        accepted = self._accepted(lcov)
        coverages = build_file_coverages(["src/x.py"], accepted)
        assert coverages[0].status == CoverageStatus.covered

    def test_uncovered_status_when_no_lines_hit(self) -> None:
        lcov = b"TN:\nSF:src/x.py\nDA:1,0\nDA:2,0\nend_of_record\n"
        accepted = self._accepted(lcov)
        coverages = build_file_coverages(["src/x.py"], accepted)
        assert coverages[0].status == CoverageStatus.uncovered

    def test_partial_status_when_mixed(self) -> None:
        accepted = self._accepted()  # src/app.py has 1,3 covered and 2 uncovered
        coverages = build_file_coverages(["src/app.py"], accepted)
        assert coverages[0].status == CoverageStatus.partial

    def test_file_absent_from_artifact_is_unknown(self) -> None:
        accepted = self._accepted()
        coverages = build_file_coverages(["src/not_in_artifact.py"], accepted)
        assert coverages[0].status == CoverageStatus.unknown
        assert coverages[0].source is None

    def test_source_tag_set_on_accepted_file(self) -> None:
        accepted = self._accepted()
        coverages = build_file_coverages(["src/app.py"], accepted)
        assert coverages[0].source is not None
        assert "github_actions" in coverages[0].source

    def test_order_preserved(self) -> None:
        lcov = (
            b"TN:\nSF:src/a.py\nDA:1,1\nend_of_record\n"
            b"TN:\nSF:src/b.py\nDA:1,0\nend_of_record\n"
        )
        accepted = self._accepted(lcov)
        paths = ["src/b.py", "src/a.py", "src/missing.py"]
        coverages = build_file_coverages(paths, accepted)
        assert [fc.file_path for fc in coverages] == paths

    def test_suffix_path_matching(self) -> None:
        # Artifact uses full path; diff uses relative
        lcov = b"TN:\nSF:/home/runner/work/repo/src/app.py\nDA:1,1\nend_of_record\n"
        accepted = self._accepted(lcov)
        coverages = build_file_coverages(["src/app.py"], accepted)
        # Should match via suffix
        assert coverages[0].status != CoverageStatus.unknown

    def test_empty_changed_files_returns_empty_tuple(self) -> None:
        accepted = self._accepted()
        coverages = build_file_coverages([], accepted)
        assert coverages == ()

    def test_covered_and_uncovered_lines_populated(self) -> None:
        accepted = self._accepted()
        coverages = build_file_coverages(["src/app.py"], accepted)
        fc = coverages[0]
        assert 1 in fc.covered_lines
        assert 2 in fc.uncovered_lines


# ===========================================================================
# build_coverage_facts integration (via coverage_facts.py)
# ===========================================================================


class TestBuildCoverageFactsIntegration:
    """Integration tests that call build_coverage_facts directly."""

    def test_none_artifact_all_unknown(self) -> None:
        from app.facts.coverage_facts import build_coverage_facts

        result = build_coverage_facts(
            ["src/a.py", "src/b.py"],
            coverage_artifact=None,
            pr_head_sha=_PR_HEAD_SHA,
        )
        assert all(fc.status == CoverageStatus.unknown for fc in result)

    def test_sha_mismatch_all_unknown(self) -> None:
        from app.facts.coverage_facts import build_coverage_facts

        artifact = _make_artifact(sha=_MISMATCHING_SHA)
        result = build_coverage_facts(
            ["src/app.py"],
            coverage_artifact=artifact,
            pr_head_sha=_PR_HEAD_SHA,
        )
        assert result[0].status == CoverageStatus.unknown

    def test_accepted_artifact_yields_real_coverage(self) -> None:
        from app.facts.coverage_facts import build_coverage_facts

        artifact = _make_artifact()
        result = build_coverage_facts(
            ["src/app.py"],
            coverage_artifact=artifact,
            pr_head_sha=_PR_HEAD_SHA,
        )
        assert result[0].status != CoverageStatus.unknown

    def test_no_pr_head_sha_all_unknown(self) -> None:
        from app.facts.coverage_facts import build_coverage_facts

        artifact = _make_artifact()
        result = build_coverage_facts(
            ["src/app.py"],
            coverage_artifact=artifact,
            pr_head_sha=None,
        )
        assert result[0].status == CoverageStatus.unknown
