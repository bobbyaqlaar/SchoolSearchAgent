"""Tests for LLM provider env bootstrap."""

from __future__ import annotations

import os

from dubai.provider_env import configure_llm_provider_env
from dubai.settings import Settings


def test_configure_llm_provider_env(monkeypatch):
    for key in [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "GROQ_API_KEY",
        "GITHUB_TOKEN",
    ]:
        monkeypatch.delenv(key, raising=False)

    settings = Settings(
        openai_api_key="sk-test",
        google_api_key="google-test",
        groq_api_key="groq-test",
        github_token="gh-test",
    )
    configure_llm_provider_env(settings)

    assert os.environ["OPENAI_API_KEY"] == "sk-test"
    assert os.environ["GOOGLE_API_KEY"] == "google-test"
    assert os.environ["GROQ_API_KEY"] == "groq-test"
    assert os.environ["GITHUB_TOKEN"] == "gh-test"
