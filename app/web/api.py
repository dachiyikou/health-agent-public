from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse


api_router = APIRouter(prefix="/api")


async def _payload(request: Request) -> dict:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        return await request.json()
    form = await request.form()
    return dict(form)


def _parse_bool(value, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _to_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.replace("，", ",")
        return [item.strip() for item in text.split(",") if item.strip()]
    return [str(value).strip()] if str(value).strip() else []


@api_router.get("/copilot/messages")
def get_copilot_messages(request: Request, user_id: str = "demo-user", session_id: str = "demo-session"):
    service = request.app.state.services["copilot"]
    return service.get_messages(user_id, session_id)


@api_router.post("/copilot/message")
async def post_copilot_message(request: Request):
    payload = await _payload(request)
    service = request.app.state.services["copilot"]
    return service.handle_message(
        payload.get("user_id", "demo-user"),
        payload.get("session_id", "demo-session"),
        payload.get("message", ""),
    )


def _format_sse(event: dict) -> str:
    event_type = event.get("type", "message")
    return f"event: {event_type}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


@api_router.post("/copilot/message/stream")
async def post_copilot_message_stream(request: Request):
    payload = await _payload(request)
    service = request.app.state.services["copilot"]
    user_id = payload.get("user_id", "demo-user")
    session_id = payload.get("session_id", "demo-session")
    message = payload.get("message", "")

    def event_stream():
        if hasattr(service, "stream_message"):
            for event in service.stream_message(user_id, session_id, message):
                yield _format_sse(event)
            return

        result = service.handle_message(user_id, session_id, message)
        fallback_events = [
            {"type": "user_echo", "session_id": session_id, "text": message},
            {"type": "assistant_done", "session_id": session_id, "text": result.get("answer", "")},
            {"type": "done", "session_id": session_id},
        ]
        for event in fallback_events:
            yield _format_sse(event)

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


@api_router.post("/copilot/session/{session_id}/delete")
async def delete_copilot_session(request: Request, session_id: str):
    payload = await _payload(request)
    service = request.app.state.services["copilot"]
    return service.delete_session(payload.get("user_id", "demo-user"), session_id)


@api_router.post("/copilot/sessions/clear")
async def clear_copilot_sessions(request: Request):
    payload = await _payload(request)
    service = request.app.state.services["copilot"]
    return service.clear_sessions(payload.get("user_id", "demo-user"))


@api_router.get("/profile")
def get_profile(request: Request, user_id: str = "demo-user"):
    service = request.app.state.services["profile"]
    return service.get_profile(user_id)


@api_router.post("/profile")
async def post_profile(request: Request):
    payload = await _payload(request)
    for key in ("allergies", "medical_history", "long_term_medications"):
        if key in payload:
            payload[key] = _to_list(payload.get(key))
    service = request.app.state.services["profile"]
    user_id = payload.get("user_id", "demo-user")
    return service.update_profile(user_id, payload)


@api_router.get("/records")
def get_records(request: Request, user_id: str = "demo-user", limit: int = 20, days: int | None = None):
    service = request.app.state.services["record"]
    return service.list_records(user_id, limit=limit, days=days)


@api_router.post("/records")
async def post_records(request: Request):
    payload = await _payload(request)
    service = request.app.state.services["record"]
    try:
        return service.create_record(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@api_router.post("/records/{record_id}/delete")
async def delete_record(request: Request, record_id: int):
    payload = await _payload(request)
    service = request.app.state.services["record"]
    try:
        return service.delete_record(payload.get("user_id", "demo-user"), record_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.post("/records/clear")
async def clear_records(request: Request):
    payload = await _payload(request)
    service = request.app.state.services["record"]
    return service.clear_records(payload.get("user_id", "demo-user"))


@api_router.post("/records/clear-all")
async def clear_records_alias(request: Request):
    payload = await _payload(request)
    service = request.app.state.services["record"]
    return service.clear_records(payload.get("user_id", "demo-user"))


@api_router.get("/reminders")
def get_reminders(request: Request, user_id: str = "demo-user"):
    service = request.app.state.services["reminder"]
    return service.list_reminders(user_id)


@api_router.post("/reminders")
async def post_reminders(request: Request):
    payload = await _payload(request)
    service = request.app.state.services["reminder"]
    return service.create_reminder(payload)


@api_router.post("/reminders/{reminder_id}/toggle")
async def toggle_reminder(request: Request, reminder_id: int):
    payload = await _payload(request)
    service = request.app.state.services["reminder"]
    try:
        return service.toggle_reminder(reminder_id, _parse_bool(payload.get("enabled"), default=True))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.post("/reminders/{reminder_id}/delete")
async def delete_reminder(request: Request, reminder_id: int):
    service = request.app.state.services["reminder"]
    try:
        return service.delete_reminder(reminder_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
