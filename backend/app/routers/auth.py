"""GitHub sign-in and per-user GitHub App installation management."""
from __future__ import annotations

import logging
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.github_auth import (
    OAUTH_STATE_COOKIE,
    OAUTH_VERIFIER_COOKIE,
    SESSION_COOKIE,
    create_session_token,
    encrypt_github_tokens,
    get_current_user,
    get_github_user,
    get_github_user_token,
    github_headers,
    oauth_authorize_url,
    require_csrf_origin,
    verify_installation_for_user,
)
from app.ingestion.github_ingestion import GitHubIngestion, GitHubIngestionError
from app.models import GitHubInstallation, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])
_OAUTH_COOKIE_MAX_AGE = 600


def _cookie_options() -> dict[str, Any]:
    return {
        "httponly": True,
        "secure": settings.auth_cookie_secure,
        "samesite": settings.auth_cookie_samesite,
        "path": "/",
    }


def _clear_oauth_cookies(response: Response) -> None:
    response.delete_cookie(OAUTH_STATE_COOKIE, path="/auth/github")
    response.delete_cookie(OAUTH_VERIFIER_COOKIE, path="/auth/github")


@router.get("/github/login")
async def github_login() -> RedirectResponse:
    """Start GitHub App user OAuth with state and PKCE protection."""
    from app.github_auth import _require_auth_config

    _require_auth_config(oauth=True)
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    response = RedirectResponse(oauth_authorize_url(state, verifier), status_code=302)
    cookie_options = _cookie_options()
    oauth_cookie_options = {**cookie_options, "path": "/auth/github"}
    response.set_cookie(OAUTH_STATE_COOKIE, state, max_age=_OAUTH_COOKIE_MAX_AGE, **oauth_cookie_options)
    response.set_cookie(OAUTH_VERIFIER_COOKIE, verifier, max_age=_OAUTH_COOKIE_MAX_AGE, **oauth_cookie_options)
    return response


@router.get("/github/callback")
async def github_oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Exchange the OAuth code, upsert the PRism user, and establish a session."""
    from app.github_auth import _require_auth_config

    _require_auth_config(oauth=True)
    expected_state = request.cookies.get(OAUTH_STATE_COOKIE)
    verifier = request.cookies.get(OAUTH_VERIFIER_COOKIE)
    if error or not code or not state or not expected_state or not verifier or not secrets.compare_digest(state, expected_state):
        raise HTTPException(400, "GitHub sign-in was cancelled or its state check failed.")
    try:
        async with httpx.AsyncClient(timeout=settings.github_request_timeout_seconds) as client:
            token_response = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.github_app_client_id,
                    "client_secret": settings.github_app_client_secret,
                    "code": code,
                    "redirect_uri": settings.github_oauth_callback_url,
                    "code_verifier": verifier,
                },
            )
            token_payload = token_response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("GitHub OAuth token exchange failed: %s", type(exc).__name__)
        raise HTTPException(502, "Could not complete GitHub sign-in.") from exc
    if token_response.status_code >= 400 or not isinstance(token_payload, dict) or not isinstance(token_payload.get("access_token"), str):
        raise HTTPException(401, "GitHub did not authorize PRism. Try signing in again.")
    profile = await get_github_user(token_payload["access_token"])
    result = await db.execute(select(User).where(User.github_user_id == profile["id"]))
    user = result.scalar_one_or_none()
    token_payload = {
        key: value
        for key, value in token_payload.items()
        if key in {"access_token", "refresh_token"} and isinstance(value, str)
    }
    if user is None:
        user = User(
            github_user_id=profile["id"],
            github_login=profile["login"],
            github_name=profile.get("name"),
        )
        db.add(user)
    user.github_login = profile["login"]
    user.github_name = profile.get("name")
    user.github_token_ciphertext = encrypt_github_tokens(token_payload)
    user.github_token_expires_at = _expiry_from_response(token_response.json(), "expires_in")
    user.github_refresh_token_expires_at = _expiry_from_response(token_response.json(), "refresh_token_expires_in")
    await db.commit()
    await db.refresh(user)
    response = RedirectResponse(settings.auth_frontend_url, status_code=302)
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user.id),
        max_age=settings.auth_session_lifetime_seconds,
        **_cookie_options(),
    )
    _clear_oauth_cookies(response)
    return response


def _expiry_from_response(payload: dict[str, Any], key: str):
    seconds = payload.get(key)
    if not isinstance(seconds, (int, float)) or seconds <= 0:
        return None
    from datetime import datetime, timedelta, timezone

    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


@router.get("/me")
async def auth_me(user: User = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "github_login": user.github_login,
        "github_name": user.github_name,
        "installations": [
            {"id": item.id, "account_login": item.account_login, "account_type": item.account_type}
            for item in user.installations
        ],
    }


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf_origin)])
async def logout() -> Response:
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/github/install")
async def start_install(
    user: User = Depends(get_current_user),
) -> RedirectResponse:
    if not settings.github_app_slug:
        raise HTTPException(503, "GITHUB_APP_SLUG is not configured.")
    if not settings.auth_session_secret or len(settings.auth_session_secret) < 32:
        raise HTTPException(503, "Authentication is not configured.")
    now = int(time.time())
    install_state = jwt.encode(
        {"sub": str(user.id), "iss": "prism", "aud": "github-install", "iat": now, "exp": now + 600},
        settings.auth_session_secret,
        algorithm="HS256",
    )
    target = f"https://github.com/apps/{settings.github_app_slug}/installations/new?{urlencode({'state': install_state})}"
    return RedirectResponse(target, status_code=302)


@router.get("/github/install/callback")
async def finish_install(
    installation_id: int = Query(gt=0),
    setup_action: str = Query(),
    state: str = Query(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    if setup_action not in {"install", "update"}:
        raise HTTPException(400, "GitHub App installation was not completed.")
    try:
        state_payload = jwt.decode(
            state,
            settings.auth_session_secret,
            algorithms=["HS256"],
            issuer="prism",
            audience="github-install",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(400, "GitHub installation state is invalid or expired.") from exc
    if state_payload.get("sub") != str(user.id):
        raise HTTPException(403, "This GitHub installation flow belongs to another PRism account.")

    access_token = await get_github_user_token(db, user)
    await verify_installation_for_user(access_token, installation_id)
    try:
        app_jwt = GitHubIngestion._app_jwt()
    except GitHubIngestionError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    api = settings.github_api_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=settings.github_request_timeout_seconds) as client:
            result = await client.get(
                f"{api}/app/installations/{installation_id}",
                headers=github_headers(app_jwt),
            )
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Could not verify the GitHub App installation.") from exc
    if result.status_code != 200:
        raise HTTPException(403, "That installation does not belong to this GitHub App.")
    payload = result.json()
    account = payload.get("account") if isinstance(payload, dict) else None
    if not isinstance(account, dict) or not isinstance(account.get("id"), int) or not isinstance(account.get("login"), str):
        raise HTTPException(502, "GitHub returned incomplete installation account details.")
    installation = await db.get(GitHubInstallation, installation_id)
    if installation is None:
        installation = GitHubInstallation(
            id=installation_id,
            account_id=account["id"],
            account_login=account["login"],
            account_type=account.get("type") or "User",
        )
        db.add(installation)
    else:
        installation.account_id = account["id"]
        installation.account_login = account["login"]
        installation.account_type = account.get("type") or "User"
    if installation not in user.installations:
        user.installations.append(installation)
    await db.commit()
    return RedirectResponse(f"{settings.auth_frontend_url.rstrip('/')}?github_app=connected", status_code=303)


@router.delete("/github/installations/{installation_id}", status_code=204)
async def disconnect_installation(
    installation_id: int,
    _: None = Depends(require_csrf_origin),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    result = await db.execute(
        select(GitHubInstallation)
        .join(GitHubInstallation.users)
        .where(GitHubInstallation.id == installation_id, User.id == user.id)
    )
    installation = result.scalar_one_or_none()
    if installation is None:
        raise HTTPException(404, "Connected GitHub installation not found.")
    user.installations.remove(installation)
    await db.commit()
    return Response(status_code=204)
