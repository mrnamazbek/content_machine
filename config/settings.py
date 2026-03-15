"""
Central configuration loaded from environment variables.
Uses pydantic-settings for validation and type coercion.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
import os


class Settings(BaseSettings):
    """All application settings, loaded from .env file."""

    # ── AI APIs ───────────────────────────────────
    openai_api_key: str = Field(default="", description="OpenAI API key")
    anthropic_api_key: str = Field(default="", description="Anthropic API key")
    perplexity_api_key: str = Field(default="", description="Perplexity API key")

    # ── Database ──────────────────────────────────
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "content_machine"
    postgres_user: str = "cm_user"
    postgres_password: str = "cm_secure_password_change_me"

    # ── API Server ────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    # ── Content Settings ──────────────────────────
    niches: str = "gym discipline,engineer life,coding mindset,football motivation"
    min_views: int = 50_000
    max_duration: int = 60
    posts_per_day: int = 5

    # ── TikTok Auth ───────────────────────────────
    tiktok_session_cookie: str = ""
    tiktok_username: str = ""
    tiktok_password: str = ""

    # ── Instagram Auth ────────────────────────────
    instagram_username: str = ""
    instagram_password: str = ""

    # ── Paths ─────────────────────────────────────
    video_raw_dir: str = "videos/raw"
    video_processed_dir: str = "videos/processed"
    auth_dir: str = "auth"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def niche_list(self) -> List[str]:
        """Parse comma-separated niches into a list."""
        return [n.strip() for n in self.niches.split(",") if n.strip()]

    @property
    def database_url(self) -> str:
        """Construct PostgreSQL connection string or use exact DATABASE_URL if provided."""
        if env_db_url := os.getenv("DATABASE_URL"):
            return env_db_url
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

# Singleton settings instance
settings = Settings()
