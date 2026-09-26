"""Tests for GET /analyses (history list) and PR metadata on GET /analyses/{id}.

Uses dependency overrides and stub sessions so no real database is needed.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi import HTTPException

from app.database import get_db
from app.github_auth import get_current_user
from app.main import app
from app.models import AnalysisStatus, FacetKind, FacetStatus
from app.schemas import AnalysisOut


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _pr_stub(**overrides: Any) -> SimpleNamespace:
    fields: dict[str, Any] = {
        "id": _uuid(),
        "title": "Add refund endpoint",
        "description": "Adds POST /refunds",
        "repo_full_name": "octocat/payments",
        "pr_number": 42,
        "github_pr_url": "https://github.com/octocat/payments/pull/42",
        "head_sha": "a" * 40,
        "base_sha": "b" * 40,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _analysis_stub(pr: SimpleNamespace, **overrides: Any) -> SimpleNamespace:
    fields: dict[str, Any] = {
        "id": _uuid(),
        "status": AnalysisStatus.completed,
        "error": None,
        "created_at": datetime(2026, 9, 26, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 9, 26, tzinfo=timezone.utc) + timedelta(minutes=2),
        "coverage_status": None,
        "coverage_rejection_reason": None,
        "coverage_format": None,
        "coverage_ci_provider": None,
        "coverage_run_id": None,
        "coverage_run_attempt": None,
        "coverage_artifact_name": None,
        "coverage_commit_sha": None,
        "coverage_artifact_sha256": None,
        "coverage_parsed_at": None,
        "coverage_file_count": None,
        "coverage_parser_warnings": None,
        "pr": pr,
        "facets": [],
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


class _ScalarsResult:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def scalars(self) -> "_ScalarsResult":
        return self

    def all(self) -> list[Any]:
        return self._items


class _SingleResult:
    def __init__(self, item: Any) -> None:
        self._item = item

    def scalar_one_or_none(self) -> Any:
        return self._item


class _FakeDb:
    """Async session stub returning queued results per execute() call."""

    def __init__(self, results: list[Any]) -> None:
        self._results = list(results)
        self.executed: list[Any] = []

    async def execute(self, statement: Any) -> Any:
        self.executed.append(statement)
        return self._results.pop(0)


@pytest.fixture()
def authed_user() -> SimpleNamespace:
    return SimpleNamespace(id=_uuid(), github_login="octocat", installations=[])


def _install_overrides(db: _FakeDb, user: Any) -> None:
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_list_analyses_returns_history_with_pr_metadata(authed_user: SimpleNamespace) -> None:
    pr = _pr_stub()
    older = _analysis_stub(
        pr,
        created_at=datetime(2026, 9, 25, tzinfo=timezone.utc),
        status=AnalysisStatus.failed,
        error="Review failed for one or more facets.",
    )
    newer = _analysis_stub(pr, status=AnalysisStatus.pending)
    db = _FakeDb([_ScalarsResult([newer, older])])  # router order is authoritative
    _install_overrides(db, authed_user)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/analyses")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list) and len(payload) == 2
    assert payload[0]["status"] == "pending"
    assert payload[1]["status"] == "failed"
    assert payload[1]["error"] == "Review failed for one or more facets."
    for item in payload:
        assert item["pr"]["repo_full_name"] == "octocat/payments"
        assert item["pr"]["pr_number"] == 42
        assert item["pr"]["github_pr_url"].endswith("/pull/42")
        assert "id" in item and "created_at" in item


@pytest.mark.anyio
async def test_list_analyses_rejects_unauthenticated() -> None:
    async def _denied() -> None:
        raise HTTPException(status_code=401, detail="Sign in with GitHub to continue.")

    app.dependency_overrides[get_current_user] = _denied
    app.dependency_overrides[get_db] = lambda: _FakeDb([])

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/analyses")

    assert response.status_code == 401


@pytest.mark.anyio
async def test_list_analyses_validates_limit(authed_user: SimpleNamespace) -> None:
    db = _FakeDb([])
    _install_overrides(db, authed_user)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/analyses", params={"limit": 0})

    assert response.status_code == 422


@pytest.mark.anyio
async def test_get_analysis_includes_pr_metadata(authed_user: SimpleNamespace) -> None:
    analysis_id = _uuid()
    facet = SimpleNamespace(
        id=_uuid(),
        kind=FacetKind.test_coverage_gaps,
        status=FacetStatus.completed,
        created_at=datetime(2026, 9, 26, tzinfo=timezone.utc),
        updated_at=datetime(2026, 9, 26, tzinfo=timezone.utc),
        findings=[],
    )
    pr = _pr_stub()
    analysis = _analysis_stub(pr, id=analysis_id, facets=[facet])
    db = _FakeDb([_SingleResult(analysis)])
    _install_overrides(db, authed_user)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/analyses/{analysis_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(analysis_id)
    assert payload["pr"]["title"] == "Add refund endpoint"
    assert payload["pr"]["head_sha"] == "a" * 40
    assert payload["facets"][0]["kind"] == "test_coverage_gaps"


@pytest.mark.anyio
async def test_get_analysis_404_for_other_users_analysis(authed_user: SimpleNamespace) -> None:
    db = _FakeDb([_SingleResult(None)])
    _install_overrides(db, authed_user)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/analyses/{_uuid()}")

    assert response.status_code == 404


def test_analysis_out_validates_pr_relationship() -> None:
    pr = _pr_stub()
    analysis = _analysis_stub(pr)
    validated = AnalysisOut.model_validate(analysis)
    assert validated.pr.repo_full_name == "octocat/payments"
    assert validated.status == AnalysisStatus.completed
