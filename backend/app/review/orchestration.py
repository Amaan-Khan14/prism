"""Background review orchestration from stored PR input through evidence gate."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from dataclasses import asdict

from sqlalchemy import desc, select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.facts import compute_facts
from app.facts.coverage_intake import (
    AcceptedCoverage,
    CIRunMetadata,
    CoverageArtifact,
    RejectedCoverage,
    accept_coverage,
)
from app.facts.models import PRFacts
from app.gate import (
    CitationCheck,
    EvidenceCitation,
    EvidenceVerdict,
    FindingCandidate,
    gate_findings,
)
from app.models import (
    Analysis,
    AnalysisStatus,
    CoverageArtifactRecord,
    Facet,
    FacetKind,
    FacetStatus,
    Finding,
    FindingVerdict,
    PR,
)
from app.review.provider import ReviewProvider, get_review_provider
from app.storage import facts_key, get_artifact_store

logger = logging.getLogger(__name__)

FACET_ORDER = (
    FacetKind.intent_vs_spec,
    FacetKind.cross_file_impact,
    FacetKind.test_coverage_gaps,
    FacetKind.risk_hazards,
)


def _facts_to_dict(facts: PRFacts) -> dict:
    """Convert immutable facts to stable JSON for artifact storage."""
    return {
        "title": facts.title,
        "description": facts.description,
        "files": [
            {
                "path": item.path,
                "old_path": item.old_path,
                "is_new_file": item.is_new_file,
                "is_deleted_file": item.is_deleted_file,
                "is_rename": item.is_rename,
                "added_line_numbers": sorted(item.added_line_numbers),
                "removed_line_numbers": sorted(item.removed_line_numbers),
                "added_ranges": [asdict(span) for span in item.added_ranges],
                "removed_ranges": [asdict(span) for span in item.removed_ranges],
            }
            for item in facts.files
        ],
        "dependency_edges": [
            {
                "from_file": edge.from_file,
                "imported_module": edge.imported_module,
                "import_kind": edge.import_kind.value,
                "lineno": edge.lineno,
            }
            for edge in facts.dependency_edges
        ],
        "coverage": [
            {
                "file_path": item.file_path,
                "status": item.status.value,
                "covered_lines": sorted(item.covered_lines),
                "uncovered_lines": sorted(item.uncovered_lines),
                "source": item.source,
            }
            for item in facts.coverage
        ],
    }


def _citation_to_dict(
    citation: EvidenceCitation,
    check: CitationCheck,
    changed_line_text: dict[tuple[str, int], str],
) -> dict:
    result = {
        "kind": citation.kind.value,
        "file_path": citation.file_path,
        "line_number": citation.line_number,
        "imported_module": citation.imported_module,
        "supported": check.supported,
        "reason": check.reason,
    }
    if citation.line_number is not None:
        excerpt = changed_line_text.get((citation.file_path, citation.line_number))
        if excerpt is not None:
            result["excerpt"] = excerpt[:500]
    return result


async def _mark_failed(analysis_id: uuid.UUID, message: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Analysis)
            .where(Analysis.id == analysis_id)
            .options(selectinload(Analysis.facets))
        )
        analysis = result.scalar_one_or_none()
        if analysis is None:
            return
        analysis.status = AnalysisStatus.failed
        analysis.error = message
        for facet in analysis.facets:
            if facet.status in (FacetStatus.pending, FacetStatus.running):
                facet.status = FacetStatus.failed
        await db.commit()


async def _review_one_facet(
    provider: ReviewProvider,
    facet: FacetKind,
    facts: PRFacts,
    diff_raw: str,
    concurrency_limit: asyncio.Semaphore | None = None,
) -> tuple[FacetKind, tuple[FindingCandidate, ...], Exception | None]:
    try:
        if facet is FacetKind.cross_file_impact and not facts.dependency_edges:
            # Without deterministic dependency edges this facet has no valid
            # evidence source, and asking the model only invites speculation.
            return facet, (), None
        if facet is FacetKind.test_coverage_gaps and not any(
            item.uncovered_lines for item in facts.coverage
        ):
            # Unknown coverage is surfaced by the deterministic coverage panel;
            # calling the model here used to create a repetitive pseudo-finding.
            return facet, (), None
        if concurrency_limit is None:
            findings = await provider.review_facet(facet, facts, diff_raw)
        else:
            async with concurrency_limit:
                findings = await provider.review_facet(facet, facts, diff_raw)
        return facet, findings, None
    except Exception as exc:
        logger.exception("review facet failed: %s", facet.value)
        return facet, (), exc


async def _persist_facet_result(
    analysis_id: uuid.UUID,
    facet_kind: FacetKind,
    findings: tuple[FindingCandidate, ...],
    facts: PRFacts,
    error: Exception | None,
    changed_line_text: dict[tuple[str, int], str],
) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Facet).where(
                Facet.analysis_id == analysis_id,
                Facet.kind == facet_kind,
            )
        )
        facet = result.scalar_one_or_none()
        if facet is None:
            raise RuntimeError(f"Missing facet row: {facet_kind.value}")

        if error is not None:
            facet.status = FacetStatus.failed
            await db.commit()
            return

        gated = gate_findings(findings, facts)
        for item in gated.findings:
            candidate = item.finding
            citations = [
                _citation_to_dict(check.citation, check, changed_line_text)
                for check in item.citation_checks
            ]
            first = candidate.citations[0] if candidate.citations else None
            raw_output = json.dumps(
                {
                    "claim": candidate.claim.value,
                    "summary": candidate.summary,
                    "severity": candidate.severity,
                    "citations": [
                        {
                            "kind": citation.kind.value,
                            "file_path": citation.file_path,
                            "line_number": citation.line_number,
                            "imported_module": citation.imported_module,
                        }
                        for citation in candidate.citations
                    ],
                },
                ensure_ascii=False,
            )
            db.add(
                Finding(
                    facet_id=facet.id,
                    verdict=(
                        FindingVerdict.verified
                        if item.verdict is EvidenceVerdict.verified
                        else FindingVerdict.unverified
                    ),
                    severity=candidate.severity,
                    summary=candidate.summary,
                    claim_type=candidate.claim.value,
                    citations=citations,
                    gate_reasons=list(item.reasons),
                    citation_file=first.file_path if first else None,
                    citation_line=first.line_number if first else None,
                    raw_llm_output=raw_output,
                )
            )
        facet.status = FacetStatus.completed
        await db.commit()


async def execute_analysis(
    analysis_id: uuid.UUID,
    provider: ReviewProvider | None = None,
) -> None:
    """Compute facts, run the four review facets, gate, and persist findings.

    This function is suitable for FastAPI ``BackgroundTasks`` and uses fresh
    sessions so the response request does not retain its DB connection.
    """
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Analysis).where(Analysis.id == analysis_id)
            )
            analysis = result.scalar_one_or_none()
            if analysis is None or analysis.status in (
                AnalysisStatus.completed,
                AnalysisStatus.failed,
            ):
                return
            if analysis.status == AnalysisStatus.running:
                return
            pr_result = await db.execute(select(PR).where(PR.id == analysis.pr_id))
            pr = pr_result.scalar_one_or_none()
            if pr is None:
                raise RuntimeError("Analysis pull request record is missing.")

            analysis.status = AnalysisStatus.running
            facet_result = await db.execute(
                select(Facet).where(Facet.analysis_id == analysis_id)
            )
            facets = list(facet_result.scalars().all())
            existing = {facet.kind for facet in facets}
            for kind in FACET_ORDER:
                if kind not in existing:
                    facet = Facet(
                        analysis_id=analysis_id,
                        kind=kind,
                        status=FacetStatus.pending,
                    )
                    db.add(facet)
                    facets.append(facet)
            for facet in facets:
                facet.status = FacetStatus.running
            storage_key = pr.diff_storage_key
            inline_diff = pr.diff
            title = pr.title or ""
            description = pr.description or ""
            github_pr_url = pr.github_pr_url
            repo_full_name = pr.repo_full_name
            pr_number = pr.pr_number
            head_sha = pr.head_sha
            base_sha = pr.base_sha
            github_installation_id = pr.github_installation_id
            await db.commit()

        store = get_artifact_store()
        if storage_key:
            diff_bytes = await asyncio.to_thread(store.get, storage_key)
        elif inline_diff:
            diff_bytes = inline_diff.encode("utf-8")
        else:
            raise RuntimeError("No diff artifact is available for this analysis.")
        diff_raw = diff_bytes.decode("utf-8")

        from app.ingestion import FileIngestion

        bundle = FileIngestion().ingest(
            diff=diff_raw,
            title=title,
            description=description,
        )
        bundle.github_pr_url = github_pr_url
        bundle.repo_full_name = repo_full_name
        bundle.pr_number = pr_number
        bundle.head_sha = head_sha
        bundle.base_sha = base_sha
        if not bundle.patches:
            raise RuntimeError("The supplied diff contains no parseable file changes.")
        bundle.github_installation_id = github_installation_id
        source_map: dict[str, str] = {}
        if repo_full_name and head_sha and github_installation_id is not None:
            try:
                from app.ingestion import GitHubIngestion

                source_map = await GitHubIngestion().fetch_changed_python_sources(
                    repo_full_name,
                    head_sha,
                    github_installation_id,
                    [patch.path for patch in bundle.patches],
                )
            except Exception:
                logger.exception("changed source enrichment failed for analysis %s", analysis_id)
        coverage_record = None
        if repo_full_name and head_sha:
            async with AsyncSessionLocal() as db:
                coverage_result = await db.execute(
                    select(CoverageArtifactRecord)
                    .where(
                        CoverageArtifactRecord.repo_full_name == repo_full_name.lower(),
                        CoverageArtifactRecord.commit_sha == head_sha.lower(),
                    )
                    .order_by(desc(CoverageArtifactRecord.created_at))
                    .limit(1)
                )
                coverage_record = coverage_result.scalar_one_or_none()

        accepted_coverage: AcceptedCoverage | None = None
        rejected_coverage: RejectedCoverage | None = None
        coverage_artifact: CoverageArtifact | None = None
        if coverage_record is not None:
            try:
                raw_coverage = await asyncio.to_thread(store.get, coverage_record.storage_key)
                if hashlib.sha256(raw_coverage).hexdigest() != coverage_record.artifact_sha256:
                    rejected_coverage = RejectedCoverage(
                        "Stored coverage artifact failed its SHA-256 integrity check."
                    )
                else:
                    coverage_artifact = CoverageArtifact(
                        raw=raw_coverage,
                        format=coverage_record.format,
                        metadata=CIRunMetadata(
                            commit_sha=coverage_record.commit_sha,
                            ci_provider="github_actions",
                            run_id=coverage_record.run_id,
                            artifact_name=coverage_record.artifact_name,
                            run_attempt=coverage_record.run_attempt,
                        ),
                    )
                    intake_result = accept_coverage(coverage_artifact, head_sha)
                    if isinstance(intake_result, AcceptedCoverage):
                        accepted_coverage = intake_result
                    else:
                        rejected_coverage = intake_result
            except Exception:
                logger.exception("coverage artifact could not be loaded for analysis %s", analysis_id)
                rejected_coverage = RejectedCoverage(
                    "Stored coverage artifact could not be read from artifact storage."
                )

        facts = compute_facts(
            bundle,
            file_source_map=source_map,
            coverage_artifact=coverage_artifact if accepted_coverage is None and rejected_coverage is None else None,
            accepted_coverage=accepted_coverage,
            rejected_coverage=rejected_coverage,
        )
        changed_line_text = {
            (patch.path, line_number): line_text
            for patch in bundle.patches
            for line_number, line_text in patch.added_lines
        }
        facts_bytes = json.dumps(
            _facts_to_dict(facts), ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        stored_facts = await asyncio.to_thread(
            store.put,
            facts_key(analysis_id),
            facts_bytes,
            "application/json",
        )
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Analysis).where(Analysis.id == analysis_id)
            )
            analysis = result.scalar_one_or_none()
            if analysis is None:
                return
            analysis.facts_storage_key = stored_facts.key
            if coverage_record is None:
                analysis.coverage_status = "none"
                analysis.coverage_rejection_reason = None
                analysis.coverage_format = None
                analysis.coverage_ci_provider = None
                analysis.coverage_run_id = None
                analysis.coverage_run_attempt = None
                analysis.coverage_artifact_name = None
                analysis.coverage_commit_sha = None
                analysis.coverage_artifact_sha256 = None
                analysis.coverage_parsed_at = None
                analysis.coverage_file_count = None
                analysis.coverage_parser_warnings = []
            elif accepted_coverage is not None:
                provenance = accepted_coverage.provenance
                analysis.coverage_status = "accepted"
                analysis.coverage_rejection_reason = None
                analysis.coverage_format = provenance.format
                analysis.coverage_ci_provider = provenance.ci_provider
                analysis.coverage_run_id = provenance.run_id
                analysis.coverage_run_attempt = provenance.run_attempt
                analysis.coverage_artifact_name = provenance.artifact_name
                analysis.coverage_commit_sha = provenance.commit_sha
                analysis.coverage_artifact_sha256 = provenance.artifact_sha256
                analysis.coverage_parsed_at = provenance.parsed_at
                analysis.coverage_file_count = provenance.file_count
                analysis.coverage_parser_warnings = provenance.parser_warnings
            else:
                analysis.coverage_status = "rejected"
                analysis.coverage_rejection_reason = (
                    rejected_coverage.reason if rejected_coverage else "Coverage artifact was unavailable."
                )
                analysis.coverage_format = coverage_record.format
                analysis.coverage_ci_provider = "github_actions"
                analysis.coverage_run_id = coverage_record.run_id
                analysis.coverage_run_attempt = coverage_record.run_attempt
                analysis.coverage_artifact_name = coverage_record.artifact_name
                analysis.coverage_commit_sha = coverage_record.commit_sha
                analysis.coverage_artifact_sha256 = coverage_record.artifact_sha256
                analysis.coverage_parsed_at = None
                analysis.coverage_file_count = None
                analysis.coverage_parser_warnings = []
            await db.commit()

        active_provider = provider or get_review_provider()
        # Keep the deep-review requests below provider burst limits while still
        # allowing independent facets to make progress concurrently.
        concurrency_limit = asyncio.Semaphore(2)
        tasks = [
            asyncio.create_task(
                _review_one_facet(
                    active_provider, facet, facts, diff_raw, concurrency_limit
                )
            )
            for facet in FACET_ORDER
        ]
        failed_facets: list[str] = []
        for completed_task in asyncio.as_completed(tasks):
            facet_kind, candidates, error = await completed_task
            await _persist_facet_result(
                analysis_id, facet_kind, candidates, facts, error,
                changed_line_text,
            )
            if error is not None:
                failed_facets.append(facet_kind.value)

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Analysis).where(Analysis.id == analysis_id)
            )
            analysis = result.scalar_one_or_none()
            if analysis is None:
                return
            if failed_facets:
                analysis.status = AnalysisStatus.failed
                analysis.error = "Review failed for one or more facets."
            else:
                analysis.status = AnalysisStatus.completed
                analysis.error = None
            await db.commit()
    except Exception:
        logger.exception("analysis orchestration failed: %s", analysis_id)
        await _mark_failed(
            analysis_id,
            "Analysis failed. Check backend logs for details.",
        )
