"""Evidence gate for structured review findings.

The gate does not infer whether prose is true. It verifies the structured
claim/evidence contract against :class:`PRFacts`, then partitions findings so
unsupported items cannot be promoted to the verified brief.
"""
from __future__ import annotations

from app.facts.models import CoverageStatus, PRFacts
from app.gate.models import (
    CitationCheck,
    EvidenceCitation,
    EvidenceGateResult,
    EvidenceKind,
    EvidenceVerdict,
    FindingCandidate,
    FindingClaim,
    GatedFinding,
)


_CLAIM_EVIDENCE = {
    FindingClaim.code: EvidenceKind.added_line,
    FindingClaim.dependency: EvidenceKind.dependency_edge,
    FindingClaim.coverage_gap: EvidenceKind.coverage,
    FindingClaim.coverage_unknown: EvidenceKind.coverage,
}


def _check_citation(
    citation: EvidenceCitation,
    facts: PRFacts,
    claim: FindingClaim,
) -> CitationCheck:
    expected_kind = _CLAIM_EVIDENCE[claim]
    if citation.kind is not expected_kind:
        return CitationCheck(citation, False, "citation_kind_mismatch")

    if citation.kind is EvidenceKind.added_line:
        file_facts = next(
            (item for item in facts.files if item.path == citation.file_path), None
        )
        if file_facts is None:
            return CitationCheck(citation, False, "file_not_in_diff")
        if citation.line_number is None:
            return CitationCheck(citation, False, "line_number_required")
        if citation.line_number not in file_facts.added_line_numbers:
            return CitationCheck(citation, False, "line_not_added")
        return CitationCheck(citation, True, "added_line_verified")

    if citation.kind is EvidenceKind.dependency_edge:
        if citation.line_number is None:
            return CitationCheck(citation, False, "line_number_required")
        if not any(
            edge.from_file == citation.file_path
            and edge.lineno == citation.line_number
            and edge.imported_module == citation.imported_module
            for edge in facts.dependency_edges
        ):
            return CitationCheck(citation, False, "dependency_edge_not_found")
        return CitationCheck(citation, True, "dependency_edge_verified")

    coverage = next(
        (item for item in facts.coverage if item.file_path == citation.file_path), None
    )
    if coverage is None:
        return CitationCheck(citation, False, "coverage_file_not_found")

    if claim is FindingClaim.coverage_unknown:
        if coverage.status is not CoverageStatus.unknown:
            return CitationCheck(citation, False, "coverage_is_known")
        if citation.line_number is not None:
            return CitationCheck(citation, False, "line_number_not_applicable")
        return CitationCheck(citation, True, "coverage_unknown_verified")

    if citation.line_number is None:
        return CitationCheck(citation, False, "line_number_required")
    if coverage.status is CoverageStatus.unknown:
        return CitationCheck(citation, False, "coverage_unknown")
    if citation.line_number not in coverage.uncovered_lines:
        return CitationCheck(citation, False, "line_not_uncovered")
    return CitationCheck(citation, True, "uncovered_line_verified")


def _gate_one(finding: FindingCandidate, facts: PRFacts) -> GatedFinding:
    if not finding.citations:
        return GatedFinding(
            finding=finding,
            verdict=EvidenceVerdict.unverified,
            citation_checks=(),
            reasons=("missing_citation",),
        )

    checks = tuple(
        _check_citation(citation, facts, finding.claim)
        for citation in finding.citations
    )
    reasons = tuple(dict.fromkeys(
        check.reason for check in checks if not check.supported
    ))
    verdict = (
        EvidenceVerdict.verified
        if all(check.supported for check in checks)
        else EvidenceVerdict.unverified
    )
    return GatedFinding(
        finding=finding,
        verdict=verdict,
        citation_checks=checks,
        reasons=reasons,
    )


def gate_findings(
    findings: tuple[FindingCandidate, ...] | list[FindingCandidate],
    facts: PRFacts,
) -> EvidenceGateResult:
    """Verify each finding against deterministic facts and partition results.

    All citations attached to a finding must validate. Findings with missing,
    mismatched, or unsupported citations are retained as unverified for an
    appendix. In particular, a coverage-gap claim is unverified while coverage
    is unknown, and a statement that coverage is unknown requires a matching
    file-level unknown-coverage citation.
    """
    return EvidenceGateResult(
        findings=tuple(_gate_one(finding, facts) for finding in findings)
    )
