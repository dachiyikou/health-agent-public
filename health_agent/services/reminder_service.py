from __future__ import annotations

from health_agent.schemas.record_schema import ReminderCreatePayload, ReminderPayload
from health_agent.repositories.reminder_repository import ReminderRepository


class ReminderService:
    def __init__(self, runtime):
        self.runtime = runtime
        self.reminders = ReminderRepository(runtime.db)

    def create_reminder(self, payload: dict) -> dict:
        request = ReminderCreatePayload(**payload)
        reminder = ReminderPayload(
            user_id=request.user_id,
            reminder_type=request.recurrence,
            target_name=request.title,
            cron_expr=self._cron_from_request(request),
            local_time=request.schedule_time,
            timezone="Asia/Shanghai",
            status="active" if request.enabled else "paused",
            metadata={"content": request.content, "source": "manual", "recurrence": request.recurrence},
        )
        reminder_id = self.reminders.create_reminder(reminder)
        created = self.reminders.get_reminder(reminder_id)
        if created and request.enabled:
            self.runtime.scheduler.sync_job(created)
        return created or {"id": reminder_id}

    def list_reminders(self, user_id: str) -> list[dict]:
        return self.reminders.list_reminders(user_id)

    def toggle_reminder(self, reminder_id: int, enabled: bool) -> dict:
        updated = self.reminders.set_enabled(reminder_id, enabled)
        if updated is None:
            raise ValueError(f"Reminder {reminder_id} not found")
        if enabled:
            self.runtime.scheduler.sync_job(updated)
        else:
            self.runtime.scheduler.remove_job(reminder_id)
        return updated

    def delete_reminder(self, reminder_id: int) -> dict:
        deleted = self.reminders.delete_reminder(reminder_id)
        if deleted is None:
            raise ValueError(f"Reminder {reminder_id} not found")
        self.runtime.scheduler.remove_job(reminder_id)
        return {"deleted_reminder_id": reminder_id}

    def _cron_from_request(self, request: ReminderCreatePayload) -> str:
        hour, minute = request.schedule_time.split(":")
        if request.recurrence == "daily":
            return f"{minute} {hour} * * *"
        return f"{minute} {hour} * * 1"
