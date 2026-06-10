"""Push LLM provider credentials into os.environ for LangChain SDKs."""

from __future__ import annotations

import os

from dubai.settings import Settings

_PROVIDER_ENV: tuple[tuple[str, str], ...] = (
    ("OPENAI_API_KEY", "openai_api_key"),
    ("ANTHROPIC_API_KEY", "anthropic_api_key"),
    ("GOOGLE_API_KEY", "google_api_key"),
    ("XAI_API_KEY", "xai_api_key"),
    ("GROQ_API_KEY", "groq_api_key"),
    ("DEEPSEEK_API_KEY", "deepseek_api_key"),
    ("GITHUB_TOKEN", "github_token"),
)


def configure_llm_provider_env(settings: Settings) -> None:
    """LangChain provider clients read API keys from the process environment."""
    for env_name, field_name in _PROVIDER_ENV:
        value = getattr(settings, field_name)
        if value:
            os.environ[env_name] = value
