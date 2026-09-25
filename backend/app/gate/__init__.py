"""Deterministic verification of review-finding evidence."""

from app.gate.evidence_gate import gate_findings
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

__all__ = [
    "CitationCheck",
    "EvidenceCitation",
    "EvidenceGateResult",
    "EvidenceKind",
    "EvidenceVerdict",
    "FindingCandidate",
    "FindingClaim",
    "GatedFinding",
    "gate_findings",
]
