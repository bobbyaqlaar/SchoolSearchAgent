"""Single source of truth for runtime configuration.

Every module reads from `Settings`. Phase 2 only adds fields here; consumers
never change. Values load from environment / `.env`.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    xai_api_key: str | None = None
    groq_api_key: str | None = None
    deepseek_api_key: str | None = None

    # GitHub Models: free, OpenAI-compatible inference for dev.
    github_token: str | None = None
    github_models_base_url: str = "https://models.github.ai/inference"

    default_model: str = "gpt-4o"

    local_llm_base_url: str = "http://localhost:11434"
    local_backend: Literal["ollama", "vllm"] = "ollama"

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    langchain_tracing_v2: bool = False
    langchain_api_key: str | None = None
    langchain_project: str = "dubai-graph-sync-agent"

    model_pricing_path: str | None = None
    langsmith_pricing_probes_path: str | None = None
    sync_langsmith_pricing: bool = False
    sync_langsmith_pricing_write: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if value is None or value == "":
            return ["http://localhost:3000", "http://127.0.0.1:3000"]
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


def get_settings() -> Settings:
    """Return a freshly loaded settings instance."""
    return Settings()
