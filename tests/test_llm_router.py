import importlib.util

import pytest


def test_known_models_listed():
    from dubai.llm_router import MODEL_REGISTRY, list_models

    assert "gpt-4o" in list_models()
    assert len(MODEL_REGISTRY) >= 13


def test_github_models_present():
    from dubai.llm_router import list_models
    from dubai.model_pricing import get_model_pricing

    gh = [m for m in list_models() if m.startswith("github:")]
    assert "github:gpt-4o-mini" in gh
    assert all(get_model_pricing(m).input_per_1k == 0.0 for m in gh)


def test_github_factory(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    from dubai.llm_router import get_chat_model

    model = get_chat_model("github:gpt-4o-mini")
    assert model.__class__.__name__ == "ChatOpenAI"


def test_github_llama_ask_model_disables_parallel_tools(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    from dubai.llm_router import get_ask_chat_model, get_chat_model

    model = get_ask_chat_model("github:llama-3.3-70b")
    assert model.model_kwargs.get("parallel_tool_calls") is False
    assert (
        get_chat_model("github:llama-3.3-70b").model_kwargs.get("parallel_tool_calls")
        is False
    )


def test_unknown_model_raises():
    from dubai.llm_router import get_chat_model

    with pytest.raises(ValueError, match="unknown model"):
        get_chat_model("not-a-model")


def test_pricing_present_for_all():
    from dubai.llm_router import list_models
    from dubai.model_pricing import get_model_pricing, load_model_pricing

    table = load_model_pricing()
    for model_id in list_models():
        assert model_id in table
        rates = get_model_pricing(model_id)
        assert rates.input_per_1k >= 0
        assert rates.output_per_1k >= 0


def test_openai_factory(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from dubai.llm_router import get_chat_model

    model = get_chat_model("gpt-4o")
    assert model.__class__.__name__ == "ChatOpenAI"


@pytest.mark.parametrize(
    "model_id,module",
    [
        ("gemini-1.5-pro", "langchain_google_genai"),
        ("grok-2-beta-fast", "langchain_xai"),
        ("qwen-2.5-72b-instruct", "langchain_groq"),
        ("llama-3.1", "langchain_ollama"),
    ],
)
def test_optional_provider_factories(model_id, module, monkeypatch):
    if importlib.util.find_spec(module) is None:
        pytest.skip(f"{module} not installed")
    for key in ["ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "XAI_API_KEY", "GROQ_API_KEY"]:
        monkeypatch.setenv(key, "x")
    from dubai.llm_router import get_chat_model

    assert get_chat_model(model_id) is not None
