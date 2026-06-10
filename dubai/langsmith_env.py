"""Push LangSmith settings into os.environ for LangChain auto-tracing."""

from __future__ import annotations

import os

from dubai.settings import Settings


def configure_langsmith_tracing(settings: Settings) -> None:
    """LangChain reads LANGCHAIN_* from the process environment, not pydantic Settings."""
    api_key = settings.langchain_api_key
    if api_key:
        os.environ["LANGCHAIN_API_KEY"] = api_key
    if settings.langchain_tracing_v2:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
    if settings.langchain_project:
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
