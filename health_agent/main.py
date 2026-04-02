from __future__ import annotations

from health_agent.runtime import create_session_id, get_runtime
from health_agent.services.copilot_service import CopilotService


def _build_error_response(exc: Exception) -> dict:
    return {
        "answer": f"处理失败：{exc}",
        "citations": [],
        "risk_level": "error",
        "current_agent": "system",
        "data": {"error": str(exc)},
    }


def handle_user_message(user_id: str, session_id: str, message: str) -> dict:
    try:
        runtime = get_runtime()
        result = CopilotService(runtime).handle_message(user_id, session_id, message)
        runtime.db.audit(
            action="handle_user_message",
            payload={"parsed": result.get("parsed", {}), "result": result},
            user_id=user_id,
            session_id=session_id,
        )
        runtime.tracer.log_event(
            "handle_user_message",
            {"user_id": user_id, "session_id": session_id, "route": result.get("current_agent", "unknown")},
        )
        return result
    except Exception as exc:
        try:
            logger = get_runtime().logger
            logger.exception("Failed to handle user message.")
        except Exception:
            logger = None
        return _build_error_response(exc)
