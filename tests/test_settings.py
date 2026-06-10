def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("NEO4J_PASSWORD", "secret123")
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    from dubai.settings import Settings

    s = Settings(_env_file=None)
    assert s.neo4j_password == "secret123"
    assert s.neo4j_uri.startswith("bolt://")


def test_settings_defaults(monkeypatch):
    for key in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "XAI_API_KEY", "GROQ_API_KEY"]:
        monkeypatch.delenv(key, raising=False)
    from dubai.settings import Settings

    s = Settings(_env_file=None)
    assert s.default_model == "gpt-4o"
    assert s.local_backend in {"ollama", "vllm"}
    assert s.openai_api_key is None
    assert isinstance(s.cors_origins, list)


def test_cors_origins_comma_separated_env(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000,https://app.example.com")
    from dubai.settings import Settings

    s = Settings(_env_file=None)
    assert s.cors_origins == ["http://localhost:3000", "https://app.example.com"]


def test_cors_origins_empty_env_uses_default(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "")
    from dubai.settings import Settings

    s = Settings(_env_file=None)
    assert s.cors_origins == ["http://localhost:3000", "http://127.0.0.1:3000"]
