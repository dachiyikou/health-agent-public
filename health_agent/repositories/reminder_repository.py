from __future__ import annotations

from sqlalchemy import select

from schemas.record_schema import ReminderPayload
from tools.db import DBClient, Reminder, utcnow


class ReminderRepository:
    def __init__(self, db: DBClient):
        self.db = db

    def create_reminder(self, payload: ReminderPayload) -> int:
        return self.db.save_reminder(payload)

    def list_reminders(self, user_id: str) -> list[dict]:
        with self.db.session_scope() as session:
            rows = session.scalars(
                select(Reminder)
                .where(Reminder.user_id == user_id, Reminder.status != "deleted")
                .order_by(Reminder.created_at.desc(), Reminder.id.desc())
            ).all()
        return [self.db._reminder_to_dict(row) for row in rows]

    def get_reminder(self, reminder_id: int) -> dict | None:
        with self.db.session_scope() as session:
            row = session.get(Reminder, reminder_id)
        if row is None:
            return None
        return self.db._reminder_to_dict(row)

    def set_enabled(self, reminder_id: int, enabled: bool) -> dict | None:
        with self.db.session_scope() as session:
            row = session.get(Reminder, reminder_id)
            if row is None or row.status == "deleted":
                return None
            row.status = "active" if enabled else "paused"
            row.updated_at = utcnow()
        return self.get_reminder(reminder_id)

    def delete_reminder(self, reminder_id: int) -> dict | None:
        row = self.get_reminder(reminder_id)
        if row is None or row.get("status") == "deleted":
            return None
        self.db.delete_reminder(reminder_id)
        return self.get_reminder(reminder_id)
