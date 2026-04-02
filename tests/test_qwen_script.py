from pathlib import Path


def test_qwen_smoke_script_exists():
    script = Path(__file__).resolve().parents[1] / "scripts" / "test_qwen.py"
    assert script.exists()
    content = script.read_text(encoding="utf-8")
    assert "DASHSCOPE_API_KEY" in content
    assert "OpenAI" in content
