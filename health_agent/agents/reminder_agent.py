from __future__ import annotations

from health_agent.config import DEFAULT_TIMEZONE
from health_agent.jobs.scheduler import ReminderScheduler
from health_agent.schemas.agent_schema import AgentResponse
from health_agent.schemas.record_schema import ReminderPayload
from health_agent.tools.db import DBClient


class ReminderAgent:
    def __init__(self, db: DBClient, scheduler: ReminderScheduler):
        self.db = db
        self.scheduler = scheduler

    def run(self, user_id: str, parsed: dict, profile: dict) -> dict:
        schedule = parsed.get("schedule", {})
        local_time = schedule.get("local_time")
        if not local_time:
            raise ValueError("未识别到提醒时间，请使用如“每天早上8点提醒我吃药”的表达。")
        timezone = profile.get("timezone") or DEFAULT_TIMEZONE
        payload = ReminderPayload(
            user_id=user_id,
            reminder_type="medication",
            target_name="健康提醒",
            cron_expr=schedule.get("cron_expr") or "0 9 * * *",
            local_time=local_time,
            timezone=timezone,
            metadata={"source": "chat"},
        )
        reminder_id = self.db.save_reminder(payload)
        reminder_row = {
            "id": reminder_id,
            "user_id": payload.user_id,
            "reminder_type": payload.reminder_type,
            "target_name": payload.target_name,
            "cron_expr": payload.cron_expr,
            "local_time": payload.local_time,
            "timezone": payload.timezone,
            "status": payload.status,
            "metadata": payload.metadata,
        }
        self.scheduler.sync_job(reminder_row)
        result = AgentResponse(
            answer=f"已创建提醒：每天 {payload.local_time}，时区 {payload.timezone}。",
            current_agent="reminder_agent",
            risk_level="low",
            citations=[],
            data={"reminder_id": reminder_id, "schedule": payload.model_dump()},
        )
        return result.model_dump()
