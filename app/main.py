from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HEALTH_AGENT_ROOT = PROJECT_ROOT / "health_agent"

for import_path in (PROJECT_ROOT, HEALTH_AGENT_ROOT):
    value = str(import_path)
    if value not in sys.path:
        sys.path.insert(0, value)

from app.web.api import api_router
from app.web.pages import page_router
from health_agent.runtime import get_runtime
from health_agent.services.copilot_service import CopilotService
from health_agent.services.profile_service import ProfileService
from health_agent.services.record_service import RecordService
from health_agent.services.reminder_service import ReminderService


BASE_DIR = Path(__file__).resolve().parent


def _resolve_asset_version() -> str:
    configured = os.getenv("ASSET_VERSION", "").strip()
    if configured:
        return configured
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(PROJECT_ROOT),
                text=True,
            )
            .strip()
            or "dev"
        )
    except Exception:
        return "dev"


def build_services() -> dict:
    runtime = get_runtime()
    return {
        "copilot": CopilotService(runtime),
        "profile": ProfileService(runtime),
        "record": RecordService(runtime),
        "reminder": ReminderService(runtime),
    }


def create_app(services: dict | None = None, bootstrap_error: str | None = None) -> FastAPI:
    app = FastAPI(title="Health Copilot")
    app.state.services = services if services is not None else build_services()
    app.state.bootstrap_error = bootstrap_error
    app.state.asset_version = _resolve_asset_version()
    static_dir = BASE_DIR / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/healthz")
    def healthz():
        if app.state.bootstrap_error:
            return JSONResponse(
                status_code=503,
                content={"status": "error", "detail": app.state.bootstrap_error},
            )
        return {"status": "ok"}

    app.include_router(page_router)
    app.include_router(api_router)
    return app


try:
    app = create_app()
except Exception as exc:  # pragma: no cover - protects imports when runtime deps are unavailable
    app = create_app(services={}, bootstrap_error=str(exc))
