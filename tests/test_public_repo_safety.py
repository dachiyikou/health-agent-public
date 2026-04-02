from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_config_defaults_do_not_expose_internal_hosts():
    content = (PROJECT_ROOT / "health_agent" / "config.py").read_text(encoding="utf-8")

    assert "58.87.70.92" not in content
    assert 'VECTOR_DB_URL = os.getenv("VECTOR_DB_URL", "http://localhost:6333")' in content
    assert 'VECTOR_DB_GRPC_URL = os.getenv("VECTOR_DB_GRPC_URL", "http://localhost:6334")' in content
    assert 'LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")' in content
    assert 'PLAYWRIGHT_MCP_URL = os.getenv("PLAYWRIGHT_MCP_URL", "http://localhost:8931")' in content


def test_env_example_uses_local_placeholder_hosts():
    content = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")

    assert "58.87.70.92" not in content
    assert "VECTOR_DB_URL=http://localhost:6333" in content
    assert "VECTOR_DB_GRPC_URL=http://localhost:6334" in content
    assert "LANGFUSE_HOST=http://localhost:3000" in content
    assert "PLAYWRIGHT_MCP_URL=http://localhost:8931" in content


def test_vector_store_messages_do_not_reference_machine_specific_credentials_path():
    content = (PROJECT_ROOT / "health_agent" / "tools" / "vector_store.py").read_text(encoding="utf-8")

    assert "/home/lighthouse/credentials.txt" not in content
    assert "Set QDRANT_API_KEY in your environment." in content
    assert "Check QDRANT_API_KEY configuration." in content
