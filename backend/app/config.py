"""Application settings loaded from environment / .env file."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    database_url: str = "postgresql+asyncpg://prism:prism@localhost:5432/prism"

    # ------------------------------------------------------------------
    # Artifact storage
    # ------------------------------------------------------------------
    storage_backend: str = "local"
    """Which artifact store to use.  Valid values: ``local`` (default), ``s3``."""

    local_artifact_root: str = "/tmp/prism-artifacts"
    """Root directory for the local artifact store.  Ignored when ``storage_backend=s3``."""

    s3_bucket_name: str = ""
    """Name of the S3 bucket.  Required when ``storage_backend=s3``.
    Example: ``prism-artifact-storage-prismartifactbucket-ubri8x7giofh``
    """

    aws_region: str = "ap-south-1"
    """AWS region for the S3 bucket.  Defaults to ap-south-1 (PRism bucket region)."""

    # ------------------------------------------------------------------
    # Review provider
    # ------------------------------------------------------------------
    review_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"
    openai_api_key: str = ""
    openai_model: str = "gpt-6-astra"
    review_request_timeout_seconds: float = 90.0

    # ------------------------------------------------------------------
    # GitHub App (read-only PR ingestion)
    # ------------------------------------------------------------------
    github_app_id: str = ""
    github_private_key_path: str = ""
    github_app_slug: str = "pr-review-prism"
    github_app_client_id: str = ""
    github_app_client_secret: str = ""
    github_oauth_callback_url: str = ""
    github_app_setup_url: str = ""
    github_api_url: str = "https://api.github.com"
    github_api_version: str = "2026-03-10"
    github_request_timeout_seconds: float = 20.0

    # GitHub Actions OIDC coverage uploads. Keep this allowlist empty until
    # trusted workflow references have been configured explicitly.
    github_actions_oidc_audience: str = "prism"
    github_coverage_trusted_workflow_refs: list[str] = []

    # User sessions and encrypted GitHub App user tokens.
    auth_session_secret: str = ""
    github_token_encryption_key: str = ""
    auth_cookie_secure: bool = True
    auth_cookie_samesite: str = "lax"
    auth_session_lifetime_seconds: int = 604800
    auth_frontend_url: str = "http://localhost:3000"
    cors_allowed_origins: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
