from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    database_url: str = Field(default="postgresql+psycopg://user:pass@db:5432/fl_ingest")
    rss_feed_url: str = Field(default="https://www.fl.ru/rss/all.xml")
    rss_category: Optional[int] = None
    rss_subcategory: Optional[int] = None
    upload_dir: Path = Field(default=Path("/app/uploads"))
    max_upload_mb: int = Field(default=250)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("upload_dir", mode="before")
    @classmethod
    def _ensure_path(cls, value: str | Path) -> Path:
        return Path(value)

    @field_validator("rss_category", "rss_subcategory", mode="before")
    @classmethod
    def _empty_str_to_none(cls, value: Optional[str | int]) -> Optional[int]:
        if value in ("", None):
            return None
        return int(value)

    @field_validator("max_upload_mb", mode="after")
    @classmethod
    def _validate_upload_limit(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("MAX_UPLOAD_MB must be greater than zero")
        return value


class RSSIngestOptions(BaseModel):
    feed_url: Optional[str] = None
    category: Optional[int] = None
    subcategory: Optional[int] = None
    limit: Optional[int] = None


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
    try:
        settings.upload_dir.chmod(0o755)
    except PermissionError:
        # Best-effort permission adjustment; ignore if not allowed (e.g., mounted volume).
        pass
    return settings
