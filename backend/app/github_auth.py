"""GitHub App OAuth, encrypted user tokens, and PRism session helpers."""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx
import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models import User

logger = logging.getLogger(__name__)
SESSION_COOKIE = "prism_session"
OAUTH_STATE_COOKIE = "github_oauth_state"
OAUTH_VERIFIER_COOKIE = "github_oauth_verifier"


def _require_auth_config(*, oauth: bool = False) -> None:
    if not settings.auth_session_secret or len(settings.auth_session_secret) < 32:
        raise HTTPException(503, "Authentication is not configured: AUTH_SESSION_SECRET must be at least 32 characters.")
    if oauth and not all((settings.github_app_client_id, settings.github_app_client_secret, settings.github_oauth_callback_url)):
        raise HTTPException(503, "GitHub sign-in is not configured. Set the GitHub App OAuth client ID, secret, and callback URL.")


def _encryption_key() -> bytes:
    raw = settings.github_token_encryption_key
    try:
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except Exception as exc:
        raise HTTPException(503, "GitHub token encryption is not configured correctly.") from exc
    if len(key) != 32:
        raise HTTPException(503, "GITHUB_TOKEN_ENCRYPTION_KEY must be a base64-encoded 32-byte key.")
    return key


def encrypt_github_tokens(tokens: dict[str, str]) -> bytes:
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(_encryption_key()).encrypt(nonce, json.dumps(tokens).encode(), b"prism-github-user-tokens-v1")
    return nonce + ciphertext


def decrypt_github_tokens(ciphertext: bytes | None) -> dict[str, str]:
    if not ciphertext:
        raise HTTPException(401, "Reconnect your GitHub account to continue.")
    try:
        payload = AESGCM(_encryption_key()).decrypt(
            ciphertext[:12], ciphertext[12:], b"prism-github-user-tokens-v1"
        )
        result = json.loads(payload)
        if not isinstance(result, dict) or not isinstance(result.get("access_token"), str):
            raise ValueError("invalid token payload")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Stored GitHub user token could not be decrypted")
        raise HTTPException(401, "Reconnect your GitHub account to continue.") from exc


def create_session_token(user_id: UUID) -> str:
    _require_auth_config()
    now = int(time.time())
    return jwt.encode(
        {"sub": str(user_id), "iss": "prism", "iat": now, "exp": now + settings.auth_session_lifetime_seconds},
        settings.auth_session_secret,
        algorithm="HS256",
    )


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    _require_auth_config()
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(401, "Sign in with GitHub to continue.")
    try:
        payload = jwt.decode(token, settings.auth_session_secret, algorithms=["HS256"], issuer="prism")
        user_id = UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(401, "Your session is invalid or expired. Sign in again.") from exc
    result = await db.execute(
        select(User).where(User.id == user_id).options(selectinload(User.installations))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(401, "Your session is no longer valid. Sign in again.")
    return user


async def require_csrf_origin(request: Request) -> None:
    """Reject cookie-authenticated writes from untrusted browser origins."""
    origin = request.headers.get("origin")
    if not origin or origin not in settings.cors_allowed_origins:
        raise HTTPException(403, "This request origin is not allowed.")


def github_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": settings.github_api_version,
        "User-Agent": "PRism-PR-review",
    }


def _token_expiry(seconds: Any) -> datetime | None:
    if not isinstance(seconds, (int, float)) or seconds <= 0:
        return None
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


async def get_github_user_token(db: AsyncSession, user: User) -> str:
    """Return a current GitHub user token, refreshing it when near expiry."""
    tokens = decrypt_github_tokens(user.github_token_ciphertext)
    expires_at = user.github_token_expires_at
    if expires_at and expires_at > datetime.now(timezone.utc) + timedelta(minutes=5):
        return tokens["access_token"]
    refresh_token = tokens.get("refresh_token")
    if not refresh_token or not settings.github_app_client_id or not settings.github_app_client_secret:
        raise HTTPException(401, "Your GitHub session expired. Sign in again.")
    try:
        async with httpx.AsyncClient(timeout=settings.github_request_timeout_seconds) as client:
            response = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.github_app_client_id,
                    "client_secret": settings.github_app_client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
            )
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("GitHub user token refresh failed: %s", type(exc).__name__)
        raise HTTPException(502, "Could not refresh the GitHub session. Try signing in again.") from exc
    if response.status_code >= 400 or not isinstance(payload, dict) or not isinstance(payload.get("access_token"), str):
        raise HTTPException(401, "Your GitHub session expired. Sign in again.")
    tokens = {key: value for key, value in payload.items() if key in {"access_token", "refresh_token"} and isinstance(value, str)}
    user.github_token_ciphertext = encrypt_github_tokens(tokens)
    user.github_token_expires_at = _token_expiry(payload.get("expires_in"))
    user.github_refresh_token_expires_at = _token_expiry(payload.get("refresh_token_expires_in"))
    await db.commit()
    return tokens["access_token"]


async def github_get_user(access_token: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=settings.github_request_timeout_seconds) as client:
            response = await client.get(f"{settings.github_api_url.rstrip('/')}/user", headers=github_headers(access_token))
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Could not reach GitHub to verify your account.") from exc
    if response.status_code != 200:
        raise HTTPException(401, "GitHub could not verify this account. Sign in again.")
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("id"), int) or not isinstance(payload.get("login"), str):
        raise HTTPException(502, "GitHub returned an invalid account response.")
    return payload


async def assert_user_can_access_repo(access_token: str, repo_full_name: str) -> None:
    api = settings.github_api_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=settings.github_request_timeout_seconds) as client:
            response = await client.get(f"{api}/repos/{repo_full_name}", headers=github_headers(access_token))
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Could not verify your GitHub repository access.") from exc
    if response.status_code == 404:
        raise HTTPException(403, "Your GitHub account cannot access this repository.")
    if response.status_code in (401, 403):
        raise HTTPException(403, "Your GitHub account cannot access this repository.")
    if response.status_code >= 500:
        raise HTTPException(502, "GitHub is temporarily unavailable. Try again shortly.")
    if response.status_code != 200:
        raise HTTPException(502, "GitHub could not verify your repository access.")


async def verify_installation_for_user(access_token: str, installation_id: int) -> dict[str, Any]:
    """Verify the authenticated GitHub user can see the given App installation."""
    api = settings.github_api_url.rstrip("/")
    url = f"{api}/user/installations/{installation_id}/repositories?per_page=1"
    try:
        async with httpx.AsyncClient(timeout=settings.github_request_timeout_seconds) as client:
            response = await client.get(url, headers=github_headers(access_token))
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Could not verify the GitHub App installation.") from exc
    if response.status_code != 200:
        raise HTTPException(403, "That GitHub App installation is not accessible to your account.")
    try:
        repositories = response.json()
    except ValueError as exc:
        raise HTTPException(502, "GitHub returned an invalid installation response.") from exc
    if not isinstance(repositories, dict) or not isinstance(repositories.get("repositories"), list):
        raise HTTPException(502, "GitHub returned an invalid installation response.")
    return repositories


def oauth_authorize_url(state: str, verifier: str) -> str:
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    query = urlencode({
        "client_id": settings.github_app_client_id,
        "redirect_uri": settings.github_oauth_callback_url,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    return f"https://github.com/login/oauth/authorize?{query}"


# Backward-compatible alias so auth.py can import either name.
get_github_user = github_get_user
