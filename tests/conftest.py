import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HEALTH_AGENT_ROOT = PROJECT_ROOT / "health_agent"

for path in (HEALTH_AGENT_ROOT, PROJECT_ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

loaded_app = sys.modules.get("app")
if loaded_app is not None:
    module_file = getattr(loaded_app, "__file__", "")
    if module_file and Path(module_file).resolve() == (HEALTH_AGENT_ROOT / "app.py").resolve():
        del sys.modules["app"]
