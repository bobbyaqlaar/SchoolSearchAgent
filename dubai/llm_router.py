"""Multi-provider LLM router (README §3 FR5).

Public surface is frozen: Phase 2 only adds rows to ``MODEL_REGISTRY``; it never
changes these signatures. Token **pricing** is loaded from ``config/model_pricing.yaml``
(see ``dubai.model_pricing``) so rates can change without editing this module.

Provider SDKs are imported lazily inside each factory so a missing optional
dependency or API key never breaks module import or unrelated models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from dubai.model_pricing import warn_missing_registry_pricing
from dubai.settings import get_settings

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel


def _coerce_openai_compat_kwargs(overrides: dict[str, object]) -> dict[str, object]:
    """Route OpenAI-specific kwargs (e.g. parallel_tool_calls) into model_kwargs."""
    merged = dict(overrides)
    model_kwargs = dict(merged.pop("model_kwargs", {}) or {})
    if "parallel_tool_calls" in merged:
        model_kwargs["parallel_tool_calls"] = merged.pop("parallel_tool_calls")
    if model_kwargs:
        merged["model_kwargs"] = model_kwargs
    return merged


@dataclass(frozen=True)
class ModelSpec:
    provider: str
    factory: Callable[..., "BaseChatModel"]
    model_kwargs: dict[str, object] = field(default_factory=dict)


def _openai(model_name: str) -> Callable[..., "BaseChatModel"]:
    def build(**overrides: object) -> "BaseChatModel":
        from langchain_openai import ChatOpenAI

        settings = get_settings()
        return ChatOpenAI(
            model=model_name,
            temperature=0,
            api_key=settings.openai_api_key or "not-set",
            **_coerce_openai_compat_kwargs(dict(overrides)),
        )

    return build


def _deepseek(model_name: str) -> Callable[..., "BaseChatModel"]:
    def build(**overrides: object) -> "BaseChatModel":
        from langchain_openai import ChatOpenAI

        settings = get_settings()
        return ChatOpenAI(
            model=model_name,
            temperature=0,
            base_url="https://api.deepseek.com",
            api_key=settings.deepseek_api_key or "not-set",
            **_coerce_openai_compat_kwargs(dict(overrides)),
        )

    return build


def _anthropic(model_name: str) -> Callable[..., "BaseChatModel"]:
    def build(**overrides: object) -> "BaseChatModel":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as error:
            raise ImportError(
                "Anthropic provider not installed — run: uv sync --extra providers"
            ) from error

        settings = get_settings()
        return ChatAnthropic(
            model=model_name,
            temperature=0,
            api_key=settings.anthropic_api_key or "not-set",
            **overrides,
        )

    return build


def _google(model_name: str) -> Callable[..., "BaseChatModel"]:
    def build(**overrides: object) -> "BaseChatModel":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as error:
            raise ImportError(
                "Google provider not installed — run: uv sync --extra providers"
            ) from error

        settings = get_settings()
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
            google_api_key=settings.google_api_key or "not-set",
            **overrides,
        )

    return build


def _xai(model_name: str) -> Callable[..., "BaseChatModel"]:
    def build(**overrides: object) -> "BaseChatModel":
        try:
            from langchain_xai import ChatXAI
        except ImportError as error:
            raise ImportError(
                "xAI provider not installed — run: uv sync --extra providers"
            ) from error

        settings = get_settings()
        return ChatXAI(
            model=model_name,
            temperature=0,
            api_key=settings.xai_api_key or "not-set",
            **overrides,
        )

    return build


def _groq(model_name: str) -> Callable[..., "BaseChatModel"]:
    def build(**overrides: object) -> "BaseChatModel":
        try:
            from langchain_groq import ChatGroq
        except ImportError as error:
            raise ImportError(
                "Groq provider not installed — run: uv sync --extra providers"
            ) from error

        settings = get_settings()
        return ChatGroq(
            model=model_name,
            temperature=0,
            api_key=settings.groq_api_key or "not-set",
            **overrides,
        )

    return build


def _github(model_name: str) -> Callable[..., "BaseChatModel"]:
    """GitHub Models: free OpenAI-compatible dev inference via GITHUB_TOKEN."""

    def build(**overrides: object) -> "BaseChatModel":
        from langchain_openai import ChatOpenAI

        settings = get_settings()
        return ChatOpenAI(
            model=model_name,
            temperature=0,
            base_url=settings.github_models_base_url,
            api_key=settings.github_token or "not-set",
            **_coerce_openai_compat_kwargs(dict(overrides)),
        )

    return build


def _local(model_name: str) -> Callable[..., "BaseChatModel"]:
    def build(**overrides: object) -> "BaseChatModel":
        settings = get_settings()
        if settings.local_backend == "vllm":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=model_name,
                temperature=0,
                base_url=f"{settings.local_llm_base_url}/v1",
                api_key="not-needed",
                **overrides,
            )
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=model_name,
            temperature=0,
            base_url=settings.local_llm_base_url,
            **overrides,
        )

    return build


MODEL_REGISTRY: dict[str, ModelSpec] = {
    "gpt-4o": ModelSpec("openai", _openai("gpt-4o")),
    "gpt-4o-mini": ModelSpec("openai", _openai("gpt-4o-mini")),
 #   "claude-3-5-sonnet": ModelSpec(
 #       "anthropic", _anthropic("claude-3-5-sonnet-latest")
 #   ),
    "gemini-1.5-pro": ModelSpec("google", _google("gemini-2.0-flash")),
    "gemini-1.5-flash": ModelSpec("google", _google("gemini-2.0-flash")),
    "qwen-2.5-72b-instruct": ModelSpec(
        "groq", _groq("qwen/qwen3-32b")
    ),
 #   "deepseek-v3": ModelSpec("deepseek", _deepseek("deepseek-chat")),
 #   "deepseek-r1": ModelSpec("deepseek", _deepseek("deepseek-reasoner")),
    "grok-2-beta-foundation": ModelSpec("xai", _xai("grok-4.3")),
    "grok-2-beta-fast": ModelSpec("xai", _xai("grok-4.20-0309-non-reasoning")),
 #   "llama-3.1": ModelSpec("local", _local("llama3.1")),
 #   "llama-3.3": ModelSpec("local", _local("llama3.3")),
 #   "gemma-2": ModelSpec("local", _local("gemma2")),
    "github:gpt-4o-mini": ModelSpec("github", _github("openai/gpt-4o-mini")),
    "github:gpt-4o": ModelSpec("github", _github("openai/gpt-4o")),
    "github:llama-3.3-70b": ModelSpec(
        "github",
        _github("meta/llama-3.3-70b-instruct"),
        model_kwargs={"parallel_tool_calls": False},
    ),
    "github:deepseek-v3": ModelSpec(
        "github",
        _github("deepseek/deepseek-v3-0324"),
        model_kwargs={"parallel_tool_calls": False},
    ),
}

warn_missing_registry_pricing(list(MODEL_REGISTRY))


def list_models() -> list[str]:
    """Return all selectable model ids (for the API and frontend selector)."""
    return list(MODEL_REGISTRY)


def get_chat_model(model_id: str, **overrides: object) -> "BaseChatModel":
    """Build a chat model for ``model_id``. Raises ValueError if unknown."""
    spec = MODEL_REGISTRY.get(model_id)
    if spec is None:
        raise ValueError(f"unknown model: {model_id}")
    merged = {**spec.model_kwargs, **overrides}
    return spec.factory(**merged)


def get_ask_chat_model(model_id: str) -> "BaseChatModel":
    """Chat model tuned for Ask agent tool use (single tool call per turn when needed)."""
    spec = MODEL_REGISTRY[model_id]
    ask_kwargs: dict[str, object] = dict(spec.model_kwargs)
    if spec.provider in ("openai", "github", "deepseek"):
        ask_kwargs.setdefault("parallel_tool_calls", False)
    return get_chat_model(model_id, **ask_kwargs)
