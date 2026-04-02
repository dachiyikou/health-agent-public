from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from health_agent.runtime import create_session_id


page_router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


def _render(request: Request, template_name: str, page_title: str, active_nav: str, context: dict) -> HTMLResponse:
    data = {
        "request": request,
        "page_title": page_title,
        "active_nav": active_nav,
        "asset_version": getattr(request.app.state, "asset_version", "dev"),
        **context,
    }
    return templates.TemplateResponse(request=request, name=template_name, context=data)


@page_router.get("/", response_class=HTMLResponse)
@page_router.get("/copilot", response_class=HTMLResponse)
def copilot_page(request: Request, user_id: str = "demo-user", session_id: str | None = None) -> HTMLResponse:
    if getattr(request.app.state, "bootstrap_error", None):
        response = _render(
            request,
            "bootstrap_error.html",
            "系统状态",
            "copilot",
            {"error_detail": request.app.state.bootstrap_error},
        )
        response.status_code = 503
        return response
    service = request.app.state.services["copilot"]
    query_session_id = request.query_params.get("session_id") or session_id
    sessions = service.list_sessions(user_id)
    if request.query_params.get("new_session") == "1" and query_session_id:
        resolved_session_id = query_session_id
    elif query_session_id:
        resolved_session_id = query_session_id
    else:
        resolved_session_id = sessions[0]["id"] if sessions else "demo-session"
    messages = service.get_messages(user_id, resolved_session_id)
    sessions = service.list_sessions(user_id)
    return _render(
        request,
        "copilot.html",
        "Copilot",
        "copilot",
        {
            "user_id": user_id,
            "session_id": resolved_session_id,
            "new_session_id": create_session_id(),
            "messages": messages,
            "sessions": sessions,
        },
    )


@page_router.get("/profile", response_class=HTMLResponse)
def profile_page(
    request: Request,
    user_id: str = "demo-user",
    session_id: str | None = None,
    trend_window: str = "7d",
) -> HTMLResponse:
    if getattr(request.app.state, "bootstrap_error", None):
        response = _render(
            request,
            "bootstrap_error.html",
            "系统状态",
            "profile",
            {"error_detail": request.app.state.bootstrap_error},
        )
        response.status_code = 503
        return response
    service = request.app.state.services["profile"]
    resolved_window = trend_window if trend_window in {"7d", "30d"} else "7d"
    profile = service.get_profile(user_id, trend_window=resolved_window)
    return _render(
        request,
        "profile.html",
        "健康档案",
        "profile",
        {"user_id": user_id, "session_id": session_id, "profile": profile, "trend_window": resolved_window},
    )


@page_router.get("/records", response_class=HTMLResponse)
def records_page(request: Request, user_id: str = "demo-user", session_id: str | None = None) -> HTMLResponse:
    if getattr(request.app.state, "bootstrap_error", None):
        response = _render(
            request,
            "bootstrap_error.html",
            "系统状态",
            "records",
            {"error_detail": request.app.state.bootstrap_error},
        )
        response.status_code = 503
        return response
    service = request.app.state.services["record"]
    records = service.list_records(user_id, limit=100, days=7)
    return _render(
        request,
        "records.html",
        "记录录入",
        "records",
        {"user_id": user_id, "session_id": session_id, "records": records},
    )


@page_router.get("/reminders", response_class=HTMLResponse)
def reminders_page(request: Request, user_id: str = "demo-user", session_id: str | None = None) -> HTMLResponse:
    if getattr(request.app.state, "bootstrap_error", None):
        response = _render(
            request,
            "bootstrap_error.html",
            "系统状态",
            "reminders",
            {"error_detail": request.app.state.bootstrap_error},
        )
        response.status_code = 503
        return response
    service = request.app.state.services["reminder"]
    reminders = service.list_reminders(user_id)
    return _render(
        request,
        "reminders.html",
        "提醒中心",
        "reminders",
        {"user_id": user_id, "session_id": session_id, "reminders": reminders},
    )
