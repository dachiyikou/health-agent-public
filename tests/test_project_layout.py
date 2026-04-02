from __future__ import annotations

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class ProjectLayoutTests(unittest.TestCase):
    def test_python_sources_do_not_use_legacy_internal_imports(self) -> None:
        legacy_prefixes = (
            "from agents.",
            "from config import",
            "from jobs.",
            "from memory.",
            "from repositories.",
            "from runtime import",
            "from schemas.",
            "from services.",
            "from tools.",
        )
        checked_files: list[Path] = []

        for path in REPO_ROOT.rglob("*.py"):
            if path.parts[-2:-1] == ("tests",):
                continue
            text = path.read_text(encoding="utf-8")
            checked_files.append(path)
            for prefix in legacy_prefixes:
                self.assertNotIn(prefix, text, f"{path} still contains legacy import prefix {prefix!r}")

        self.assertGreater(len(checked_files), 0)

    def test_project_does_not_use_sys_path_bootstrap_hacks(self) -> None:
        for relative_path in (
            Path("app/main.py"),
            Path("scripts/rebuild_qdrant_collections.py"),
        ):
            text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
            self.assertNotIn("sys.path.insert", text, f"{relative_path} should not mutate sys.path")
            self.assertNotIn("HEALTH_AGENT_ROOT", text, f"{relative_path} should not depend on HEALTH_AGENT_ROOT")

    def test_run_script_matches_current_runtime(self) -> None:
        run_script = (REPO_ROOT / "health_agent" / "run.sh").read_text(encoding="utf-8")
        self.assertNotIn("source ../venv/bin/activate", run_script)
        self.assertNotIn("streamlit run app.py", run_script)


if __name__ == "__main__":
    unittest.main()
