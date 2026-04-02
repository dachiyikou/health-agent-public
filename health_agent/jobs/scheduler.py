from __future__ import annotations

from typing import Any

from health_agent.tools.db import DBClient
from health_agent.tools.logger import build_logger

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except Exception:  # pragma: no cover - optional in current environment
    BackgroundScheduler = None


class ReminderScheduler:
    def __init__(self, db: DBClient):
        self.db = db
        self.logger = build_logger("health_agent.scheduler")
        self.scheduler = BackgroundScheduler(timezone="Asia/Shanghai") if BackgroundScheduler else None
        self.jobs: dict[str, Any] = {}

    def start(self) -> None:
        if self.scheduler and not self.scheduler.running:
            self.scheduler.start()
        self.load_jobs_from_db()

    def load_jobs_from_db(self) -> None:
        for reminder in self.db.list_active_reminders():
            self.sync_job(reminder)

    def sync_job(self, reminder: dict[str, Any]) -> None:
        job_id = str(reminder.get("id"))
        self.jobs[job_id] = reminder
        if not self.scheduler:
            self.logger.warning("APScheduler is not installed; reminder %s stored without runtime scheduling.", job_id)
            return
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
        hour = 9
        minute = 0
        local_time = reminder.get("local_time")
        if local_time and ":" in local_time:
            parts = local_time.split(":")
            hour = int(parts[0])
            minute = int(parts[1])
        self.scheduler.add_job(
            self._emit_job,
            "cron",
            id=job_id,
            hour=hour,
            minute=minute,
            args=[reminder],
            replace_existing=True,
        )

    def remove_job(self, reminder_id: int | str) -> None:
        job_id = str(reminder_id)
        self.jobs.pop(job_id, None)
        if self.scheduler and self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

    def _emit_job(self, reminder: dict[str, Any]) -> None:
        self.logger.info("Reminder triggered: %s", reminder)
