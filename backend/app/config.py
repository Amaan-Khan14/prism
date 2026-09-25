"""Application settings loaded from environment / .env file."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://prism:prism@localhost:5432/prism"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
