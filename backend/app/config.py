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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
