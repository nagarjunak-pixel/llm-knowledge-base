"""Runtime configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Paths (relative to repo root by default)
    root_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    raw_dir_name: str = "raw"
    wiki_dir_name: str = "wiki"
    outputs_dir_name: str = "outputs"
    db_path_name: str = "app.db"

    # LLM
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-4-6"
    anthropic_max_tokens: int = 4096

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"

    @property
    def raw_dir(self) -> Path:
        return self.root_dir / self.raw_dir_name

    @property
    def wiki_dir(self) -> Path:
        return self.root_dir / self.wiki_dir_name

    @property
    def outputs_dir(self) -> Path:
        return self.root_dir / self.outputs_dir_name

    @property
    def db_path(self) -> Path:
        return self.root_dir / self.db_path_name

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    def ensure_dirs(self) -> None:
        for p in (self.raw_dir, self.wiki_dir, self.outputs_dir,
                  self.wiki_dir / "concepts", self.wiki_dir / "summaries",
                  self.wiki_dir / "_meta",
                  self.raw_dir / "articles", self.raw_dir / "papers",
                  self.raw_dir / "images", self.raw_dir / "data"):
            p.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
