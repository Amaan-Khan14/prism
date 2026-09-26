"""Background review orchestration from stored PR input through evidence gate."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.facts import compute_facts
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
) -> dict:
    return {
        "kind": citation.kind.value,
        "file_path": citation.file_path,
        "line_number": citation.line_number,
        "imported_module": citation.imported_module,
        "supported": check.supported,
        "reason": check.reason,
    }


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
) -> tuple[FacetKind, tuple[FindingCandidate, ...], Exception | None]:
    try:
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
                _citation_to_dict(check.citation, check)
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
        facts = compute_facts(bundle)
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
            await db.commit()

        active_provider = provider or get_review_provider()
        tasks = [
            asyncio.create_task(
                _review_one_facet(active_provider, facet, facts, diff_raw)
            )
            for facet in FACET_ORDER
        ]
        failed_facets: list[str] = []
        for completed_task in asyncio.as_completed(tasks):
            facet_kind, candidates, error = await completed_task
            await _persist_facet_result(
                analysis_id, facet_kind, candidates, facts, error
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
