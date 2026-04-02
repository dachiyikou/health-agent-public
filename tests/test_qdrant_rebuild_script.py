from pathlib import Path


def test_qdrant_rebuild_script_exists():
    script = Path(__file__).resolve().parents[1] / "scripts" / "rebuild_qdrant_collections.py"
    assert script.exists()
    content = script.read_text(encoding="utf-8")
    assert "ensure_collections" in content
    assert "delete" in content.lower()
    assert "sys.path.insert" in content
    assert "from health_agent.config import" in content
