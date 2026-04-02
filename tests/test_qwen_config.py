import importlib


def test_config_exposes_dashscope_settings():
    config = importlib.import_module("config")

    assert hasattr(config, "DASHSCOPE_API_KEY")
    assert hasattr(config, "DASHSCOPE_BASE_URL")
    assert hasattr(config, "DASHSCOPE_CHAT_MODEL")
    assert hasattr(config, "DASHSCOPE_REASON_MODEL")
    assert hasattr(config, "DASHSCOPE_EMBEDDING_MODEL")


def test_validate_required_config_allows_dashscope_only(monkeypatch):
    config = importlib.import_module("config")

    monkeypatch.setattr(config, "DASHSCOPE_API_KEY", "dashscope-test-key")
    monkeypatch.setattr(config, "VECTOR_DB_URL", "http://example.com")

    config.validate_required_config()


def test_config_no_longer_requires_openai_or_groq_attributes():
    config = importlib.import_module("config")

    assert not hasattr(config, "_DEFAULT_OPENAI_API_KEY")
    assert not hasattr(config, "_DEFAULT_GROQ_API_KEY")
