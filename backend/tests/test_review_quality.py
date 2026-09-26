import json

import httpx
import pytest

from app.facts.models import CoverageStatus, FileCoverage, PRFacts
from app.gate.models import EvidenceCitation, EvidenceKind
from app.models import FacetKind
from app.review.orchestration import _review_one_facet
from app.review.provider import (
    ReviewProviderError,
    _post_with_retry,
    _FACET_CLAIMS,
    _facet_prompts,
    _parse_findings,
)


def _facts(*, coverage: tuple[FileCoverage, ...] = ()) -> PRFacts:
    return PRFacts(
        title="Review quality fixture",
        description="",
        files=(),
        dependency_edges=(),
        coverage=coverage,
    )


def test_coverage_prompt_omits_unknown_as_a_finding() -> None:
    system, _ = _facet_prompts(
        FacetKind.test_coverage_gaps,
        _facts(coverage=(FileCoverage("src/app.go", CoverageStatus.unknown),)),
        "",
    )

    assert "Unknown or missing coverage is not a finding" in system
    assert _FACET_CLAIMS[FacetKind.test_coverage_gaps] == () or all(
        claim.value != "coverage_unknown"
        for claim in _FACET_CLAIMS[FacetKind.test_coverage_gaps]
    )


def test_cross_file_review_receives_the_patch_context() -> None:
    diff = "diff --git a/main.go b/main.go\n+callChangedDependency()\n"
    _, user_input = _facet_prompts(FacetKind.cross_file_impact, _facts(), diff)

    assert json.loads(user_input)["diff"] == diff


def test_risk_review_traces_changed_settings_against_in_flight_work() -> None:
    system, _ = _facet_prompts(FacetKind.risk_hazards, _facts(), "diff")

    assert "before the setting changes, at the change, and when the existing work completes" in system
    assert "cancelled or rescheduled" in system
    assert "cite the changed setting assignment" in system
    assert "verify the relevant API contract" in system


def test_review_prompt_limits_citations_to_lines_that_establish_the_defect() -> None:
    system, _ = _facet_prompts(FacetKind.intent_vs_spec, _facts(), "diff")

    assert "omit declarations and background lines" in system
    assert "never more than two" in system


def test_provider_cannot_return_unknown_coverage_claim() -> None:
    with pytest.raises(ReviewProviderError):
        _parse_findings(
            json.dumps(
                {
                    "findings": [
                        {
                            "claim": "coverage_unknown",
                            "summary": "Coverage is unavailable.",
                            "severity": 1,
                            "citations": [],
                        }
                    ]
                }
            ),
            FacetKind.test_coverage_gaps,
        )


@pytest.mark.asyncio
async def test_coverage_facet_skips_model_when_coverage_is_unknown() -> None:
    class Provider:
        called = False

        async def review_facet(self, facet, facts, diff_raw):
            self.called = True
            return ()

    provider = Provider()
    facts = _facts(coverage=(FileCoverage("src/app.go", CoverageStatus.unknown),))

    facet, findings, error = await _review_one_facet(
        provider, FacetKind.test_coverage_gaps, facts, "diff"
    )

    assert facet is FacetKind.test_coverage_gaps
    assert findings == ()
    assert error is None
    assert provider.called is False


@pytest.mark.asyncio
async def test_cross_file_facet_skips_model_without_dependency_edges() -> None:
    class Provider:
        called = False

        async def review_facet(self, facet, facts, diff_raw):
            self.called = True
            return ()

    provider = Provider()
    facet, findings, error = await _review_one_facet(
        provider, FacetKind.cross_file_impact, _facts(), "diff"
    )

    assert facet is FacetKind.cross_file_impact
    assert findings == ()
    assert error is None
    assert provider.called is False


def test_non_dependency_citation_does_not_keep_imported_module_noise() -> None:
    finding = _parse_findings(
        json.dumps(
            {
                "findings": [
                    {
                        "claim": "code",
                        "summary": "Handle this error before returning.",
                        "severity": 2,
                        "citations": [
                            {
                                "kind": "added_line",
                                "file_path": "main.go",
                                "line_number": 7,
                                "imported_module": "os",
                            }
                        ],
                    }
                ]
            }
        ),
        FacetKind.risk_hazards,
    )[0]

    assert finding.citations == (
        EvidenceCitation(EvidenceKind.added_line, "main.go", 7, None),
    )


@pytest.mark.asyncio
async def test_provider_retries_transient_overload() -> None:
    calls = 0

    async def respond(_request):
        nonlocal calls
        calls += 1
        status = 503 if calls == 1 else 200
        return httpx.Response(status, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        response = await _post_with_retry(client, "https://provider.test/review")

    assert response.status_code == 200
    assert calls == 2
