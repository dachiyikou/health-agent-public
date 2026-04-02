from __future__ import annotations

from health_agent.tools.db import DBClient


class ChatRepository:
    def __init__(self, db: DBClient):
        self.db = db

    def ensure_session(self, user_id: str, session_id: str, title: str | None = None) -> None:
        self.db.ensure_session(user_id, session_id, title=title)

    def save_message(self, session_id: str, role: str, content: str, message_type: str = "chat") -> int:
        return self.db.save_message(session_id, role, content, message_type=message_type)

    def list_messages(self, session_id: str, limit: int = 50) -> list[dict]:
        return self.db.get_recent_messages(session_id, limit=limit)

    def list_sessions(self, user_id: str) -> list[dict]:
        return self.db.list_sessions(user_id)

    def delete_session(self, user_id: str, session_id: str) -> None:
        self.db.delete_session(user_id, session_id)

    def clear_sessions(self, user_id: str) -> None:
        self.db.clear_sessions(user_id)
